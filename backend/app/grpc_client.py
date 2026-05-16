import base64
import hashlib
import math
import time
from io import BytesIO

import grpc
from flask import current_app
from PIL import Image, ImageDraw


class InferenceUnavailable(RuntimeError):
    pass


LOCATION_LABELS = [
    "声门",
    "气管",
    "隆突",
    "右主支气管",
    "右肺上叶",
    "右肺中间段",
    "右肺中叶",
    "右肺下叶",
    "右肺上叶·尖段",
    "右肺上叶·后段",
    "右肺上叶·前段",
    "右肺中叶·外侧段",
    "右肺中叶·内侧段",
    "右肺下叶·背段",
    "右肺下叶·内基底段",
    "右肺下叶·前基底段",
    "右肺下叶·外基底段",
    "右肺下叶·后基底段",
    "左主支气管",
    "左肺上叶",
    "左肺下叶",
    "左肺上叶·固有支",
    "左肺上叶·舌段",
    "左肺上叶·固有支·尖后段",
    "左肺上叶·固有支·前段",
    "左肺上叶·舌段·上舌段",
    "左肺上叶·舌段·下舌段",
    "左肺下叶·背段",
    "左肺下叶·前基底段",
    "左肺下叶·外基底段",
    "左肺下叶·后基底段",
]

ABNORMALITY_LABELS = ["病变", "出血", "黏液", "模糊", "正常", "体外"]


def analyze_frame(image_jpeg, session_id, timestamp_ms):
    try:
        from generated import inference_pb2, inference_pb2_grpc
    except Exception as exc:
        if current_app.config["MOCK_INFERENCE_ENABLED"]:
            return mock_analyze_frame(image_jpeg, session_id, timestamp_ms)
        raise InferenceUnavailable("gRPC stubs are not generated") from exc

    target = current_app.config["INFERENCE_GRPC_TARGET"]
    timeout = current_app.config["INFERENCE_TIMEOUT_SECONDS"]
    try:
        with grpc.insecure_channel(target) as channel:
            stub = inference_pb2_grpc.InferenceEngineStub(channel)
            start = time.perf_counter()
            response = stub.AnalyzeFrame(
                inference_pb2.FrameRequest(
                    image_jpeg=image_jpeg,
                    session_id=session_id,
                    timestamp_ms=int(timestamp_ms),
                ),
                timeout=timeout,
            )
            delay_ms = int((time.perf_counter() - start) * 1000)
    except grpc.RpcError as exc:
        if current_app.config["MOCK_INFERENCE_ENABLED"]:
            return mock_analyze_frame(image_jpeg, session_id, timestamp_ms)
        raise InferenceUnavailable(str(exc)) from exc

    return {
        "timestamp": int(timestamp_ms),
        "location": {
            "id": response.location.id,
            "name": response.location.name,
            "confidence": response.location.confidence,
            "is_uncertain": response.location.is_uncertain,
        },
        "abnormality": {
            "type_id": response.abnormality.type_id,
            "type": response.abnormality.type,
            "confidence": response.abnormality.confidence,
            "is_uncertain": response.abnormality.is_uncertain,
            "is_outside": response.abnormality.is_outside,
        },
        "segmentation": {
            "has_lesion": response.segmentation.has_lesion,
            "mask_png": base64.b64encode(response.segmentation.mask_png).decode("ascii"),
        },
        "processing_ms": response.processing_ms,
        "delay_ms": delay_ms,
    }


def mock_analyze_frame(image_jpeg, session_id, timestamp_ms):
    started = time.perf_counter()
    digest = hashlib.sha256(image_jpeg[:4096] + session_id.encode("utf-8") + str(timestamp_ms).encode("ascii")).digest()
    location_id = digest[0] % len(LOCATION_LABELS)
    abnormality_id = _mock_abnormality_id(digest, timestamp_ms)
    has_lesion = abnormality_id in {0, 1, 2} and digest[2] % 3 != 0
    location_conf = 0.62 + (digest[3] / 255) * 0.34
    abnormality_conf = 0.64 + (digest[4] / 255) * 0.32
    processing_ms = (time.perf_counter() - started) * 1000 + 8 + digest[5] % 14
    mask_png = _mock_mask_png(has_lesion, digest)
    return {
        "timestamp": int(timestamp_ms),
        "location": {
            "id": location_id,
            "name": LOCATION_LABELS[location_id],
            "confidence": round(location_conf, 3),
            "is_uncertain": location_conf < 0.6,
        },
        "abnormality": {
            "type_id": abnormality_id,
            "type": ABNORMALITY_LABELS[abnormality_id],
            "confidence": round(abnormality_conf, 3),
            "is_uncertain": abnormality_conf < 0.6,
            "is_outside": abnormality_id == 5,
        },
        "segmentation": {
            "has_lesion": has_lesion,
            "mask_png": base64.b64encode(mask_png).decode("ascii"),
        },
        "processing_ms": round(processing_ms, 2),
        "delay_ms": int(processing_ms),
        "mock": True,
    }


def _mock_abnormality_id(digest, timestamp_ms):
    phase = int(timestamp_ms / 3000) % 9
    if phase in {0, 1, 2, 3}:
        return 4
    if phase == 8:
        return 3
    return digest[1] % 5


def _mock_mask_png(has_lesion, digest):
    image = Image.new("L", (512, 512), 0)
    if has_lesion:
        draw = ImageDraw.Draw(image)
        cx = 160 + digest[6] % 190
        cy = 140 + digest[7] % 200
        rx = 36 + digest[8] % 70
        ry = 28 + digest[9] % 60
        points = []
        for step in range(32):
            angle = step / 32 * math.tau
            wobble = 0.86 + (digest[10 + step % 12] / 255) * 0.28
            points.append((cx + math.cos(angle) * rx * wobble, cy + math.sin(angle) * ry * wobble))
        draw.polygon(points, fill=255)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
