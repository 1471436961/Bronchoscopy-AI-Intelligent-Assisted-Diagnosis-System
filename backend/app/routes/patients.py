from flask import Blueprint, jsonify, request

from ..audit import write_audit
from ..authz import require_roles
from ..crypto import decrypt_text, encrypt_text
from ..extensions import db
from ..models import Patient

bp = Blueprint("patients", __name__)


def patient_to_dict(patient):
    return {
        "id": patient.id,
        "name": decrypt_text(patient.name_encrypted),
        "medical_no": patient.medical_no,
        "gender": patient.gender,
        "age": patient.age,
        "id_number_masked": _mask(decrypt_text(patient.id_number_encrypted)),
        "created_at": patient.created_at.isoformat(),
    }


def _mask(value):
    if not value:
        return ""
    return value[:3] + "*" * max(0, len(value) - 7) + value[-4:]


@bp.get("")
@require_roles("doctor", "director", "admin")
def list_patients():
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", 10)), 1), 100)
    keyword = request.args.get("q", "").strip()

    query = Patient.query.order_by(Patient.created_at.desc())
    if keyword:
        records = [p for p in query.all() if keyword in p.medical_no or keyword in decrypt_text(p.name_encrypted)]
        total = len(records)
        page_items = records[(page - 1) * page_size : page * page_size]
    else:
        pagination = query.paginate(page=page, per_page=page_size, error_out=False)
        total = pagination.total
        page_items = pagination.items
    return jsonify({"items": [patient_to_dict(p) for p in page_items], "total": total, "page": page, "page_size": page_size})


@bp.post("")
@require_roles("doctor", "director", "admin")
def create_patient():
    data = request.get_json(force=True)
    required = ["name", "medical_no", "gender", "age"]
    missing = [field for field in required if data.get(field) in (None, "")]
    if missing:
        return jsonify({"error": "missing_fields", "fields": missing}), 400
    if Patient.query.filter_by(medical_no=data["medical_no"]).first():
        return jsonify({"error": "medical_no_exists"}), 409

    patient = Patient(
        name_encrypted=encrypt_text(data["name"]),
        medical_no=data["medical_no"],
        gender=data["gender"],
        age=int(data["age"]),
        id_number_encrypted=encrypt_text(data.get("id_number")),
    )
    db.session.add(patient)
    db.session.commit()
    write_audit("create_patient", "patient", patient.id)
    return jsonify(patient_to_dict(patient)), 201


@bp.put("/<int:patient_id>")
@require_roles("doctor", "director", "admin")
def update_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    data = request.get_json(force=True)
    if "name" in data:
        patient.name_encrypted = encrypt_text(data["name"])
    if "medical_no" in data:
        patient.medical_no = data["medical_no"]
    if "gender" in data:
        patient.gender = data["gender"]
    if "age" in data:
        patient.age = int(data["age"])
    if "id_number" in data:
        patient.id_number_encrypted = encrypt_text(data["id_number"])
    db.session.commit()
    write_audit("update_patient", "patient", patient.id)
    return jsonify(patient_to_dict(patient))
