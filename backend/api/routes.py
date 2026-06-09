from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from backend.agent.graph import run_query
from backend.cv.processor import StreamProcessor
from backend.db.database import SessionLocal
from backend.db.models import Event, Stream
import shutil
import os

router = APIRouter()

class QueryRequest(BaseModel):
    query: str

class StreamRequest(BaseModel):
    stream_id: int
    source_url: str

active_processors: dict[int, StreamProcessor] = {}
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/query")
def ask_agent(request: QueryRequest):
    try:
        response = run_query(request.query)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events")
def get_events(limit: int = 20):
    db = SessionLocal()
    try:
        events = db.query(Event).order_by(Event.timestamp.desc()).limit(limit).all()
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


@router.post("/streams/upload")
async def upload_video(file: UploadFile = File(...)):
    """Save the uploaded video, create a DB Stream record, then start CV processing."""
    safe_name = os.path.basename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Create a Stream row so events.stream_id FK is satisfied
    db = SessionLocal()
    try:
        # Purge all existing events and streams to keep DB clean
        db.query(Event).delete()
        db.query(Stream).delete()
        db.commit()

        stream = Stream(name=safe_name, source_url=file_path, status="active")
        db.add(stream)
        db.commit()
        db.refresh(stream)
        stream_id = stream.id
    finally:
        db.close()

    # Start YOLO CV processing in background thread
    processor = StreamProcessor(stream_id, file_path)
    processor.start()
    active_processors[stream_id] = processor

    return {
        "message": "Video uploaded and processing started.",
        "stream_id": stream_id,
        "filename": safe_name,
    }


@router.get("/streams/video/{stream_id}")
def serve_video(stream_id: int):
    """Serve the uploaded video file so the frontend can play it."""
    if stream_id not in active_processors:
        raise HTTPException(status_code=404, detail="Stream not found.")
    file_path = active_processors[stream_id].file_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video file not found.")
    return FileResponse(
        file_path,
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes"},
    )


@router.get("/streams/status/{stream_id}")
def stream_status(stream_id: int):
    """Return real-time YOLO processing stats for a stream."""
    if stream_id not in active_processors:
        raise HTTPException(status_code=404, detail="Stream not found.")
    return active_processors[stream_id].get_stats()


@router.get("/streams/active")
def list_active_streams():
    """List stats for all active/completed streams."""
    return [p.get_stats() for p in active_processors.values()]


@router.post("/streams/start")
def start_stream(request: StreamRequest):
    if request.stream_id in active_processors:
        return {"message": "Stream already running"}
    processor = StreamProcessor(request.stream_id, request.source_url)
    processor.start()
    active_processors[request.stream_id] = processor
    return {"message": f"Stream {request.stream_id} started."}


@router.post("/streams/stop/{stream_id}")
def stop_stream(stream_id: int):
    if stream_id in active_processors:
        active_processors[stream_id].stop()
        del active_processors[stream_id]
        return {"message": f"Stream {stream_id} stopped."}
    raise HTTPException(status_code=404, detail="Stream not running.")

@router.get("/reports/summary")
def get_analysis_summary():
    """Generates a comprehensive post-analysis summary."""
    db = SessionLocal()
    try:
        events = db.query(Event).order_by(Event.id.asc()).all()
        
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
