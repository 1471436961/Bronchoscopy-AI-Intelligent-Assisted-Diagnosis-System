from flask import Blueprint, jsonify, request

from ..audit import write_audit
from ..authz import require_roles
from ..extensions import db
from ..models import ModelVersion

bp = Blueprint("model_versions", __name__)


@bp.get("/versions")
@require_roles("doctor", "director", "admin")
def versions():
    items = ModelVersion.query.order_by(ModelVersion.created_at.desc()).all()
    return jsonify({"items": [item.to_dict() for item in items]})


@bp.post("/rollback")
@require_roles("admin", "director")
def rollback():
    data = request.get_json(force=True)
    version_id = int(data.get("version_id"))
    target = ModelVersion.query.get_or_404(version_id)
    ModelVersion.query.update({ModelVersion.is_active: False})
    target.is_active = True
    db.session.commit()
    write_audit("rollback_model", "model_version", target.id)
    return jsonify({"status": "ok", "active": target.to_dict(), "reload": "requested"})
