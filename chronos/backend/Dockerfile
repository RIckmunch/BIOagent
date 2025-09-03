FROM python:3.12-slim

WORKDIR /app

# Install system dependencies, including Tesseract OCR and build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tesseract-ocr \
    build-essential \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Do NOT expose 8000 — Render doesn't require EXPOSE
# EXPOSE 8000  ← Remove or comment out

# Use $PORT environment variable (Render assigns 10000 by default)
CMD ["/bin/sh", "-c", "uvicorn chronos.backend.main:app --host 0.0.0.0 --port $PORT"]