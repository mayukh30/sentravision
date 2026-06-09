# SentraVision

AI Video Surveillance & Security Assistant.

## Architecture
- **FastAPI**: Main backend server
- **Ultralytics YOLOv11 & DeepSORT/ByteTrack**: Real-time object detection and tracking
- **PostgreSQL**: Relational metadata storage for events
- **Pinecone**: Vector database for semantic search on events
- **LangGraph & Groq (Llama 3)**: Agentic AI for natural language queries

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**:
   Create a `.env` file in the root directory:
   ```env
   POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/sentravision
   REDIS_URL=redis://localhost:6379/0
   PINECONE_API_KEY=your_pinecone_api_key
   PINECONE_INDEX_NAME=sentravision-events
   GROQ_API_KEY=your_groq_api_key
   ```

3. **Initialize Database**:
   ```bash
   python -m backend.db.init_db
   ```

4. **Run Server**:
   ```bash
   uvicorn backend.main:app --reload
   ```

## API Endpoints

- `POST /api/streams/start` - Start processing a video stream.
  Body: `{"stream_id": 1, "source_url": "path/to/video.mp4"}`
- `POST /api/streams/stop/{stream_id}` - Stop processing a stream.
- `POST /api/query` - Ask the AI agent about events.
  Body: `{"query": "Show me all people detected recently"}`
