# chronos/backend/Dockerfile
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tesseract-ocr \
    build-essential \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory to /app
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the ENTIRE project root (so 'chronos/' is included)
COPY . /app/

# Add /app to PYTHONPATH so 'chronos' is importable
ENV PYTHONPATH=/app

# Use shell to expand $PORT
CMD ["/bin/sh", "-c", "uvicorn chronos.backend.main:app --host 0.0.0.0 --port $PORT"]