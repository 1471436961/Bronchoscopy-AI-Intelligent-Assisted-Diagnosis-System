import base64

from flask import Blueprint, jsonify, request

from ..authz import require_roles
from ..extensions import db, socketio
from ..grpc_client import InferenceUnavailable, analyze_frame
from ..models import AnalysisSession, FrameResult
from ..websocket import emit_frame_result

bp = Blueprint("analysis", __name__)


@bp.post("/frame")
@require_roles("doctor", "director", "admin")
def analyze_frame_endpoint():
    data = request.get_json(force=True)
    session = AnalysisSession.query.get_or_404(data.get("session_id"))
    if session.status != "running":
        return jsonify({"error": "session_not_running", "status": session.status}), 409

    image_payload = data.get("image_jpeg", "")
    if "," in image_payload:
        image_payload = image_payload.split(",", 1)[1]
    try:
        image_jpeg = base64.b64decode(image_payload)
    except Exception:
        return jsonify({"error": "invalid_image_jpeg"}), 400

    try:
        result = analyze_frame(image_jpeg, session.id, int(data.get("timestamp_ms", 0)))
    except InferenceUnavailable as exc:
        return jsonify({"error": "inference_unavailable", "message": str(exc)}), 503

    frame_index = int(data.get("frame_index", 0))
    if frame_index % int(data.get("sample_every", 5)) == 0:
        db.session.add(
            FrameResult(
                session_id=session.id,
                frame_index=frame_index,
                timestamp=result["timestamp"],
                location_id=result["location"]["id"],
                location_name=result["location"]["name"],
                location_conf=result["location"]["confidence"],
                abnormality_id=result["abnormality"]["type_id"],
                abnormality_name=result["abnormality"]["type"],
                abnormality_conf=result["abnormality"]["confidence"],
                has_lesion=result["segmentation"]["has_lesion"],
                is_outside=result["abnormality"]["is_outside"],
            )
        )
        db.session.commit()

    emit_frame_result(socketio, session.id, result)
    return jsonify(result)
