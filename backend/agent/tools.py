from langchain.tools import tool
from backend.db.pinecone_client import get_vector_index
from backend.agent.embedder import embeddings_model
from backend.db.database import SessionLocal
from backend.db.models import Event

@tool
def search_events_by_semantics(query: str, top_k: int = 5):
    """
    Search for events based on semantic meaning or visual description.
    Use this when the user asks for conceptual events like "a person running" or "someone in a red shirt".
    """
    index = get_vector_index()
    if not index:
        return "Vector database not initialized."
    
    query_embedding = embeddings_model.embed_query(query)
    results = index.query(vector=query_embedding, top_k=top_k, include_metadata=True)
    
    events = []
    for match in results.get("matches", []):
        meta = match.get("metadata", {})
        events.append(f"Event ID {meta.get('event_id')}: {meta.get('text')} (Score: {match.get('score'):.2f})")
    
    if not events:
        return "No relevant semantic events found."
    return "\n".join(events)

@tool
def query_events_by_sql(object_id: str = None, event_type: str = None):
    """
    Query events from the relational database using exact filters like object_id or event_type.
    Use this when looking for a specific tracking ID or exact event type (e.g., 'person_detected').
    """
    db = SessionLocal()
    try:
        query = db.query(Event)
        if object_id:
            query = query.filter(Event.object_id == str(object_id))
        if event_type:
            query = query.filter(Event.event_type == event_type)
        
        events = query.order_by(Event.id.asc()).limit(500).all()
        if not events:
            return "No matching events found."
        
        result = []
        for e in events:
            v_time = (e.event_metadata or {}).get('video_time', 'unknown')
            result.append(f"Time: {v_time}s, Type: {e.event_type}, Desc: {e.description}, Meta: {e.event_metadata}")
        return "\n".join(result)
    finally:
        db.close()

@tool
def count_events(event_type: str = None, start_time_sec: float = None, end_time_sec: float = None):
    """
    Count the number of events that match specific filters. 
    Use this when the user asks "how many persons" or "how many helmets in the first 2 seconds".
    event_type can be 'person_detected', 'vehicle_detected', 'helmet_on', 'no_helmet', 'license_plate'.
    start_time_sec and end_time_sec allow filtering by video playback time in seconds (e.g. 0 to 2).
    """
    db = SessionLocal()
    try:
        query = db.query(Event)
        if event_type:
            query = query.filter(Event.event_type == event_type)
        
        events = query.all()
        count = 0
        for e in events:
            meta = e.event_metadata or {}
            video_time = meta.get("video_time", -1.0)
            
            if start_time_sec is not None and video_time < start_time_sec:
                continue
            if end_time_sec is not None and video_time > end_time_sec:
                continue
                
            count += 1
            
        if event_type:
            return f"Found {count} events of type '{event_type}'."
        return f"Found {count} total events."
    finally:
        db.close()

@tool
def get_video_info():
    """
    Get the metadata of the currently analyzed video, such as resolution (width/height), FPS, and total frames.
    Use this when the user asks about the video properties or resolution.
    """
    import os
    import cv2
    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        return "Uploads directory not found."
    files = os.listdir(upload_dir)
    if not files:
        return "No video uploaded yet."
    
    vid_path = os.path.join(upload_dir, files[0])
    cap = cv2.VideoCapture(vid_path)
    if not cap.isOpened():
        return "Failed to open the video file."
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    
    return f"Video Resolution: {width}x{height}, FPS: {fps:.1f}, Total Frames: {total_frames}"

@tool
def analyze_video_visually(query: str):
    """
    Use this tool when the user asks a visual question about the video that cannot be answered by SQL or counting events, 
    such as identifying clothing colors (e.g. 'green tshirt', 'red car'), specific actions, or visual descriptions.
    It samples frames from the video and uses a Vision AI model to answer.
    """
    import os
    import cv2
    import base64
    from langchain_core.messages import HumanMessage
    from langchain_groq import ChatGroq
    from backend.core.config import settings
    
    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        return "Uploads directory not found."
    files = os.listdir(upload_dir)
    if not files:
        return "No video uploaded yet."
    
    vid_path = os.path.join(upload_dir, files[0])
    cap = cv2.VideoCapture(vid_path)
    if not cap.isOpened():
        return "Failed to open the video file."
        
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Extract 5 evenly spaced frames
    frames_to_extract = 5
    step = max(1, total_frames // frames_to_extract)
    
    base64_frames = []
    
    for i in range(frames_to_extract):
        frame_idx = min(i * step, total_frames - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break
            
        # Resize frame to save tokens and avoid payload limits
        frame = cv2.resize(frame, (640, 360))
        _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        b64 = base64.b64encode(buffer).decode('utf-8')
        base64_frames.append(b64)
        
    cap.release()
    
    if not base64_frames:
        return "Failed to extract frames."
        
    # Use Llama 4 Scout Vision model
    llm = ChatGroq(model_name="meta-llama/llama-4-scout-17b-16e-instruct", api_key=settings.GROQ_API_KEY)
    
    content = [{"type": "text", "text": f"You are a security analyst looking at {len(base64_frames)} sequential frames from a video feed. Answer the following question: {query}"}]
    
    for b64 in base64_frames:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })
        
    message = HumanMessage(content=content)
    
    try:
        response = llm.invoke([message])
        return response.content
    except Exception as e:
        return f"Vision analysis failed: {str(e)}"
