from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router
from backend.api.auth_routes import auth_router
from backend.db.database import engine, Base
from backend.db.models import User, Stream, Event

app = FastAPI(
    title="SentraVision API",
    description="Backend API for AI Video Surveillance & Security Assistant",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(auth_router, prefix="/api")

@app.on_event("startup")
def on_startup():
    """Create all database tables on startup (including User table)."""
    Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"message": "Welcome to SentraVision API"}
