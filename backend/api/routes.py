from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from backend.agent.graph import run_query
from backend.cv.processor import StreamProcessor
from backend.db.database import SessionLocal
from backend.db.models import Event, Stream
from backend.db.pinecone_client import delete_session_embeddings
import shutil
import os
import threading
import time

router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    session_id: str = None

# ── Processors keyed by session_id for multi-user isolation ───────────────────
active_processors: dict[str, StreamProcessor] = {}

# ── Queue State ───────────────────────────────────────────────────────────────
queued_sessions: list[str] = []
queue_lock = threading.Lock()
processing_session: str = None

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Background Worker Thread ──────────────────────────────────────────────────
def process_queue_worker():
    global processing_session
    while True:
        session_to_process = None
        
        # 1. Check if the current processor is done or errored
        if processing_session:
            proc = active_processors.get(processing_session)
            if proc and proc.status in ("done", "error", "stopped"):
                with queue_lock:
                    processing_session = None
            elif not proc:
                with queue_lock:
                    processing_session = None

        # 2. Pick up the next job if idle
        with queue_lock:
            if processing_session is None and len(queued_sessions) > 0:
                session_to_process = queued_sessions.pop(0)
                processing_session = session_to_process

        # 3. Start processing
        if session_to_process:
            db = SessionLocal()
            try:
                stream = db.query(Stream).filter(Stream.session_id == session_to_process).order_by(Stream.id.desc()).first()
                if stream:
                    processor = StreamProcessor(stream.id, stream.source_url, session_id=session_to_process)
                    processor.start()
                    active_processors[session_to_process] = processor
            except Exception as e:
                print(f"Failed to start queue job for {session_to_process}: {e}")
                with queue_lock:
                    processing_session = None
            finally:
                db.close()
        
        time.sleep(1)

# Start the worker thread on import
worker_thread = threading.Thread(target=process_queue_worker, daemon=True)
worker_thread.start()


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/query")
def ask_agent(request: QueryRequest):
    try:
        response = run_query(request.query, session_id=request.session_id)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events")
def get_events(limit: int = 20, session_id: str = Query(None)):
    db = SessionLocal()
    try:
        query = db.query(Event).join(Stream, Event.stream_id == Stream.id)
        if session_id:
            query = query.filter(Stream.session_id == session_id)
        events = query.order_by(Event.timestamp.desc()).limit(limit).all()
        return [
            {
                "id": e.id,
                "time": e.timestamp.strftime("%I:%M:%S %p"),
                "type": e.event_type,
                "desc": e.description,
                "metadata": e.event_metadata,
            }
            for e in events
        ]
    finally:
        db.close()


def cleanup_global_db(db):
    """Keep the DB from growing infinitely. Delete all streams except the latest 20."""
    try:
        all_streams = db.query(Stream).order_by(Stream.id.desc()).all()
        if len(all_streams) > 20:
            streams_to_delete = all_streams[20:]
            for s in streams_to_delete:
                db.query(Event).filter(Event.stream_id == s.id).delete()
                # Clean up Pinecone embeddings globally too
                if s.session_id:
                    try:
                        delete_session_embeddings(s.session_id)
                    except:
                        pass
                # Delete upload folder
                if s.session_id:
                    old_dir = os.path.join(UPLOAD_DIR, s.session_id)
                    if os.path.exists(old_dir):
                        shutil.rmtree(old_dir, ignore_errors=True)
            
            # Delete streams
            db.query(Stream).filter(Stream.id.in_([s.id for s in streams_to_delete])).delete(synchronize_session=False)
            db.commit()
    except Exception as e:
        print(f"Global DB cleanup failed: {e}")


