import cv2
from ultralytics import YOLO
import threading
import time
from backend.db.database import SessionLocal
from backend.db.models import Event, Stream
from backend.core.redis_client import get_redis_client
import json

class StreamProcessor:
    def __init__(self, stream_id: int, source_url: str):
        self.stream_id = stream_id
        self.source_url = source_url
        self.model = YOLO("yolo11n.pt") # YOLOv11 Nano for real-time
        self.is_running = False
        self.thread = None
        self.tracked_objects = set()

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self._process_stream)
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join()

    def _process_stream(self):
        cap = cv2.VideoCapture(self.source_url)
        if not cap.isOpened():
            print(f"Error: Could not open stream {self.source_url}")
            return

        db = SessionLocal()
        redis_client = get_redis_client()

        try:
            while self.is_running:
                ret, frame = cap.read()
                if not ret:
                    break # End of stream

                # Run YOLO tracking for 'person' class (0)
                results = self.model.track(frame, persist=True, classes=[0], tracker="bytetrack.yaml", verbose=False)

                if results[0].boxes is not None and results[0].boxes.id is not None:
                    boxes = results[0].boxes.xyxy.cpu().numpy()
                    track_ids = results[0].boxes.id.int().cpu().tolist()
                    confidences = results[0].boxes.conf.cpu().numpy()

                    for box, track_id, conf in zip(boxes, track_ids, confidences):
                        if track_id not in self.tracked_objects:
                            # New person detected! 
                            self.tracked_objects.add(track_id)
                            event_desc = f"Person {track_id} detected."
                            
                            new_event = Event(
                                stream_id=self.stream_id,
                                event_type="person_detected",
                                object_id=str(track_id),
                                description=event_desc,
                                event_metadata={"bbox": box.tolist(), "confidence": float(conf)}
                            )
                            db.add(new_event)
                            db.commit()
                            db.refresh(new_event)
                            
                            # Publish to Redis
                            if redis_client:
                                alert_msg = json.dumps({
                                    "event_id": new_event.id,
                                    "stream_id": self.stream_id,
                                    "type": "person_detected",
                                    "object_id": track_id,
                                    "description": event_desc
                                })
                                redis_client.publish("alerts", alert_msg)
                            
                            # TODO: Call Pinecone embedder here

                # Optional: Add small sleep if reading local video too fast
                # time.sleep(0.03) 
        except Exception as e:
            print(f"Stream processing error: {e}")
        finally:
            cap.release()
            db.close()
