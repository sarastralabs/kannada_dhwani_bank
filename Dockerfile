# Backend image for container hosts (Render, Fly, Hugging Face Spaces).
# Model weights are NOT baked in (they are gitignored) — see docs/DEPLOY_FREE.md.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# CPU-only torch keeps the image far smaller than the default CUDA wheels.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

COPY api ./api
COPY backend ./backend
COPY data ./data
COPY models ./models
COPY run_*.py parler_model_utils.py ./

EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
