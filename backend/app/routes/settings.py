from flask import Blueprint, jsonify, request

from ..audit import write_audit
from ..authz import require_roles
from ..extensions import db
from ..models import User, VideoStreamConfig

bp = Blueprint("settings", __name__)


@bp.get("/users")
@require_roles("admin")
def users():
    return jsonify({"items": [user.to_dict() for user in User.query.order_by(User.created_at.desc()).all()]})


@bp.post("/users")
@require_roles("admin")
def create_user():
    data = request.get_json(force=True)
    if User.query.filter_by(username=data.get("username")).first():
        return jsonify({"error": "username_exists"}), 409
    user = User(username=data["username"], role=data.get("role", "doctor"))
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    write_audit("create_user", "user", user.id)
    return jsonify(user.to_dict()), 201


@bp.put("/users/<int:user_id>")
@require_roles("admin")
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json(force=True)
    if "role" in data:
        user.role = data["role"]
    if "password" in data and data["password"]:
        user.set_password(data["password"])
    db.session.commit()
    write_audit("update_user", "user", user.id)
    return jsonify(user.to_dict())


@bp.delete("/users/<int:user_id>")
@require_roles("admin")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    write_audit("delete_user", "user", user_id)
    return jsonify({"status": "ok"})


@bp.get("/streams")
@require_roles("doctor", "director", "admin")
def streams():
    return jsonify({"items": [stream.to_dict() for stream in VideoStreamConfig.query.order_by(VideoStreamConfig.id.asc()).all()]})


@bp.post("/streams")
@require_roles("admin")
def create_stream():
    data = request.get_json(force=True)
    stream = VideoStreamConfig(name=data["name"], url=data["url"], fps=int(data.get("fps", 25)), resolution=data.get("resolution", "1280x720"))
    db.session.add(stream)
    db.session.commit()
    write_audit("create_stream", "video_stream", stream.id)
    return jsonify(stream.to_dict()), 201
