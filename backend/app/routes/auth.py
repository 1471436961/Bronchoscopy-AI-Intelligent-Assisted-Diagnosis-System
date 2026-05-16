from datetime import timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt, jwt_required

from ..audit import write_audit
from ..cache import revoke_token
from ..models import User

bp = Blueprint("auth", __name__)


@bp.post("/login")
def login():
    data = request.get_json(force=True)
    user = User.query.filter_by(username=data.get("username", "")).first()
    if not user or not user.check_password(data.get("password", "")):
        return jsonify({"error": "invalid_credentials"}), 401

    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    write_audit("login", "user", user.id, user_id=user.id)
    return jsonify({"token": token, "user": user.to_dict()})


@bp.post("/logout")
@jwt_required()
def logout():
    revoke_token(get_jwt()["jti"], timedelta(hours=24))
    write_audit("logout", "token")
    return jsonify({"status": "ok"})
