import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from server.main import app as main_app

# Universal Vercel ASGI Proxy Middleware
# Seamlessly handles both direct routing and Vercel serverless rewrites
async def app(scope, receive, send):
    if scope["type"] in ("http", "websocket"):
        path = scope.get("path", "/")
        if path.startswith("/api/index.py"):
            new_path = path[len("/api/index.py"):] or "/"
            scope["path"] = new_path
            scope["raw_path"] = new_path.encode("utf-8")
    await main_app(scope, receive, send)
