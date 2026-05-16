from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def now_utc():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="doctor")
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
        }


class Patient(db.Model):
    __tablename__ = "patients"

    id = db.Column(db.Integer, primary_key=True)
    name_encrypted = db.Column(db.Text, nullable=False)
    medical_no = db.Column(db.String(64), unique=True, nullable=False, index=True)
    gender = db.Column(db.String(16), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    id_number_encrypted = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)


class AnalysisSession(db.Model):
    __tablename__ = "analysis_sessions"

    id = db.Column(db.String(36), primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="running")
    start_time = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    end_time = db.Column(db.DateTime(timezone=True))

    patient = db.relationship("Patient")
    doctor = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "status": self.status,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class FrameResult(db.Model):
    __tablename__ = "frame_results"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey("analysis_sessions.id"), nullable=False, index=True)
    frame_index = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.Integer, nullable=False)
    location_id = db.Column(db.Integer, nullable=False)
    location_name = db.Column(db.String(64), nullable=False)
    location_conf = db.Column(db.Float, nullable=False)
    abnormality_id = db.Column(db.Integer, nullable=False)
    abnormality_name = db.Column(db.String(32), nullable=False)
    abnormality_conf = db.Column(db.Float, nullable=False)
    has_lesion = db.Column(db.Boolean, default=False, nullable=False)
    is_outside = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)


class SessionSummary(db.Model):
    __tablename__ = "session_summary"

    session_id = db.Column(db.String(36), db.ForeignKey("analysis_sessions.id"), primary_key=True)
    most_frequent_location = db.Column(db.String(64), nullable=False, default="")
    abnormalities_json = db.Column(db.JSON, nullable=False, default=dict)
    lesion_frames_count = db.Column(db.Integer, nullable=False, default=0)
    total_frames = db.Column(db.Integer, nullable=False, default=0)
    duration = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "most_frequent_location": self.most_frequent_location,
            "abnormalities": self.abnormalities_json,
            "lesion_frames_count": self.lesion_frames_count,
            "total_frames": self.total_frames,
            "duration": self.duration,
        }


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey("analysis_sessions.id"), nullable=False, index=True)
    doctor_conclusion = db.Column(db.Text, nullable=False)
    signature_image_path = db.Column(db.String(255), nullable=False)
    pdf_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "doctor_conclusion": self.doctor_conclusion,
            "signature_image_path": self.signature_image_path,
            "pdf_path": self.pdf_path,
            "created_at": self.created_at.isoformat(),
        }


class ModelVersion(db.Model):
    __tablename__ = "model_versions"

    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(80), unique=True, nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    config_path = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "version": self.version,
            "file_path": self.file_path,
            "config_path": self.config_path,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True)
    action = db.Column(db.String(64), nullable=False)
    target_type = db.Column(db.String(64), nullable=False)
    target_id = db.Column(db.String(64))
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)


class VideoStreamConfig(db.Model):
    __tablename__ = "video_stream_configs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    fps = db.Column(db.Integer, nullable=False, default=25)
    resolution = db.Column(db.String(32), nullable=False, default="1280x720")
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "fps": self.fps,
            "resolution": self.resolution,
        }
