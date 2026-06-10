FROM python:3.10-slim

WORKDIR /app

# Install system dependencies required for OpenCV and Redis
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    redis-server \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project directory
COPY . .

# Expose the port that Hugging Face Spaces expects (7860)
EXPOSE 7860

# Start Redis in the background, then start FastAPI
CMD service redis-server start && uvicorn backend.main:app --host 0.0.0.0 --port 7860
