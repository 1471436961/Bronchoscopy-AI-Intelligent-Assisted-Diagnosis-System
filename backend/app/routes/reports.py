from datetime import datetime

from flask import Blueprint, Response, jsonify, request

from ..audit import write_audit
from ..authz import require_roles
from ..extensions import db
from ..models import AnalysisSession, Report, SessionSummary
from ..pdf import build_report_pdf
from ..routes.patients import patient_to_dict
from ..storage import decode_data_url, read_bytes, save_bytes

bp = Blueprint("reports", __name__)


@bp.post("/generate")
@require_roles("doctor", "director", "admin")
def generate_report():
    data = request.get_json(force=True)
    conclusion = (data.get("doctor_conclusion") or "").strip()
    if not conclusion:
        return jsonify({"error": "doctor_conclusion_required"}), 400

    session = AnalysisSession.query.get_or_404(data.get("session_id"))
    summary = SessionSummary.query.get(session.id)
    ext, content_type, signature_bytes = decode_data_url(data.get("signature_image", ""))
    signature_name = f"signature_{session.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
    signature_path = save_bytes("signatures", signature_name, signature_bytes, content_type)

    pdf_bytes = build_report_pdf(session.patient, session, summary, conclusion, signature_path)
    pdf_name = f"报告_{session.patient.medical_no}_{datetime.now().strftime('%Y%m%d')}.pdf"
    pdf_path = save_bytes("reports", pdf_name, pdf_bytes, "application/pdf")

    report = Report(session_id=session.id, doctor_conclusion=conclusion, signature_image_path=signature_path, pdf_path=pdf_path)
    db.session.add(report)
    db.session.commit()
    write_audit("generate_report", "report", report.id)
    return jsonify(report.to_dict()), 201


@bp.get("/<int:report_id>")
@require_roles("doctor", "director", "admin")
def get_report(report_id):
    report = Report.query.get_or_404(report_id)
    return Response(read_bytes(report.pdf_path), mimetype="application/pdf", headers={"Content-Disposition": f"inline; filename=report_{report.id}.pdf"})


@bp.get("")
@require_roles("doctor", "director", "admin")
def list_reports():
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", 10)), 1), 100)
    items = Report.query.order_by(Report.created_at.desc()).paginate(page=page, per_page=page_size, error_out=False)
    return jsonify({"items": [item.to_dict() for item in items.items], "total": items.total})
