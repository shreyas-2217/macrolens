# MacroLens — container image for Docker hosts (Vercel Container runtime,
# Railway, Fly.io, Render, a VPS).
#
# The live demo runs on Vercel's Container runtime, which builds this file and
# serves it as an autoscaling Function. Two host-specific notes:
#   * Vercel routes traffic to port 80 by default; set PORT=80 in the project's
#     environment variables (it overrides the 7860 default below).
#   * Vercel has no persistent disk, so set MACROLENS_DB=/tmp/logs.duckdb there.
#     /tmp is per-instance and wiped on cold start, so the DuckDB log resets.
# For a log that survives restarts, run this image somewhere with a volume
# mounted at /app/data.
#
# CPU-only torch matters: the default PyPI wheel drags in ~2.5 GB of CUDA
# libraries this app never uses.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.hf-cache \
    PORT=7860

WORKDIR /app

# libgomp1 is required by torch's CPU kernels.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# CPU-only torch first. requirements.txt keeps torch unpinned, so pip sees it
# as already satisfied and does not pull the CUDA build on top.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Bake the Food-101 weights in at build time so the first request is fast and
# the container needs no Hugging Face access at runtime.
RUN python -c "from src.classify import load_classifier; load_classifier()"

# Hugging Face Spaces (and some other hosts) run the container as uid 1000.
# Files copied above are owned by root, so open up the paths the app writes:
# the DuckDB log, the HF cache lock files, and the Python bytecode dir.
RUN mkdir -p data .hf-cache \
 && chmod -R a+rwX /app

EXPOSE 7860
CMD ["sh", "-c", "uvicorn server.app:app --host 0.0.0.0 --port ${PORT}"]
