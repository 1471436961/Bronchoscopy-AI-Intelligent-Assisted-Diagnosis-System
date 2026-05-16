FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv:/srv/generated

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

COPY inference/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY inference/proto /proto
RUN mkdir -p /srv/generated && touch /srv/generated/__init__.py && \
    python -m grpc_tools.protoc -I/proto --python_out=/srv/generated --grpc_python_out=/srv/generated /proto/inference.proto

COPY inference /srv

CMD ["python", "-m", "app.server"]
