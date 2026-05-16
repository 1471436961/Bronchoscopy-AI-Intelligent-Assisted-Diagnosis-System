import uuid
from collections import Counter
from datetime import timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from ..audit import write_audit
from ..authz import require_roles
from ..cache import set_session_status
from ..extensions import db
from ..models import AnalysisSession, FrameResult, Patient, SessionSummary, now_utc

bp = Blueprint("sessions", __name__)


@bp.post("/start")
@require_roles("doctor", "director", "admin")
def start_session():
    data = request.get_json(force=True)
    patient = Patient.query.get_or_404(int(data.get("patient_id")))
    existing = AnalysisSession.query.filter_by(patient_id=patient.id).filter(AnalysisSession.status.in_(["running", "paused"])).first()
    if existing:
        return jsonify({"error": "active_session_exists", "session": existing.to_dict()}), 409

    session = AnalysisSession(id=str(uuid.uuid4()), patient_id=patient.id, doctor_id=int(get_jwt_identity()), status="running")
    db.session.add(session)
    db.session.commit()
    set_session_status(session.id, "running")
    write_audit("start_session", "analysis_session", session.id)
    return jsonify(session.to_dict()), 201


@bp.post("/pause")
@require_roles("doctor", "director", "admin")
def pause_session():
    session = _get_session_from_body()
    if session.status != "running":
        return jsonify({"error": "invalid_transition"}), 409
    session.status = "paused"
    db.session.commit()
    set_session_status(session.id, "paused")
    write_audit("pause_session", "analysis_session", session.id)
    return jsonify(session.to_dict())


@bp.post("/resume")
@require_roles("doctor", "director", "admin")
def resume_session():
    session = _get_session_from_body()
    if session.status != "paused":
        return jsonify({"error": "invalid_transition"}), 409
    session.status = "running"
    db.session.commit()
    set_session_status(session.id, "running")
    write_audit("resume_session", "analysis_session", session.id)
    return jsonify(session.to_dict())


@bp.post("/stop")
@require_roles("doctor", "director", "admin")
def stop_session():
    session = _get_session_from_body()
    if session.status == "stopped":
        return jsonify({"error": "invalid_transition"}), 409
    session.status = "stopped"
    session.end_time = now_utc()
    summary = _build_summary(session)
    db.session.merge(summary)
    db.session.commit()
    set_session_status(session.id, "stopped")
    write_audit("stop_session", "analysis_session", session.id)
    return jsonify({"session": session.to_dict(), "summary": summary.to_dict()})


@bp.get("/<session_id>")
@require_roles("doctor", "director", "admin")
def get_session(session_id):
    session = AnalysisSession.query.get_or_404(session_id)
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", 20)), 1), 100)
    frames_page = FrameResult.query.filter_by(session_id=session_id).order_by(FrameResult.frame_index.desc()).paginate(
        page=page, per_page=page_size, error_out=False
    )
    summary = SessionSummary.query.get(session_id)
    return jsonify(
        {
            "session": session.to_dict(),
            "summary": summary.to_dict() if summary else None,
            "frames": [_frame_to_dict(frame) for frame in frames_page.items],
            "total": frames_page.total,
        }
    )


@bp.get("")
@require_roles("doctor", "director", "admin")
def list_sessions():
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", 10)), 1), 100)
    items = AnalysisSession.query.order_by(AnalysisSession.start_time.desc()).paginate(page=page, per_page=page_size, error_out=False)
    return jsonify({"items": [s.to_dict() for s in items.items], "total": items.total})


def _get_session_from_body():
    data = request.get_json(force=True)
    return AnalysisSession.query.get_or_404(data.get("session_id"))


def _build_summary(session):
    frames = FrameResult.query.filter_by(session_id=session.id).all()
    location_counts = Counter(frame.location_name for frame in frames)
    abnormality_counts = Counter(frame.abnormality_name for frame in frames)
    start_time = _aware_utc(session.start_time)
    end_time = _aware_utc(session.end_time or now_utc())
    duration = int((end_time - start_time).total_seconds())
    return SessionSummary(
        session_id=session.id,
        most_frequent_location=location_counts.most_common(1)[0][0] if location_counts else "",
        abnormalities_json=dict(abnormality_counts),
        lesion_frames_count=sum(1 for frame in frames if frame.has_lesion),
        total_frames=len(frames),
        duration=duration,
    )


def _frame_to_dict(frame):
    return {
        "id": frame.id,
        "frame_index": frame.frame_index,
        "timestamp": frame.timestamp,
        "location": {"id": frame.location_id, "name": frame.location_name, "confidence": frame.location_conf},
        "abnormality": {"type_id": frame.abnormality_id, "type": frame.abnormality_name, "confidence": frame.abnormality_conf},
        "has_lesion": frame.has_lesion,
        "is_outside": frame.is_outside,
    }


def _aware_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
