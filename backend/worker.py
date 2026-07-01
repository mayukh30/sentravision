"""
RabbitMQ worker — consumes video processing tasks from the queue and runs
StreamProcessor. Designed to run as a separate process alongside FastAPI.

Usage:
    python -m backend.worker
"""
import json
import logging
import time
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.config import settings
from backend.core.rabbitmq_client import get_rabbitmq_connection, declare_queue, QUEUE_NAME
from backend.core.redis_client import get_redis_client
from backend.cv.processor import StreamProcessor
from backend.db.database import SessionLocal
from backend.db.models import Stream

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WORKER] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def update_status_in_redis(session_id: str, processor: StreamProcessor):
    """Push the processor's live stats into Redis so the API can read them."""
    stats = processor.get_stats()
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.set(
                f"stream_status:{session_id}",
                json.dumps(stats),
                ex=600,  # expire after 10 minutes
            )
        except Exception as e:
            logger.warning(f"Failed to update Redis status: {e}")
            
    # Fallback: write to local status file
    try:
        uploads_dir = "uploads"
        os.makedirs(uploads_dir, exist_ok=True)
        status_file = os.path.join(uploads_dir, f"status_{session_id}.json")
        with open(status_file, "w") as f:
            json.dump(stats, f)
    except Exception as e:
        logger.error(f"Failed to update fallback status file: {e}")


def update_stream_db_status(stream_id: int, status: str):
    """Update the stream status in the database."""
    db = SessionLocal()
    try:
        stream = db.query(Stream).filter(Stream.id == stream_id).first()
        if stream:
            stream.status = status
            db.commit()
    except Exception as e:
        logger.error(f"Failed to update DB status: {e}")
    finally:
        db.close()


def should_stop(session_id: str) -> bool:
    """Check Redis or local file for a stop signal."""
    redis_client = get_redis_client()
    if redis_client:
        try:
            if redis_client.get(f"stream_stop:{session_id}") is not None:
                return True
        except Exception:
            pass
            
    # Fallback stop file
    try:
        stop_file = os.path.join("uploads", f"stop_{session_id}")
        if os.path.exists(stop_file):
            return True
    except Exception:
        pass
    return False


def process_video_task(task_data: dict):
    """Process a single video task — runs StreamProcessor to completion."""
    stream_id = task_data["stream_id"]
    source_url = task_data["source_url"]
    session_id = task_data.get("session_id", "")
    user_id = task_data.get("user_id")

    logger.info(f"Processing: stream_id={stream_id}, session={session_id}, file={source_url}")

    # Update DB status to processing
    update_stream_db_status(stream_id, "processing")

    # Set initial Redis status so frontend sees "processing" immediately
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.set(
                f"stream_status:{session_id}",
                json.dumps({
                    "stream_id": stream_id,
                    "session_id": session_id,
                    "status": "processing",
                    "progress": 0,
                    "fps": 0,
                    "persons_count": 0,
                    "helmet_count": 0,
                    "no_helmet_count": 0,
                    "vehicle_counts": {"car": 0, "motorcycle": 0, "bicycle": 0, "bus": 0, "truck": 0},
                    "total_vehicles": 0,
                    "license_plates": [],
                    "frames_processed": 0,
                    "total_frames": 0,
                }),
                ex=600,
            )
        except Exception as e:
            logger.warning(f"Failed to set initial Redis status: {e}")

    # Create and start the processor
    processor = StreamProcessor(stream_id, source_url, session_id=session_id)
    processor.start()

    # Poll until done, updating Redis with live stats
    try:
        while processor.status == "processing":
            update_status_in_redis(session_id, processor)

            # Check for stop signal
            if should_stop(session_id):
                logger.info(f"Stop signal received for session {session_id}")
                processor.stop()
                # Clear the stop signal
                redis_client = get_redis_client()
                if redis_client:
                    try:
                        redis_client.delete(f"stream_stop:{session_id}")
                    except Exception:
                        pass
                # Clear fallback stop file
                try:
                    stop_file = os.path.join("uploads", f"stop_{session_id}")
                    if os.path.exists(stop_file):
                        os.remove(stop_file)
                except Exception:
                    pass
                break

            time.sleep(1)

        # Final status update
        update_status_in_redis(session_id, processor)
        final_status = processor.status
        update_stream_db_status(stream_id, final_status)
        logger.info(f"Completed: stream_id={stream_id}, status={final_status}")

    except Exception as e:
        logger.error(f"Error processing stream {stream_id}: {e}")
        update_stream_db_status(stream_id, "error")


def callback(ch, method, properties, body):
    """RabbitMQ message callback — runs for each queued task."""
    try:
        task_data = json.loads(body)
        logger.info(f"Received task: {task_data}")
        process_video_task(task_data)
    except Exception as e:
        logger.error(f"Task processing failed: {e}")
    finally:
        # Acknowledge the message after processing (success or failure)
        ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    """Main worker loop — connects to RabbitMQ and consumes tasks."""
    logger.info("Starting SentraVision video processing worker...")
    logger.info(f"RabbitMQ URL: {settings.RABBITMQ_URL[:30]}...")

    while True:
        try:
            connection = get_rabbitmq_connection()
            channel = connection.channel()
            declare_queue(channel)

            # Process one task at a time
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

            logger.info("Worker ready — waiting for video processing tasks...")
            channel.start_consuming()

        except KeyboardInterrupt:
            logger.info("Worker shutdown requested.")
            break
        except Exception as e:
            logger.error(f"RabbitMQ connection error: {e}")
            logger.info("Reconnecting in 5 seconds...")
            time.sleep(5)


if __name__ == "__main__":
    main()
