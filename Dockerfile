# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 – Base image
#   Python 3.11 slim keeps the image small while matching typical dev setups.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ─────────────────────────────────────────────────────────────────────────────
# Working directory inside the container
# ─────────────────────────────────────────────────────────────────────────────
WORKDIR /app

# ─────────────────────────────────────────────────────────────────────────────
# Copy dependency manifest first so Docker can cache the pip layer
# (only re-runs pip install when requirements.txt actually changes)
# ─────────────────────────────────────────────────────────────────────────────
COPY requirements.txt .

# ─────────────────────────────────────────────────────────────────────────────
# Install Python dependencies
#   --no-cache-dir  → keeps the image lean (no pip download cache left behind)
#   --upgrade pip   → ensures the resolver is up to date
# ─────────────────────────────────────────────────────────────────────────────
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# Copy the rest of the application source code into the container
# ─────────────────────────────────────────────────────────────────────────────
COPY . .

# ─────────────────────────────────────────────────────────────────────────────
# Expose the port that server.py (FastAPI / Uvicorn) listens on
# ─────────────────────────────────────────────────────────────────────────────
EXPOSE 1337

# ─────────────────────────────────────────────────────────────────────────────
# Runtime command
#   Starts the FastAPI server with Uvicorn.
#   --host 0.0.0.0  → listen on all interfaces (required inside Docker)
#   --port 1337     → must match EXPOSE above
#
#   NOTE: creator_mcp_server.py is spawned as a subprocess by server.py via
#   MCP stdio transport — no separate CMD is needed for it.
#
#   NOTE: Ollama is an external dependency. Either:
#     a) Run Ollama on the host and pass --add-host=host.docker.internal:host-gateway
#     b) Run Ollama in a separate container and use docker-compose (recommended)
# ─────────────────────────────────────────────────────────────────────────────
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "1337"]
