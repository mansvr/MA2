# Hugging Face Spaces (GPU) + same image works on any NVIDIA host with Docker.
# Build context: repository root (MeshAnythingV2).
#
# Note: pytorch/pytorch:2.1.1-cuda11.8-cudnn8-runtime was removed from Docker Hub.
# Use a current CUDA 11.8 runtime tag (cudnn9).

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

# Skip flash-attn compile (often fails on HF builders). Use PyTorch SDPA in the model instead.
ENV MESHANYTHING_USE_SDP_ATTENTION=1
# Avoid invalid OMP_NUM_THREADS from host (libgomp warnings)
ENV OMP_NUM_THREADS=4

COPY . /app

ENV PYTHONPATH=/app
WORKDIR /app/integrations/space_api

EXPOSE 7860

# HF sets PORT; local Docker defaults to 7860
# Force valid OMP before Python (HF sometimes injects empty OMP_NUM_THREADS)
CMD ["sh", "-c", "export OMP_NUM_THREADS=4; exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}"]
