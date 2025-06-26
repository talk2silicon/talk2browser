import threading
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..utils.config import is_vision_enabled, get_vision_model_path

class VisionService:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._latest_results = None
        self._latest_image_path = None
        self._model_path = get_vision_model_path()
        self._logger = logging.getLogger(__name__)
        self._model = None
        if is_vision_enabled():
            self._load_model()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = VisionService()
            return cls._instance

    def _load_model(self):
        try:
            from ultralytics import YOLO
            self._logger.info(f"[VisionService] Loading YOLOv11 model from {self._model_path}")
            self._model = YOLO(self._model_path)
        except Exception as e:
            self._logger.error(f"[VisionService] Failed to load YOLOv11 model: {e}")
            self._model = None

    def store_screenshot(self, image_path: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Store the latest screenshot path and optional metadata. Overwrites previous.
        """
        self._latest_image_path = image_path
        self._latest_metadata = metadata or {}
        self._logger.debug(f"[VisionService] Stored screenshot: {image_path} with metadata: {self._latest_metadata}")

    def analyze(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Run YOLOv11 inference on the given image, store the latest screenshot, and vision results.
        Returns a list of dicts: [{label, bbox, confidence}, ...]
        """
        if not is_vision_enabled():
            self._logger.debug("[VisionService] Vision is disabled. Skipping analysis.")
            return []
        if self._model is None:
            self._logger.warning("[VisionService] YOLOv11 model not loaded. Skipping analysis.")
            return []
        try:
            self.store_screenshot(image_path)
            results = self._model(image_path)
            detections = []
            for box in results[0].boxes:
                label = self._model.names[int(box.cls)]
                bbox = [float(coord) for coord in box.xyxy[0].tolist()]
                confidence = float(box.conf)
                detections.append({
                    "label": label,
                    "bbox": bbox,
                    "confidence": confidence
                })
            self._logger.info(f"[VisionService] YOLOv11 detected {len(detections)} elements in {image_path}")
            self._latest_results = detections
            return detections
        except Exception as e:
            self._logger.error(f"[VisionService] YOLOv11 inference failed: {e}")
            return []

    def get_latest_results(self) -> Optional[List[Dict[str, Any]]]:
        return self._latest_results

    def get_latest_image_path(self) -> Optional[str]:
        return self._latest_image_path

    def get_latest_metadata(self) -> Optional[Dict[str, Any]]:
        return getattr(self, '_latest_metadata', None)
