import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "SentraVision"
    POSTGRES_URL: str = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/sentravision")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "sentravision-events")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # RabbitMQ
    RABBITMQ_URL: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    # JWT Authentication
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24

    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
