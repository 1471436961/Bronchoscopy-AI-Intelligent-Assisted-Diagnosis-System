import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///bronchoscopy_ai.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    REDIS_URL = os.getenv("REDIS_URL", "")
    SOCKETIO_MESSAGE_QUEUE = REDIS_URL or None
    SOCKETIO_ASYNC_MODE = os.getenv("SOCKETIO_ASYNC_MODE", "eventlet")
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")
    INFERENCE_GRPC_TARGET = os.getenv("INFERENCE_GRPC_TARGET", "inference:50051")
    INFERENCE_TIMEOUT_SECONDS = float(os.getenv("INFERENCE_TIMEOUT_SECONDS", "3"))
    MOCK_INFERENCE_ENABLED = os.getenv("MOCK_INFERENCE_ENABLED", "true").lower() == "true"

    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
    LOCAL_STORAGE_ROOT = os.getenv("LOCAL_STORAGE_ROOT", "storage")
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET = os.getenv("MINIO_BUCKET", "bronchoscopy-ai")
    MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"


