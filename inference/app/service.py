import os
import time

import cv2
import numpy as np
import torch

from backend.generated import inference_pb2, inference_pb2_grpc

from .labels import ABNORMALITY_LABELS, LOCATION_LABELS
from .model import load_model

MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


class InferenceEngine(inference_pb2_grpc.InferenceEngineServicer):
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = load_model(os.getenv("MODEL_PATH", "/models/efficientvit_multitask.pth"), self.device)
        if os.getenv("USE_TORCH_COMPILE", "false").lower() == "true" and hasattr(torch, "compile"):
            try:
                self.model = torch.compile(self.model)
            except Exception:
                pass
        self.mean = MEAN.to(self.device)
        self.std = STD.to(self.device)
        self._warmup()

    def AnalyzeFrame(self, request, context):
        started = time.perf_counter()
        try:
            tensor = self._preprocess(request.image_jpeg)
            with torch.inference_mode():
                outputs = self.model(tensor)
            location = self._location(outputs["location"])
            segmentation = self._segmentation(outputs["segmentation"])
            abnormality = self._abnormality(outputs["abnormality"])
            processing_ms = (time.perf_counter() - started) * 1000
            return inference_pb2.FrameResponse(
                location=location,
                segmentation=segmentation,
                abnormality=abnormality,
                processing_ms=processing_ms,
            )
        except Exception as exc:
            context.set_code(13)
            context.set_details(str(exc))
            return inference_pb2.FrameResponse()

    def _preprocess(self, image_jpeg):
        raw = np.frombuffer(image_jpeg, dtype=np.uint8)
        bgr = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError("invalid JPEG frame")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (512, 512), interpolation=cv2.INTER_LINEAR)
        tensor = torch.from_numpy(rgb).to(self.device).float().permute(2, 0, 1).unsqueeze(0) / 255.0
        return (tensor - self.mean) / self.std

    def _location(self, logits):
        probs = torch.softmax(logits.float(), dim=1)[0]
        confidence, idx = torch.max(probs, dim=0)
        location_id = int(idx.item())
        conf = float(confidence.item())
        return inference_pb2.Location(
            id=location_id,
            name=LOCATION_LABELS[location_id],
            confidence=conf,
            is_uncertain=conf < 0.6,
        )

    def _segmentation(self, logits):
        mask = (torch.sigmoid(logits.float())[0, 0].cpu().numpy() > 0.5).astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        has_lesion = any(cv2.contourArea(contour) > 24 for contour in contours)
        ok, encoded = cv2.imencode(".png", mask)
        if not ok:
            raise ValueError("failed to encode mask png")
        return inference_pb2.Segmentation(mask_png=encoded.tobytes(), has_lesion=has_lesion)

    def _abnormality(self, logits):
        probs = torch.softmax(logits.float(), dim=1)[0]
        confidence, idx = torch.max(probs, dim=0)
        type_id = int(idx.item())
        conf = float(confidence.item())
        return inference_pb2.Abnormality(
            type_id=type_id,
            type=ABNORMALITY_LABELS[type_id],
            confidence=conf,
            is_uncertain=conf < 0.6,
            is_outside=type_id == 5,
        )

    def _warmup(self):
        dummy = torch.randn(1, 3, 512, 512, device=self.device)
        with torch.inference_mode():
            for _ in range(3):
                self.model(dummy)
