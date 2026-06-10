### SentraVision — Agentic AI Video Surveillance & Security Platform

**Tech Stack:** 
- **Languages:** Python, JavaScript (ES6+), SQL
- **AI/ML Models:** YOLO 11n (ByteTrack), YOLOv8n (Fine-tuned for helmets), EasyOCR, Llama 3.1 8B (Text LLM), Llama 4 Scout 17B (Vision LLM), HuggingFace MiniLM-L6-v2 (Embeddings)
- **Backend:** FastAPI, Uvicorn, SQLAlchemy, LangGraph, LangChain, OpenCV
- **Databases & Queues:** PostgreSQL (ACID event store), Redis (Pub/Sub), Pinecone (Vector DB)
- **Frontend:** React 19, Vite 8, Glassmorphism UI, CSS Grid

**Key Achievements:**
- Developed a real-time, multi-model computer vision pipeline combining **YOLO 11n (ByteTrack)** for persistent person/vehicle tracking, a fine-tuned **YOLOv8n** for helmet compliance detection, and **EasyOCR** for automated license plate reading.
- Architected an **Agentic AI Security Assistant** using the **ReAct pattern** via **LangGraph**, empowering users to query video footage in natural language instead of manually reviewing logs.
- Engineered a dynamic tool selection system allowing the autonomous agent to orchestrate 5 specialized tools, including **Pinecone semantic vector search**, **PostgreSQL** structured queries, and temporal event aggregations.
- Integrated a **Multimodal Vision Language Model (Llama 4 Scout 17B)** to process extracted video frames on-the-fly, enabling the agent to accurately answer abstract visual queries (e.g., clothing colors) unanswerable by standard databases.
- Designed a high-performance backend using **FastAPI** with background multi-threading to ensure the CPU/GPU-bound CV pipeline processes frames continuously without blocking the asynchronous API event loop.
- Implemented real-time, bidirectional system observability utilizing **Redis Pub/Sub** for sub-millisecond alert broadcasting alongside a modern, responsive **React 19** dashboard featuring a custom Glassmorphism aesthetic.
