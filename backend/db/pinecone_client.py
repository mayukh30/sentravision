from pinecone import Pinecone
from backend.core.config import settings
import logging

logger = logging.getLogger(__name__)

pc = None

def get_pinecone_client():
    global pc
    if pc is None and settings.PINECONE_API_KEY:
        try:
            pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            logger.info("Pinecone client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
    return pc

def get_vector_index():
    client = get_pinecone_client()
    if client:
        return client.Index(settings.PINECONE_INDEX_NAME)
    return None

def upsert_event_embedding(event_id: int, text_description: str, embedding: list, session_id: str = None):
    index = get_vector_index()
    if index:
        try:
            metadata = {"event_id": event_id, "text": text_description}
            if session_id:
                metadata["session_id"] = session_id
            index.upsert(
                vectors=[
                    {"id": f"event_{event_id}", "values": embedding, "metadata": metadata}
                ]
            )
        except Exception as e:
            logger.error(f"Error upserting to Pinecone: {e}")

def delete_session_embeddings(session_id: str):
    """Delete all vectors for a given session (called on re-upload)."""
    index = get_vector_index()
    if index and session_id:
        try:
            # Use metadata filter to find and delete session vectors
            index.delete(filter={"session_id": {"$eq": session_id}})
            logger.info(f"Deleted Pinecone embeddings for session {session_id}")
        except Exception as e:
            logger.error(f"Error deleting session embeddings: {e}")
