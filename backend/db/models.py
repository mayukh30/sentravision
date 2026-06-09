from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from backend.db.database import Base
from datetime import datetime

class Stream(Base):
    __tablename__ = "streams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    source_url = Column(String)  # RTSP URL or local file path
    status = Column(String, default="stopped") # active, stopped, error
    created_at = Column(DateTime, default=datetime.utcnow)

    events = relationship("Event", back_populates="stream")

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("streams.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_type = Column(String, index=True) # e.g., "intrusion", "person_detected"
    object_id = Column(String, index=True)  # Tracker ID
    description = Column(String) # e.g. "Person 5 entered the area"
    event_metadata = Column(JSON, nullable=True) # bounding box, confidence, etc.

    stream = relationship("Stream", back_populates="events")
