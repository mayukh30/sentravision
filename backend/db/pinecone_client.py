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

def upsert_event_embedding(event_id: int, text_description: str, embedding: list):
    index = get_vector_index()
    if index:
        try:
            index.upsert(
                vectors=[
                    {"id": f"event_{event_id}", "values": embedding, "metadata": {"event_id": event_id, "text": text_description}}
                ]
            )
        except Exception as e:
            logger.error(f"Error upserting to Pinecone: {e}")
