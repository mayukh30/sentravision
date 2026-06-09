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
