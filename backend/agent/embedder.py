from langchain_huggingface import HuggingFaceEmbeddings
from backend.db.pinecone_client import upsert_event_embedding
import logging

logger = logging.getLogger(__name__)

embeddings_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def embed_and_store_event(event_id: int, text: str):
    try:
        vector = embeddings_model.embed_query(text)
        upsert_event_embedding(event_id, text, vector)
        logger.info(f"Successfully embedded and stored event {event_id}")
    except Exception as e:
        logger.error(f"Failed to embed and store event {event_id}: {e}")
