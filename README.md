<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black" alt="React"/>
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/LangGraph-Agentic_AI-FF6F00?logo=google&logoColor=white" alt="LangGraph"/>
  <img src="https://img.shields.io/badge/YOLOv11-Object_Detection-00FFFF?logo=yolo" alt="YOLOv11"/>
  <img src="https://img.shields.io/badge/PostgreSQL-316192?logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/Pinecone-VectorDB-5B2C6F" alt="Pinecone"/>
</p>

# 🛡️ SentraVision — Agentic AI Video Surveillance & Security Platform

**SentraVision** is a modern, real-time AI-powered video surveillance system. It combines multi-model computer vision (YOLOv11 + OCR) with a **LangGraph-based Agentic AI security assistant**, packaged in a stunning glassmorphism React dashboard. 

Instead of just detecting objects and dumping logs, SentraVision lets you **interrogate your security footage using natural language**. Ask questions like *"How many people without helmets were near cars?"*, and the autonomous AI agent will reason, select the right tools, and provide an accurate answer.

---

## ✨ Key Features

- **Agentic AI Assistant**: Ask complex, multi-hop questions in plain English. The LangGraph agent autonomously selects between SQL, vector search, and multimodal vision tools.
- **Real-Time Computer Vision Pipeline**: Simultaneously tracks persons, vehicles, reads license plates (EasyOCR), and detects helmet compliance (YOLOv8n fine-tuned).
- **Multimodal Visual Analysis**: Send extracted video frames to a Vision Language Model (Llama 4 Scout) to answer visual questions no database could answer (e.g., *"Is anyone wearing a green shirt?"*).
- **Glassmorphism UI**: A premium, real-time React 19 dashboard with live HUD stats, an auto-scrolling event log, and post-analysis reporting.

---

## 🛠️ Tech Stack

- **Backend / AI Orchestration**: FastAPI, LangGraph, LangChain, Uvicorn, Python 3.10+
- **Machine Learning / CV**: YOLO 11n, YOLOv8n, EasyOCR, OpenCV, HuggingFace (`all-MiniLM-L6-v2` embeddings)
- **Large Language Models**: Llama 3.1 8B (Text Reasoning) & Llama 4 Scout 17B (Vision) via Groq
- **Databases**: PostgreSQL (Relational/JSONB), Pinecone (Vector Semantic Search), Redis (Real-time Pub/Sub)
- **Frontend**: React 19, Vite 8, Vanilla CSS Glassmorphism

---

## ⚙️ How It Works (In Brief)

1. **Upload & Detect**: Upload a video. The backend spawns a background thread running the CV pipeline, identifying objects, reading plates, and checking helmets frame-by-frame.
2. **Log & Broadcast**: Events are persisted to PostgreSQL and broadcasted to the frontend via Redis for real-time UI updates. Embeddings are pushed to Pinecone.
3. **Agentic Querying**: When you type a question, the ReAct AI Agent thinks about what it needs to know, selects the best tool (SQL query, Semantic Search, Visual Analysis, or Counting), executes it, and synthesizes a grounded answer.

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.10+ & Node.js 18+
- PostgreSQL & Redis running locally
- API Keys: [Groq](https://console.groq.com) & [Pinecone](https://pinecone.io)

### 1. Clone & Configure
```bash
git clone https://github.com/your-username/SentraVision.git
cd SentraVision
```
Create a `.env` file in the root:
```env
POSTGRES_URL=postgresql://user:password@localhost:5432/sentravision
REDIS_URL=redis://localhost:6379/0
GROQ_API_KEY=gsk_your_key_here
PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX_NAME=sentravision-events
```

### 2. Backend Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -c "from backend.db.init_db import init; init()"
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` and start analyzing footage!
