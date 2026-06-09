from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from backend.agent.graph import run_query
from backend.cv.processor import StreamProcessor
from backend.db.database import SessionLocal
from backend.db.models import Event
import shutil
import os

router = APIRouter()

class QueryRequest(BaseModel):
    query: str

class StreamRequest(BaseModel):
    stream_id: int
    source_url: str

active_processors = {}
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
        return [{"id": e.id, "time": e.timestamp.strftime("%I:%M %p"), "type": e.event_type, "desc": e.description} for e in events]
    finally:
        db.close()

@router.post("/streams/upload")
async def upload_video(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    stream_id = len(active_processors) + 1
    processor = StreamProcessor(stream_id, file_path)
    processor.start()
    active_processors[stream_id] = processor
    
    return {"message": "Video uploaded and processing started.", "stream_id": stream_id}

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
