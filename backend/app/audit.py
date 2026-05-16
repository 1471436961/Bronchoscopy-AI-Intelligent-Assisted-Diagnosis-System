from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from .extensions import db
from .models import AuditLog


def write_audit(action, target_type, target_id=None, user_id=None):
    if user_id is None:
        try:
            verify_jwt_in_request(optional=True)
            user_id = get_jwt_identity()
        except Exception:
            user_id = None
    db.session.add(AuditLog(user_id=user_id, action=action, target_type=target_type, target_id=str(target_id or "")))
    db.session.commit()
