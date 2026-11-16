"""Serve MacroLens in production:  python -m server.run

Deploy targets that need a single start command (Render, Railway, Fly.io,
a VPS) can point at:  uvicorn server.app:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("server.app:app", host="0.0.0.0", port=port, workers=1)
