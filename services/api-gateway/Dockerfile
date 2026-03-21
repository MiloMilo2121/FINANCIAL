FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY ../shared /tmp/shared
RUN pip install --no-cache-dir /tmp/shared

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY src/ ./src/

EXPOSE 8000

CMD ["python", "src/main.py"]
