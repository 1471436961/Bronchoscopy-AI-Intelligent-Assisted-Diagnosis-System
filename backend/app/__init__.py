from flask import Flask, jsonify
from flask_cors import CORS

from .config import Config
from .extensions import db, jwt, socketio
from .crypto import encrypt_text
from .models import ModelVersion, Patient, User


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}}, supports_credentials=True)
    db.init_app(app)
    jwt.init_app(app)
    socketio.init_app(
        app,
        cors_allowed_origins=app.config["CORS_ORIGINS"],
        message_queue=app.config.get("SOCKETIO_MESSAGE_QUEUE"),
        async_mode=app.config["SOCKETIO_ASYNC_MODE"],
    )

    from .routes.analysis import bp as analysis_bp
    from .routes.auth import bp as auth_bp
    from .routes.model_versions import bp as model_bp
    from .routes.patients import bp as patients_bp
    from .routes.reports import bp as reports_bp
    from .routes.sessions import bp as sessions_bp
    from .routes.settings import bp as settings_bp
    from .websocket import register_socket_handlers

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(patients_bp, url_prefix="/api/patients")
    app.register_blueprint(sessions_bp, url_prefix="/api/session")
    app.register_blueprint(reports_bp, url_prefix="/api/report")
    app.register_blueprint(model_bp, url_prefix="/api/model")
    app.register_blueprint(settings_bp, url_prefix="/api/settings")
    app.register_blueprint(analysis_bp, url_prefix="/api/analysis")
    register_socket_handlers(socketio)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "not_found"}), 404

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "bad_request", "message": str(error)}), 400

    with app.app_context():
        db.create_all()
        _seed_defaults()

    return app


def _seed_defaults():
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", role="admin")
        admin.set_password("Admin@123456")
        db.session.add(admin)

    if not ModelVersion.query.filter_by(version="mock-efficientvit-b1").first():
        db.session.add(
            ModelVersion(
                version="mock-efficientvit-b1",
                file_path="/models/efficientvit_multitask.pth",
                config_path="/app/configs/efficientvit_config.yaml",
                is_active=True,
            )
        )
    if not Patient.query.filter_by(medical_no="DEMO-0001").first():
        db.session.add(
            Patient(
                name_encrypted=encrypt_text("Demo Patient"),
                medical_no="DEMO-0001",
                gender="male",
                age=56,
                id_number_encrypted=encrypt_text(""),
            )
        )
    db.session.commit()

