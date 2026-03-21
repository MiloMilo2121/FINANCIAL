FROM python:3.11-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install shared library first (changes infrequently)
COPY ../shared /tmp/shared
RUN pip install --no-cache-dir /tmp/shared

# Install service dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy source
COPY src/ ./src/

EXPOSE 8001

CMD ["python", "src/main.py"]