@router.post("/streams/upload")
def upload_video(file: UploadFile = File(...), session_id: str = Form(None)):
    """Save the uploaded video, create DB record, and add to the background processing queue."""
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())

    # Stop any existing processor for this session if it's currently running
    if session_id in active_processors:
        active_processors[session_id].stop()
        del active_processors[session_id]

    # Create per-session upload directory
    session_upload_dir = os.path.join(UPLOAD_DIR, session_id)
    os.makedirs(session_upload_dir, exist_ok=True)

    # Clear any existing files in this session's upload dir
    for old_file in os.listdir(session_upload_dir):
        old_path = os.path.join(session_upload_dir, old_file)
        if os.path.isfile(old_path):
            os.remove(old_path)

    safe_name = os.path.basename(file.filename)
    file_path = os.path.join(session_upload_dir, safe_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    db = SessionLocal()
    try:
        # 1. Clean up old data for THIS session only
        old_streams = db.query(Stream).filter(Stream.session_id == session_id).all()
        for s in old_streams:
            db.query(Event).filter(Event.stream_id == s.id).delete()
        db.query(Stream).filter(Stream.session_id == session_id).delete()
        db.commit()

        # Clean up old Pinecone embeddings for this session
        try:
            delete_session_embeddings(session_id)
        except Exception:
            pass

        # 2. Run global cleanup to prevent DB explosion
        cleanup_global_db(db)

        # 3. Create new stream record
        stream = Stream(name=safe_name, source_url=file_path, status="queued", session_id=session_id)
        db.add(stream)
        db.commit()
        db.refresh(stream)
        stream_id = stream.id
    finally:
        db.close()

    # Add to background queue instead of starting immediately
    with queue_lock:
        if session_id in queued_sessions:
            queued_sessions.remove(session_id) # move to back if already queued
        
        global processing_session
        if processing_session == session_id:
            # If they were processing, stop them and push to queue
            processing_session = None

        queued_sessions.append(session_id)
        pos = queued_sessions.index(session_id) + 1

    return {
        "message": "Video uploaded and added to processing queue.",
        "stream_id": stream_id,
        "session_id": session_id,
        "filename": safe_name,
        "status": "queued",
        "position": pos
    }


@router.get("/streams/video")
def serve_video(session_id: str = Query(...)):
    """Serve the uploaded video file so the frontend can play it."""
    # Even if queued, the file is saved in the session's upload dir
    session_upload_dir = os.path.join(UPLOAD_DIR, session_id)
    if not os.path.exists(session_upload_dir):
        raise HTTPException(status_code=404, detail="Video file not found.")
    
    files = os.listdir(session_upload_dir)
    if not files:
        raise HTTPException(status_code=404, detail="Video file not found.")
        
    file_path = os.path.join(session_upload_dir, files[0])
    return FileResponse(
        file_path,
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes"},
    )


@router.get("/streams/status")
def stream_status(session_id: str = Query(...)):
    """Return real-time YOLO processing stats or queue position."""
    # 1. Is it currently processing or done?
    if session_id in active_processors:
        return active_processors[session_id].get_stats()
    
    # 2. Is it in the queue?
    with queue_lock:
        if session_id in queued_sessions:
            pos = queued_sessions.index(session_id) + 1
            return {
                "session_id": session_id,
                "status": "queued",
                "position": pos,
                "progress": 0,
                "message": f"Waiting in queue... (Position: {pos})"
            }
            
    # 3. Not found
    raise HTTPException(status_code=404, detail="Stream not found.")


@router.get("/streams/active")
def list_active_streams(session_id: str = Query(None)):
    """List stats for active/completed streams, optionally filtered by session."""
    if session_id:
        if session_id in active_processors:
            return [active_processors[session_id].get_stats()]
        return []
    return [p.get_stats() for p in active_processors.values()]


@router.post("/streams/stop")
def stop_stream(session_id: str = Query(...)):
    with queue_lock:
        if session_id in queued_sessions:
            queued_sessions.remove(session_id)
            return {"message": f"Session {session_id} removed from queue."}
            
    if session_id in active_processors:
        active_processors[session_id].stop()
        del active_processors[session_id]
        
        global processing_session
        if processing_session == session_id:
            processing_session = None
            
        return {"message": f"Stream for session {session_id} stopped."}
    raise HTTPException(status_code=404, detail="Stream not running.")

@router.get("/reports/summary")
def get_analysis_summary(session_id: str = Query(None)):
    """Generates a comprehensive post-analysis summary for a specific session."""
    db = SessionLocal()
    try:
        query = db.query(Event).join(Stream, Event.stream_id == Stream.id)
        if session_id:
            query = query.filter(Stream.session_id == session_id)
        events = query.order_by(Event.id.asc()).all()
        
        # ── Aggregate counters ──
        total_persons = 0
        total_helmets = 0
        total_no_helmets = 0
        vehicle_counts = {"car": 0, "motorcycle": 0, "bicycle": 0, "bus": 0, "truck": 0}
        
        # ── No-helmet time range tracking ──
        time_ranges = []
        current_range = None
        
        # ── Per-entity tracking ──
        detections = {}           # key: "ID_{obj_id}" -> {id, type, confidence}
        no_helmet_persons = {}    # obj_id -> {video_time, confidence}
        vehicle_plates = {}       # vehicle_obj_id -> plate_text
        plate_to_vehicle = {}     # plate_text -> vehicle_obj_id
        
        for ev in events:
            meta = ev.event_metadata or {}
            
            # Count by event type
            if ev.event_type == "person_detected":
                total_persons += 1
            elif ev.event_type == "helmet_on":
                total_helmets += 1
            elif ev.event_type == "no_helmet":
                total_no_helmets += 1
                v_time = meta.get("video_time")
                no_helmet_persons[ev.object_id] = {
                    "video_time": v_time,
                    "confidence": meta.get("confidence", 0),
                }
                # Time range logic
                if v_time is not None:
                    if current_range is None:
                        current_range = {"start": v_time, "end": v_time}
                    else:
                        if v_time - current_range["end"] <= 2.0:
                            current_range["end"] = v_time
                        else:
                            time_ranges.append(current_range)
                            current_range = {"start": v_time, "end": v_time}
            elif ev.event_type == "vehicle_detected":
                vtype = str(meta.get("vehicle_type", "car")).lower()
                if vtype in vehicle_counts:
                    vehicle_counts[vtype] += 1
            elif ev.event_type == "license_plate":
                plate_text = meta.get("plate", "")
                vid = meta.get("vehicle_id")
                if vid is not None:
                    vehicle_plates[str(vid)] = plate_text
                    plate_to_vehicle[plate_text] = str(vid)
            
            # All-detections map
            if ev.event_type in ["person_detected", "vehicle_detected", "helmet_on", "no_helmet"]:
                conf = meta.get("confidence", 0)
                if ev.event_type == "vehicle_detected":
                    obj_type = str(meta.get("vehicle_type", "vehicle")).capitalize()
                elif ev.event_type in ["helmet_on", "no_helmet"]:
                    obj_type = "Person (Helmet)" if ev.event_type == "helmet_on" else "Person (No Helmet)"
                else:
                    obj_type = "Person"
                    
                obj_id = ev.object_id
                key = f"ID_{obj_id}"
                
                if key not in detections:
                    detections[key] = {"id": obj_id, "type": obj_type, "confidence": conf}
                else:
                    if obj_type != "Person" and detections[key]["type"] == "Person":
                        detections[key]["type"] = obj_type
                    if conf > detections[key]["confidence"]:
                        detections[key]["confidence"] = conf
                        
        if current_range is not None:
            time_ranges.append(current_range)
            
        # ── Format time ranges ──
        formatted_ranges = []
        for r in time_ranges:
            start_s = f"{r['start']:.2f}s"
            end_s = f"{r['end']:.2f}s"
            if abs(r['start'] - r['end']) < 0.1:
                formatted_ranges.append(start_s)
            else:
                formatted_ranges.append(f"{start_s} – {end_s}")
        
        # ── Build violation details (no-helmet + associated plate) ──
        violations = []
        for person_id, info in no_helmet_persons.items():
            # Try to find a license plate associated with a nearby vehicle
            # Strategy: check if any vehicle was detected, try to match plates
            associated_plate = None
            for vid, plate in vehicle_plates.items():
                # Simple association: any plate found
                associated_plate = plate
                break  # Use first available plate (could be improved with spatial matching)
            
            v_time = info.get("video_time")
            violations.append({
                "person_id": person_id,
                "time": f"{v_time:.2f}s" if v_time else "N/A",
                "confidence": info.get("confidence", 0),
                "license_plate": associated_plate if associated_plate else "Unable to read",
            })
                
        all_detections = list(detections.values())
        all_detections.sort(key=lambda x: int(x["id"]) if str(x["id"]).isdigit() else 0)
                
        return {
            "stats": {
                "total_persons": total_persons,
                "total_helmets": total_helmets,
                "total_no_helmets": total_no_helmets,
                "total_cars": vehicle_counts.get("car", 0),
                "total_motorcycles": vehicle_counts.get("motorcycle", 0),
                "total_bicycles": vehicle_counts.get("bicycle", 0),
                "total_buses": vehicle_counts.get("bus", 0),
                "total_trucks": vehicle_counts.get("truck", 0),
                "total_vehicles": sum(vehicle_counts.values()),
                "total_plates_read": len(vehicle_plates),
            },
            "no_helmet_ranges": formatted_ranges,
            "violations": violations,
            "all_detections": all_detections,
        }
    finally:
        db.close()
