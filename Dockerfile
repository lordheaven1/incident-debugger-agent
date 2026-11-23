FROM python:3.12-slim

WORKDIR /app

# Install git so the agent's inspect_node can run git log on the repo
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first to keep the image small, then project dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model during build so container startup is instant
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy application code and git history into the container
COPY . .

EXPOSE 8000

# Uses cloud-injected $PORT if provided (Render/Railway), defaulting to 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]