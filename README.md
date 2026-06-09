<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/LangGraph-Agentic_AI-FF6F00?logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/YOLOv11-Object_Detection-00FFFF?logo=yolo" />
  <img src="https://img.shields.io/badge/PostgreSQL-316192?logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Pinecone-VectorDB-5B2C6F" />
</p>

# 🛡️ SentraVision — Agentic AI Video Surveillance & Security Platform

**SentraVision** is a full-stack, real-time AI-powered video surveillance system that combines **multi-model computer vision**, a **LangGraph-based agentic AI security assistant**, and a **glassmorphism React dashboard** to detect persons, helmets, vehicles, and license plates — then lets you interrogate the footage using natural language.

> **This is NOT a simple detection pipeline.** The system features a true **Agentic AI** architecture where an autonomous AI agent reasons, selects tools, and chains actions to answer arbitrary security questions about the video.

---

## 📋 Table of Contents

- [Why Agentic AI?](#-why-agentic-ai)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [Detection Pipeline](#-detection-pipeline)
- [Agentic AI Architecture](#-agentic-ai-architecture)
- [Frontend Architecture](#-frontend-architecture)
- [Project Structure](#-project-structure)
- [Setup & Installation](#-setup--installation)
- [Usage](#-usage)
- [API Endpoints](#-api-endpoints)
- [Scaling Strategy](#-scaling-strategy)

---

## 🤖 Why Agentic AI?

Traditional surveillance systems are **passive** — they detect objects and dump logs. SentraVision is fundamentally different:

| Traditional CV Pipeline | SentraVision (Agentic AI) |
|---|---|
| Detect → Log → Done | Detect → Log → **Reason** → **Plan** → **Act** |
| Fixed output format | Dynamic, context-aware responses |
| Cannot answer questions | Natural language Q&A over footage |
| Single model | Multi-model orchestration |
| No tool use | Agent autonomously selects tools |

### What makes it "Agentic"?

1. **Autonomous Reasoning (ReAct Pattern):** The AI agent uses LangGraph's `create_react_agent` to implement the **ReAct (Reasoning + Acting)** pattern. When you ask a question, the agent:
   - **Thinks** about what information it needs
   - **Selects** the appropriate tool(s) from its toolkit
   - **Executes** the tool(s) to gather data
   - **Synthesizes** a final answer

2. **Tool Selection:** The agent has 5 tools and autonomously decides which to use:
   - `query_events_by_sql` — Structured database queries
   - `search_events_by_semantics` — Semantic vector search via Pinecone
   - `count_events` — Aggregation with time-window filtering
   - `get_video_info` — Video metadata extraction
   - `analyze_video_visually` — Multimodal Vision AI (Llama 4 Scout)

3. **Multi-hop Reasoning:** The agent can chain multiple tools. For example:
   - *"How many people without helmets were near cars?"* → Agent calls `count_events(no_helmet)` → then `query_events_by_sql(vehicle_detected)` → cross-references results.

4. **Multimodal Intelligence:** The `analyze_video_visually` tool extracts frames and sends them to a **Vision Language Model (Llama 4 Scout 17B)** via Groq, enabling the agent to answer visual questions like *"Is anyone wearing a green shirt?"* that no SQL query could answer.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        React Frontend (Vite)                        │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  ┌───────────┐ │
│  │  Video    │  │  Stats HUD   │  │  Event Log    │  │  Security │ │
│  │  Player   │  │  (Real-time) │  │  (Scrollable) │  │  Chat AI  │ │
│  └──────────┘  └──────────────┘  └───────────────┘  └───────────┘ │
│                   ┌─────────────────────────────┐                   │
│                   │  Analysis Report (Bottom)    │                   │
│                   │  Stats · Violations · Entities│                  │
│                   └─────────────────────────────┘                   │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP REST (Polling every 1-1.5s)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (Uvicorn)                        │
│                                                                      │
│  ┌─────────────────────┐    ┌──────────────────────────────────┐    │
│  │   CV Pipeline        │    │   Agentic AI (LangGraph)          │   │
│  │   (Background Thread)│    │                                    │   │
│  │                       │    │  ┌────────────┐                   │   │
│  │  YOLO 11n (Persons,  │    │  │  Groq LLM  │ (Llama 3.1 8B)  │   │
│  │   Vehicles, Tracking)│    │  │  (Reasoner) │                  │   │
│  │         │             │    │  └──────┬─────┘                   │   │
│  │  Helmet Model         │    │         │ ReAct Loop              │   │
│  │  (YOLOv8n fine-tuned)│    │  ┌──────▼──────────────────┐     │   │
│  │         │             │    │  │  Tools:                  │     │   │
│  │  EasyOCR              │    │  │  • SQL Query             │     │   │
│  │  (License Plate)      │    │  │  • Semantic Search       │     │   │
│  │         │             │    │  │  • Count Events          │     │   │
│  │         ▼             │    │  │  • Video Info            │     │   │
│  │  Event Logger ────────┼────┼──│  • Visual Analysis (VLM) │     │   │
│  └─────────────────────┘    │  └──────────────────────────┘     │   │
│                              └──────────────────────────────────┘    │
└────────┬──────────────┬──────────────────┬──────────────────────────┘
         │              │                  │
         ▼              ▼                  ▼
   ┌──────────┐  ┌───────────┐     ┌────────────┐
   │PostgreSQL│  │   Redis   │     │  Pinecone  │
   │(Events + │  │ (Pub/Sub  │     │ (Vector DB │
   │ Streams) │  │  Alerts)  │     │  Semantic  │
   └──────────┘  └───────────┘     │  Search)   │
                                    └────────────┘
```

---

## 🛠️ Tech Stack

### Backend

| Technology | Purpose | Why This Choice? |
|---|---|---|
| **FastAPI** | REST API framework | Async support, auto-docs (Swagger), Pydantic validation, fastest Python framework |
| **YOLO 11n** (Ultralytics) | Person & vehicle detection + tracking | State-of-the-art real-time object detection with built-in ByteTrack multi-object tracking |
| **YOLOv8n (fine-tuned)** | Helmet detection | Fine-tuned on helmet/no-helmet dataset from HuggingFace (`iam-tsr/yolov8n-helmet-detection`) |
| **EasyOCR** | License plate reading | No API key needed, supports 80+ languages, works offline, lightweight |
| **LangGraph** | Agentic AI orchestration | Graph-based agent execution with ReAct pattern, better than raw LangChain chains |
| **LangChain** | LLM tooling framework | Tool abstraction, prompt management, model-agnostic design |
| **Groq** (Llama 3.1 8B) | LLM inference (text reasoning) | Ultra-fast inference (>300 tok/s), free tier, ideal for real-time agent responses |
| **Groq** (Llama 4 Scout 17B) | Vision Language Model | Multimodal analysis of video frames, answers visual questions |
| **PostgreSQL** | Relational event storage | ACID compliance, JSON column support for metadata, production-grade |
| **SQLAlchemy** | ORM | Pythonic database access, migration support, connection pooling |
| **Redis** | Pub/Sub event broadcasting | Sub-millisecond latency, perfect for real-time alert propagation |
| **Pinecone** | Vector database | Managed vector search, cosine similarity for semantic event matching |
| **HuggingFace** (`all-MiniLM-L6-v2`) | Sentence embeddings | 384-dim embeddings, fast inference, ideal for semantic search |
| **Uvicorn** | ASGI server | Production-grade, HTTP/2 support, works with FastAPI |

### Frontend

| Technology | Purpose | Why This Choice? |
|---|---|---|
| **React 19** | UI framework | Component-based, hooks API, massive ecosystem |
| **Vite 8** | Build tool & dev server | 10x faster than Webpack, instant HMR, native ESM |
| **Lucide React** | Icon library | Tree-shakeable, consistent design, React-native components |
| **Vanilla CSS** | Styling | Full control over glassmorphism effects, no framework overhead |

### Infrastructure

| Technology | Purpose |
|---|---|
| **Python 3.10+** | Backend runtime |
| **Node.js 18+** | Frontend runtime |
| **Docker** (optional) | Container orchestration for PostgreSQL, Redis |

---

## 🔍 Detection Pipeline

The CV pipeline runs in a **background thread** (`StreamProcessor`) and processes every frame of the uploaded video:

### Stage 1: Object Detection & Tracking
- **Model:** YOLO 11n (`yolo11n.pt`)
- **Classes:** Person (0), Bicycle (1), Car (2), Motorcycle (3), Bus (5), Truck (7)
- **Tracker:** ByteTrack (`bytetrack.yaml`) for persistent multi-object tracking
- **Confidence threshold:** 0.35
- **Lifespan filter:** Objects must persist for ≥10 frames before being logged (prevents flicker)

### Stage 2: Helmet Detection
- **Model:** YOLOv8n fine-tuned on helmet dataset (`iam-tsr/yolov8n-helmet-detection`)
- **Trigger:** Every 2nd frame, only for persons overlapping or near motorcycles
- **Proximity check:** Uses both strict bounding-box overlap AND proximity-based matching (person center within 50% margin of bike bbox)
- **Crop region:** Upper 65% of person bounding box (head + shoulders)
- **Thresholds:** Helmet-on ≥ 55%, No-helmet ≥ 35%
- **One-shot classification:** Each tracked person is classified exactly once

### Stage 3: License Plate OCR
- **Engine:** EasyOCR (English, CPU mode)
- **Trigger:** Every 5th frame on vehicle bounding boxes
- **Crop region:** Lower 35% of vehicle bbox (plate area)
- **Pre-processing:** 3× upscaling with cubic interpolation
- **Validation:** ≥5 characters, must contain at least 1 digit, alphanumeric only
- **Deduplication:** Each unique plate string is logged exactly once

### Event Logging
Every detection is persisted to PostgreSQL with:
- `event_type`: `person_detected`, `vehicle_detected`, `helmet_on`, `no_helmet`, `license_plate`
- `object_id`: ByteTrack tracker ID
- `event_metadata`: JSON containing `confidence`, `bbox`, `video_time`, `vehicle_type`, `plate`

---

## 🧠 Agentic AI Architecture

### The ReAct Agent (LangGraph)

```python
# Simplified agent creation
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(
    llm=ChatGroq(model="llama-3.1-8b-instant"),
    tools=[sql_query, semantic_search, count_events, video_info, visual_analysis]
)
```

### Agent Workflow

```
User Question: "How many people without helmets in the first 5 seconds?"
                    │
                    ▼
            ┌───────────────┐
            │   LLM Thinks  │  "I need to count no_helmet events between 0-5 seconds"
            └───────┬───────┘
                    │
                    ▼
            ┌───────────────┐
            │  Select Tool  │  → count_events(event_type="no_helmet", 
            │               │                  start_time_sec=0, end_time_sec=5)
            └───────┬───────┘
                    │
                    ▼
            ┌───────────────┐
            │  Execute Tool │  → Queries PostgreSQL with time filter
            └───────┬───────┘
                    │
                    ▼
            ┌───────────────┐
            │  Synthesize   │  "There were 3 people detected without helmets
            │  Response     │   in the first 5 seconds of the video."
            └───────────────┘
```

### Tool Descriptions

| Tool | Input | Data Source | Use Case |
|---|---|---|---|
| `query_events_by_sql` | `object_id`, `event_type` | PostgreSQL | Exact lookups: "What happened to person #5?" |
| `search_events_by_semantics` | `query` (natural language) | Pinecone | Fuzzy search: "Someone running near the entrance" |
| `count_events` | `event_type`, `start/end_time` | PostgreSQL | Aggregation: "How many cars in first 3 seconds?" |
| `get_video_info` | None | File system | Metadata: "What is the video resolution?" |
| `analyze_video_visually` | `query` | Video frames → Groq Vision | Visual: "Is anyone wearing a green shirt?" |

---

## 🎨 Frontend Architecture

### Layout Structure
- **Fixed dashboard** (100vh): Header + Video Player + Right Sidebar (Event Log + Security Chat)
- **Scrollable report**: Analysis Report renders below the fold after processing completes

### Real-time Data Flow
1. **Event polling** (every 1.5s): `GET /api/events` → Updates Event Log
2. **Stats polling** (every 1s): `GET /api/streams/status/{id}` → Updates HUD badges
3. **Report fetch** (once, on completion): `GET /api/reports/summary` → Renders bottom report

### Post-Analysis Report Sections
1. **Aggregate Stats**: Persons, Helmets, No-Helmets, Cars, Motorcycles, Vehicles, Plates Read
2. **No-Helmet Time Ranges**: Precise timestamps (e.g., `1.25s – 3.40s`)
3. **Violations Table**: Person ID, Time, Confidence, Associated License Plate (or "Unable to read")
4. **Tracked Entities Grid**: Every unique object with its type, ID, and max confidence score

---

## 📁 Project Structure

```
SentraVision/
├── .env                          # Environment variables (API keys, DB URLs)
├── .gitignore
├── requirements.txt              # Python dependencies
├── README.md
│
├── backend/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entry point
│   │
│   ├── api/
│   │   └── routes.py             # REST API endpoints
│   │
│   ├── agent/
│   │   ├── graph.py              # LangGraph ReAct agent definition
│   │   ├── tools.py              # 5 agent tools (SQL, semantic, count, video, vision)
│   │   └── embedder.py           # HuggingFace sentence embedding + Pinecone upsert
│   │
│   ├── core/
│   │   ├── config.py             # Pydantic settings (env vars)
│   │   └── redis_client.py       # Redis pub/sub client
│   │
│   ├── cv/
│   │   └── processor.py          # StreamProcessor: YOLO + Helmet + OCR pipeline
│   │
│   └── db/
│       ├── database.py           # SQLAlchemy engine + session
│       ├── models.py             # ORM models (Stream, Event)
│       ├── init_db.py            # Table creation script
│       └── pinecone_client.py    # Pinecone vector DB client
│
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx              # React entry point
        ├── App.jsx               # Main application component
        ├── index.css             # Glassmorphism design system
        └── App.css               # Component-specific styles
```

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL (running locally or via Docker)
- Redis (running locally or via Docker)
- Groq API key (free at [console.groq.com](https://console.groq.com))
- Pinecone API key (free at [pinecone.io](https://www.pinecone.io))

### 1. Clone & Environment

```bash
git clone https://github.com/your-username/SentraVision.git
cd SentraVision
```

### 2. Create `.env`

```env
POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/sentravision
REDIS_URL=redis://localhost:6379/0
GROQ_API_KEY=gsk_your_key_here
PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX_NAME=sentravision-events
```

### 3. Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database tables
python -c "from backend.db.init_db import init; init()"

# Start the backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 4. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 5. Open the Dashboard

Navigate to `http://localhost:5173` and upload a video!

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/streams/upload` | Upload video and start processing |
| `GET` | `/api/streams/status/{id}` | Real-time processing stats |
| `GET` | `/api/streams/video/{id}` | Serve video file |
| `GET` | `/api/events` | Get latest detection events |
| `POST` | `/api/query` | Send question to AI agent |
| `GET` | `/api/reports/summary` | Post-analysis summary report |
| `POST` | `/api/streams/start` | Start processing a stream |
| `POST` | `/api/streams/stop/{id}` | Stop a running stream |
| `GET` | `/api/streams/active` | List all active streams |

---

## 📈 Scaling Strategy

### Current Architecture (Single Server)
- Single FastAPI process with background threads
- Local PostgreSQL + Redis
- Suitable for 1-3 concurrent video streams

### Horizontal Scaling

```
                    ┌──────────────┐
                    │  Load Balancer│  (Nginx / AWS ALB)
                    └──────┬───────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │ FastAPI    │ │ FastAPI    │ │ FastAPI    │
     │ Worker 1   │ │ Worker 2   │ │ Worker 3   │
     └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
           │              │              │
           └──────────────┼──────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   ┌────────────┐  ┌───────────┐  ┌────────────┐
   │ PostgreSQL │  │   Redis   │  │  Pinecone  │
   │  (RDS)     │  │  Cluster  │  │  (Managed) │
   └────────────┘  └───────────┘  └────────────┘
```

### Key Scaling Decisions
1. **CV Processing → Celery/Redis Queue**: Move `StreamProcessor` to distributed Celery workers with GPU support
2. **Database → Read replicas**: PostgreSQL read replicas for event queries; write to primary
3. **Video Storage → S3/GCS**: Object storage instead of local filesystem
4. **Real-time → WebSockets**: Replace polling with WebSocket push for sub-second UI updates
5. **Model Serving → Triton/TorchServe**: Dedicated GPU inference servers for YOLO models

---

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with ❤️ using Agentic AI, Computer Vision, and Modern Web Technologies
</p>
