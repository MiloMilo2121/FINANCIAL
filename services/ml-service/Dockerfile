FROM python:3.11-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install shared library
COPY ../shared /tmp/shared
RUN pip install --no-cache-dir /tmp/shared

# Install ML dependencies (separate layer for caching)
COPY pyproject.toml .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -e .

# Copy source
COPY src/ ./src/

EXPOSE 8002

CMD ["python", "src/main.py"]
