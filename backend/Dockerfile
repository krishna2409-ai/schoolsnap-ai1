# ╔══════════════════════════════════════════════════════════════════════╗
# ║  SchoolSnap AI — Backend Dockerfile                                 ║
# ║  Multi-stage production build with security hardening               ║
# ╚══════════════════════════════════════════════════════════════════════╝

# ── Stage 1: Dependencies ────────────────────────────────────────────
FROM python:3.12-slim AS deps

WORKDIR /app

# System deps for OpenCV, ONNX, FAISS
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Production ─────────────────────────────────────────────
FROM python:3.12-slim AS production

WORKDIR /app

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from deps stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Download AI Models (YuNet and ArcFace) if not present
# This keeps the git repo light while ensuring production has the models
RUN curl -L https://github.com/opencv/opencv_zoo/raw/master/models/face_detection_yunet/face_detection_yunet_2023mar.onnx -o face_detection_yunet.onnx && \
    curl -L https://github.com/onnx/models/raw/main/validated/vision/body_analysis/arcface/model/arcfaceresnet100-8.onnx -o arcfaceresnet100-8.onnx

# Copy application code (exclude test/debug scripts via .dockerignore)
COPY . .

# Create persistent directories
RUN mkdir -p images/events images/previews images/selfies \
             event_uploads_tmp faiss_store

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser && \
    chown -R appuser:appuser /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Production: uvicorn with optimal worker config
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --limit-concurrency 100 --timeout-keep-alive 30 --access-log"]
