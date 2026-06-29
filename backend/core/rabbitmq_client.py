"""
RabbitMQ client — connection management and message publishing for the video
processing queue.
"""
import json
import logging
import pika
from backend.core.config import settings

logger = logging.getLogger(__name__)

QUEUE_NAME = "video_processing"


def get_rabbitmq_connection():
    """Create a new blocking connection to RabbitMQ."""
    params = pika.URLParameters(settings.RABBITMQ_URL)
    params.heartbeat = 600
    params.blocked_connection_timeout = 300
    return pika.BlockingConnection(params)


def declare_queue(channel):
    """Declare the durable video processing queue (idempotent)."""
    channel.queue_declare(queue=QUEUE_NAME, durable=True)


def publish_video_task(task_data: dict):
    """
    Publish a video processing task to the RabbitMQ queue.

    task_data should contain:
        - stream_id: int
        - source_url: str (file path)
        - session_id: str
        - user_id: int | None
    """
    connection = None
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        declare_queue(channel)

        message = json.dumps(task_data)
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE_NAME,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,  # persistent message
                content_type="application/json",
            ),
        )
        logger.info(f"Published task to RabbitMQ: stream_id={task_data.get('stream_id')}")
    except Exception as e:
        logger.error(f"Failed to publish to RabbitMQ: {e}")
        raise
    finally:
        if connection and connection.is_open:
            connection.close()
