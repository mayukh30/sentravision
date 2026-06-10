### SentraVision — Agentic AI Video Surveillance & Security Platform

**Why this project is unique & how it helps:**
Unlike traditional passive CCTV systems that just record video and dump logs, SentraVision transforms surveillance into an interactive, queryable AI assistant. It actively monitors footage to detect safety violations (like missing helmets) and license plates in real-time, saving hours of manual review. What makes it truly unique is the **Agentic AI** layer—security operators can simply type questions like *"How many people without helmets walked past cars?"* and the system autonomously reasons, retrieves the data, and synthesizes an answer.

**Technologies Used:**
- **Languages:** Python, JavaScript (ES6+), SQL
- **Computer Vision:** YOLOv11 (with ByteTrack multi-object tracking), YOLOv8n (Fine-tuned for helmet detection), EasyOCR, OpenCV
- **Generative AI & LLMs:** Groq API, Llama 3.1 8B (Text LLM for reasoning), Llama 4 Scout 17B (Vision Language Model for multimodal frame analysis)
- **NLP & Agentic AI:** LangGraph (ReAct agent architecture), LangChain (Tool orchestration), HuggingFace MiniLM-L6-v2 (Text embeddings for semantic search)
- **Backend & APIs:** FastAPI, Uvicorn, SQLAlchemy
- **Databases & Infrastructure:** PostgreSQL (ACID event store), Redis (Pub/Sub real-time broadcasting), Pinecone (Vector Database)
- **Frontend:** React 19, Vite 8, CSS Glassmorphism Design System

**Key Achievements & Impact:**
- **Engineered an Agentic AI Security Assistant:** Utilized the **ReAct pattern** via **LangGraph** to build an autonomous agent that dynamically selects from 5 custom tools (SQL, Semantic Vector Search, Temporal Aggregation, Vision AI) to answer complex natural language security queries.
- **Architected a Multi-Model CV Pipeline:** Developed a background-threaded **FastAPI** service running **YOLOv11**, **YOLOv8n**, and **EasyOCR** concurrently to detect persons, vehicles, license plates, and helmet compliance in real-time without blocking the API event loop.
- **Implemented Multimodal Generative AI:** Integrated **Llama 4 Scout 17B** as a VLM tool, allowing the agent to extract and visually inspect video frames on-the-fly to answer abstract queries (e.g., *"Is anyone wearing a red shirt?"*) that structural databases cannot answer.
- **Built Semantic Search Capabilities:** Leveraged **HuggingFace** NLP models to embed event descriptions into dense vectors, storing them in **Pinecone** to allow fuzzy semantic searching (RAG) of surveillance logs.
- **Designed a High-Performance Real-Time Dashboard:** Created a stunning **React 19** frontend featuring a glassmorphism UI, connected to a **Redis Pub/Sub** architecture for sub-millisecond event broadcasting and live HUD stat updates.
