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
        
        events = query.order_by(Event.timestamp.desc()).limit(10).all()
        if not events:
            return "No matching events found."
        
        return "\n".join([f"Time: {e.timestamp}, Type: {e.event_type}, Desc: {e.description}" for e in events])
    finally:
        db.close()
