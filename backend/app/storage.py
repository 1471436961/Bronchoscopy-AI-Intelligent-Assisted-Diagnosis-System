import base64
import os
from io import BytesIO
from pathlib import Path

from flask import current_app
from minio import Minio


def _root():
    root = Path(current_app.config["LOCAL_STORAGE_ROOT"])
    root.mkdir(parents=True, exist_ok=True)
    return root


def _minio_client():
    return Minio(
        current_app.config["MINIO_ENDPOINT"],
        access_key=current_app.config["MINIO_ACCESS_KEY"],
        secret_key=current_app.config["MINIO_SECRET_KEY"],
        secure=current_app.config["MINIO_SECURE"],
    )


def save_bytes(category, filename, data, content_type="application/octet-stream"):
    if current_app.config["STORAGE_BACKEND"] == "minio":
        bucket = current_app.config["MINIO_BUCKET"]
        client = _minio_client()
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        object_name = f"{category}/{filename}"
        client.put_object(bucket, object_name, BytesIO(data), len(data), content_type=content_type)
        return f"minio://{bucket}/{object_name}"

    path = _root() / category
    path.mkdir(parents=True, exist_ok=True)
    target = path / filename
    target.write_bytes(data)
    return str(target)


def read_bytes(path):
    if path.startswith("minio://"):
        _, rest = path.split("://", 1)
        bucket, object_name = rest.split("/", 1)
        response = _minio_client().get_object(bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
    return Path(path).read_bytes()


def decode_data_url(data_url):
    if "," in data_url:
        header, payload = data_url.split(",", 1)
        ext = "png" if "png" in header else "jpg"
        content_type = "image/png" if ext == "png" else "image/jpeg"
    else:
        payload = data_url
        ext = "png"
        content_type = "image/png"
    return ext, content_type, base64.b64decode(payload)
