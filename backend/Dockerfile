FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/generated

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY inference/proto /proto
RUN mkdir -p /app/generated && touch /app/generated/__init__.py && \
    python -m grpc_tools.protoc -I/proto --python_out=/app/generated --grpc_python_out=/app/generated /proto/inference.proto

COPY backend /app

CMD ["gunicorn", "-k", "eventlet", "-w", "1", "-b", "0.0.0.0:5000", "wsgi:app"]
