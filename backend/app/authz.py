from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from .cache import is_token_revoked
from .models import User


def current_user():
    user_id = get_jwt_identity()
    return User.query.get(int(user_id)) if user_id else None


def require_roles(*roles):
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            if is_token_revoked(get_jwt()["jti"]):
                return jsonify({"error": "token_revoked"}), 401
            user = current_user()
            if not user or (roles and user.role not in roles):
                return jsonify({"error": "forbidden"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator
