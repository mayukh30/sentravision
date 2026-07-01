from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from backend.agent.graph import run_query
from backend.cv.processor import StreamProcessor
from backend.db.database import SessionLocal
from backend.db.models import Event, Stream
from backend.db.pinecone_client import delete_session_embeddings
from backend.core.auth import get_current_user_id, get_optional_user_id
from backend.core.rabbitmq_client import publish_video_task
import shutil
import os
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    session_id: str = None

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/query")
def ask_agent(request: QueryRequest, user_id: int = Depends(get_current_user_id)):
    try:
        # Use user_id as session_id for consistent scoping
        session_id = str(user_id)
        response = run_query(request.query, session_id=session_id)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events")
def get_events(limit: int = 20, session_id: str = Query(None), user_id: int = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        # Always scope to authenticated user
        sid = str(user_id)
        query = db.query(Event).join(Stream, Event.stream_id == Stream.id)
        query = query.filter(Stream.session_id == sid)
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
def upload_video(
    file: UploadFile = File(...),
    session_id: str = Form(None),
    user_id: int = Depends(get_current_user_id),
):
    """Save the uploaded video, create DB record, and publish to RabbitMQ for processing."""
    # Use user_id as the session_id for per-user isolation
    session_id = str(user_id)

    # Create per-user upload directory
    session_upload_dir = os.path.join(UPLOAD_DIR, session_id)
    os.makedirs(session_upload_dir, exist_ok=True)

    # Clear any existing files in this user's upload dir
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
        # 1. Clean up old data for THIS user only
        old_streams = db.query(Stream).filter(Stream.session_id == session_id).all()
        for s in old_streams:
            db.query(Event).filter(Event.stream_id == s.id).delete()
        db.query(Stream).filter(Stream.session_id == session_id).delete()
        db.commit()

        # Clean up old Pinecone embeddings for this user
        try:
            delete_session_embeddings(session_id)
        except Exception:
            pass

        # Clean up stale Redis status so frontend doesn't see old "done" data
        try:
            from backend.core.redis_client import get_redis_client
            rc = get_redis_client()
            if rc:
                rc.delete(f"stream_status:{session_id}")
                rc.delete(f"stream_stop:{session_id}")
        except Exception:
            pass

        # Clean up fallback status and stop files
        try:
            status_file = os.path.join(UPLOAD_DIR, f"status_{session_id}.json")
            if os.path.exists(status_file):
                os.remove(status_file)
        except Exception:
            pass
        try:
            stop_file = os.path.join(UPLOAD_DIR, f"stop_{session_id}")
            if os.path.exists(stop_file):
                os.remove(stop_file)
        except Exception:
            pass

        # 2. Run global cleanup to prevent DB explosion
        cleanup_global_db(db)

        # 3. Create new stream record
        stream = Stream(
            name=safe_name,
            source_url=file_path,
            status="queued",
            session_id=session_id,
            user_id=user_id,
        )
        db.add(stream)
        db.commit()
        db.refresh(stream)
        stream_id = stream.id
    finally:
        db.close()

    # 4. Publish task to RabbitMQ instead of in-memory queue
    try:
        publish_video_task({
            "stream_id": stream_id,
            "source_url": file_path,
            "session_id": session_id,
            "user_id": user_id,
        })
    except Exception as e:
        logger.error(f"Failed to publish to RabbitMQ, falling back: {e}")
        # If RabbitMQ is down, process immediately in-thread as fallback
        import threading
        def fallback_process():
            proc = StreamProcessor(stream_id, file_path, session_id=session_id)
            proc.start()
        threading.Thread(target=fallback_process, daemon=True).start()

    return {
        "message": "Video uploaded and queued for processing.",
        "stream_id": stream_id,
        "session_id": session_id,
        "filename": safe_name,
        "status": "queued",
    }


@router.get("/streams/video")
def serve_video(session_id: str = Query(None), user_id: int = Depends(get_current_user_id)):
    """Serve the uploaded video file so the frontend can play it."""
    sid = session_id or str(user_id)
    session_upload_dir = os.path.join(UPLOAD_DIR, sid)
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
def stream_status(session_id: str = Query(None), user_id: int = Depends(get_current_user_id)):
    """Return real-time YOLO processing stats from Redis (set by worker)."""
    sid = session_id or str(user_id)

    # Check Redis for status published by the worker
    from backend.core.redis_client import get_redis_client
    redis_client = get_redis_client()
    if redis_client:
        try:
            status_data = redis_client.get(f"stream_status:{sid}")
            if status_data:
                return json.loads(status_data)
        except Exception:
            pass

    # Fallback: Check local status file
    try:
        status_file = os.path.join(UPLOAD_DIR, f"status_{sid}.json")
        if os.path.exists(status_file):
            with open(status_file, "r") as f:
                return json.load(f)
    except Exception:
        pass

    # Check DB for stream status
    db = SessionLocal()
    try:
        stream = db.query(Stream).filter(Stream.session_id == sid).order_by(Stream.id.desc()).first()
        if stream:
            return {
                "session_id": sid,
                "status": stream.status,
                "progress": 0 if stream.status == "queued" else 100 if stream.status == "done" else 0,
                "message": f"Status: {stream.status}",
            }
    finally:
        db.close()

    raise HTTPException(status_code=404, detail="Stream not found.")


@router.get("/streams/active")
def list_active_streams(session_id: str = Query(None), user_id: int = Depends(get_current_user_id)):
    """List stats for active/completed streams for the authenticated user."""
    sid = session_id or str(user_id)

    from backend.core.redis_client import get_redis_client
    redis_client = get_redis_client()
    if redis_client:
        try:
            status_data = redis_client.get(f"stream_status:{sid}")
            if status_data:
                return [json.loads(status_data)]
        except Exception:
            pass

    # Fallback: Check local status file
    try:
        status_file = os.path.join(UPLOAD_DIR, f"status_{sid}.json")
        if os.path.exists(status_file):
            with open(status_file, "r") as f:
                return [json.load(f)]
    except Exception:
        pass

    return []


@router.post("/streams/stop")
def stop_stream(session_id: str = Query(None), user_id: int = Depends(get_current_user_id)):
    sid = session_id or str(user_id)

    # Set a stop signal in Redis that the worker checks
    from backend.core.redis_client import get_redis_client
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.set(f"stream_stop:{sid}", "1", ex=300)
        except Exception:
            pass

    # Fallback stop file
    try:
        stop_file = os.path.join(UPLOAD_DIR, f"stop_{sid}")
        with open(stop_file, "w") as f:
            f.write("1")
    except Exception:
        pass

    return {"message": f"Stop signal sent for session {sid}."}


@router.get("/reports/summary")
def get_analysis_summary(session_id: str = Query(None), user_id: int = Depends(get_current_user_id)):
    """Generates a comprehensive post-analysis summary for the authenticated user."""
    sid = session_id or str(user_id)

    db = SessionLocal()
    try:
        query = db.query(Event).join(Stream, Event.stream_id == Stream.id)
        query = query.filter(Stream.session_id == sid)
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
