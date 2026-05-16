from flask import request
from flask_socketio import emit, join_room

from .cache import set_session_status

NAMESPACE = "/ws/analysis"


def register_socket_handlers(socketio):
    @socketio.on("connect", namespace=NAMESPACE)
    def connect():
        session_id = request.args.get("session_id")
        if session_id:
            join_room(session_id)
            emit("connected", {"session_id": session_id})

    @socketio.on("control", namespace=NAMESPACE)
    def control(data):
        session_id = (data or {}).get("session_id")
        action = (data or {}).get("type")
        if session_id and action in {"pause", "resume"}:
            set_session_status(session_id, "paused" if action == "pause" else "running")
            emit("control_ack", {"session_id": session_id, "type": action}, room=session_id)


def emit_frame_result(socketio, session_id, payload):
    socketio.emit("frame_result", payload, room=session_id, namespace=NAMESPACE)
