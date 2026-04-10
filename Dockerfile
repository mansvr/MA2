# Hugging Face Spaces (GPU) + same image works on any NVIDIA host with Docker.
# Build context: repository root (MeshAnythingV2).
#
# Note: pytorch/pytorch:2.1.1-cuda11.8-cudnn8-runtime was removed from Docker Hub.
# Use a current CUDA 11.8 runtime tag (cudnn9) — still compatible with cu118 wheels / flash-attn builds.

FROM pytorch/pytorch:2.5.1-cuda11.8-cudnn9-runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential ninja-build \
    && rm -rf /var/lib/apt/lists/*

# Project deps (upstream) + FastAPI stack
COPY requirements.txt /app/requirements.txt
COPY integrations/space_api/requirements.txt /app/integrations/space_api/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    pip install --no-cache-dir -r /app/integrations/space_api/requirements.txt

# Required by MeshAnything V2 (transformers / OPT path)
ENV MAX_JOBS=4
RUN pip install --no-cache-dir flash-attn --no-build-isolation

COPY . /app

ENV PYTHONPATH=/app
WORKDIR /app/integrations/space_api

EXPOSE 7860

# HF sets PORT; local Docker defaults to 7860
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}"]
