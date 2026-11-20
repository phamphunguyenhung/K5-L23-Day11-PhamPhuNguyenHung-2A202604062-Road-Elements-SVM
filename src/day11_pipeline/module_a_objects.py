"""Module A: Traffic Light & Traffic Sign detector with fisheye-aware edge_zone QC."""
from __future__ import annotations

import cv2
import numpy as np
import torch

from road_lab.cvat_xml import Shape
from road_lab.taxonomy import FISHEYE_CAMERAS
from .schema_adapter import compute_edge_zone

_YOLO_MODEL = None


def _get_yolo():
    global _YOLO_MODEL
    if _YOLO_MODEL is None:
        from ultralytics import YOLO
        _YOLO_MODEL = YOLO("yolov8n.pt")
    return _YOLO_MODEL


def _classify_tl_color(crop_bgr: np.ndarray) -> str:
    if crop_bgr.size == 0:
        return "unknown"
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2]
    s = hsv[:, :, 1]
    h = hsv[:, :, 0]
    bright = (v > 140) & (s > 60)
    if not np.any(bright):
        return "off" if float(np.mean(v)) < 90 else "unknown"
    red_px = int(np.sum(bright & ((h < 12) | (h > 165))))
    yel_px = int(np.sum(bright & (h >= 12) & (h <= 34)))
    grn_px = int(np.sum(bright & (h >= 40) & (h <= 95)))
    counts = {"red": red_px, "yellow": yel_px, "green": grn_px}
    best = max(counts, key=counts.get)
    return best if counts[best] >= 4 else "unknown"


def _classify_sign_group(crop_bgr: np.ndarray) -> str:
    if crop_bgr.size == 0:
        return "other"
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    sat = (s > 70) & (v > 60)
    total = max(1, crop_bgr.shape[0] * crop_bgr.shape[1])
    red_r = float(np.sum(sat & ((h < 12) | (h > 165)))) / total
    yel_r = float(np.sum(sat & (h >= 14) & (h <= 32))) / total
    blu_r = float(np.sum(sat & (h >= 95) & (h <= 130))) / total
    grn_r = float(np.sum(sat & (h >= 45) & (h <= 88))) / total
    if yel_r > 0.18:
        return "warning"
    if red_r > 0.15:
        return "prohibitory"
    if blu_r > 0.18 or grn_r > 0.18:
        return "information"
    return "prohibitory"


def detect_objects(
    img_bgr: np.ndarray,
    camera: str,
    ignore_mask: np.ndarray,
    conf_thresh: float = 0.22,
) -> tuple[list[Shape], list[tuple[float, float, float, float]]]:
    """Detect traffic_light and traffic_sign boxes, plus vehicle boxes for lane/drivable context."""
    h, w = img_bgr.shape[:2]
    is_fisheye = camera in FISHEYE_CAMERAS
    device = 0 if torch.cuda.is_available() else "cpu"
    model = _get_yolo()

    res = model.predict(img_bgr, conf=conf_thresh, imgsz=640, device=device, verbose=False)[0]
    shapes: list[Shape] = []
    vehicle_boxes: list[tuple[float, float, float, float]] = []

    if res.boxes is not None:
        xyxy = res.boxes.xyxy.cpu().numpy()
        cls_ids = res.boxes.cls.cpu().numpy().astype(int)
        for box, cid in zip(xyxy, cls_ids):
            x1, y1, x2, y2 = [float(v) for v in box]
            x1, y1 = max(0.0, x1), max(0.0, y1)
            x2, y2 = min(float(w - 1), x2), min(float(h - 1), y2)
            bw, bh = x2 - x1, y2 - y1
            if cid in {2, 3, 5, 7}:  # car, motorcycle, bus, truck
                vehicle_boxes.append((x1, y1, x2, y2))
                continue
            if bh < 8.0 or bw < 5.0:
                continue
            cx, cy = int((x1 + x2) * 0.5), int((y1 + y2) * 0.5)
            if 0 <= cy < h and 0 <= cx < w and ignore_mask[cy, cx]:
                continue

            crop = img_bgr[int(y1) : int(y2) + 1, int(x1) : int(x2) + 1]
            ez = "true" if (is_fisheye and compute_edge_zone(x1, y1, x2, y2, w, h)) else "false"

            if cid == 9:  # traffic light
                shapes.append(
                    Shape(
                        label="traffic_light",
                        kind="rectangle",
                        points=[(x1, y1), (x2, y2)],
                        attributes={
                            "color": _classify_tl_color(crop),
                            "type": "vehicle",
                            "facing": "front",
                            "edge_zone": ez,
                        },
                    )
                )
            elif cid == 11:  # stop sign
                shapes.append(
                    Shape(
                        label="traffic_sign",
                        kind="rectangle",
                        points=[(x1, y1), (x2, y2)],
                        attributes={
                            "group": "prohibitory",
                            "facing": "front",
                            "edge_zone": ez,
                        },
                    )
                )

    return shapes, vehicle_boxes
