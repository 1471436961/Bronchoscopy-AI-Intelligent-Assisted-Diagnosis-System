import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app


def _key():
    raw = current_app.config.get("ENCRYPTION_KEY") or current_app.config["SECRET_KEY"]
    try:
        decoded = base64.urlsafe_b64decode(raw)
        if len(decoded) in (16, 24, 32):
            return decoded.ljust(32, b"\0")[:32]
    except Exception:
        pass
    return hashlib.sha256(raw.encode("utf-8")).digest()


def encrypt_text(value):
    if value is None or value == "":
        return None
    nonce = os.urandom(12)
    aesgcm = AESGCM(_key())
    encrypted = aesgcm.encrypt(nonce, value.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")


def decrypt_text(value):
    if not value:
        return ""
    blob = base64.urlsafe_b64decode(value.encode("ascii"))
    nonce, encrypted = blob[:12], blob[12:]
    aesgcm = AESGCM(_key())
    return aesgcm.decrypt(nonce, encrypted, None).decode("utf-8")
