"""Phase 3 & 4: SegFormer Cityscapes Road Segmentation + Shapely Human-Style Geometry Engine."""
from __future__ import annotations

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image as PILImage
from shapely.geometry import Polygon

from road_lab.cvat_xml import Shape
from road_lab.taxonomy import FISHEYE_CAMERAS

_SEG_PROC = None
_SEG_MODEL = None
_SEG_ID = "nvidia/segformer-b0-finetuned-cityscapes-1024-1024"


def _get_segformer():
    global _SEG_PROC, _SEG_MODEL
    if _SEG_MODEL is None:
        from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor
        _SEG_PROC = SegformerImageProcessor.from_pretrained(_SEG_ID)
        _SEG_MODEL = SegformerForSemanticSegmentation.from_pretrained(_SEG_ID)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _SEG_MODEL.to(device).eval()
    return _SEG_PROC, _SEG_MODEL


def predict_road_mask(img_bgr: np.ndarray, ignore_mask: np.ndarray) -> np.ndarray:
    """Return boolean (H, W) road mask from SegFormer Cityscapes (class 0 = road)."""
    h, w = img_bgr.shape[:2]
    proc, model = _get_segformer()
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil = PILImage.fromarray(rgb)
    inputs = proc(images=pil, return_tensors="pt")
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        logits = model(**inputs).logits
    up = F.interpolate(logits, size=(h, w), mode="bilinear", align_corners=False)
    pred = up.argmax(dim=1)[0].cpu().numpy()
    road_mask = (pred == 0) & (~ignore_mask)
    return road_mask


def mask_to_shapely_polygons(
    road_mask: np.ndarray,
    w: int,
    h: int,
    is_fisheye: bool,
    min_area_ratio: float = 0.015,
    simplify_px: float = 10.0,
) -> list[Shape]:
    """Convert road mask into valid, non-self-intersecting Shapely polygons matching human style."""
    u8 = (road_mask.astype(np.uint8)) * 255
    u8 = cv2.morphologyEx(u8, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    u8 = cv2.morphologyEx(u8, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))

    cnts, _ = cv2.findContours(u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = w * h * min_area_ratio
    shapes: list[Shape] = []

    # Sort components by area descending; largest is 'direct', secondary (if substantial) is 'alternative'
    valid_polys: list[tuple[float, list[tuple[float, float]]]] = []
    for cnt in cnts:
        if len(cnt) < 3:
            continue
        raw_pts = [(float(p[0][0]), float(p[0][1])) for p in cnt]
        poly = Polygon(raw_pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty or poly.area < min_area:
            continue
        if poly.geom_type == "MultiPolygon":
            poly = max(poly.geoms, key=lambda g: g.area)
        simp = poly.simplify(simplify_px if is_fisheye else 8.0, preserve_topology=True)
        if simp.is_empty or len(simp.exterior.coords) < 4:
            continue
        coords = [(max(0.0, min(float(w - 1), float(x))), max(0.0, min(float(h - 1), float(y))))
                  for x, y in list(simp.exterior.coords)[:-1]]
        if len(coords) >= 4:
            valid_polys.append((float(poly.area), coords))

    valid_polys.sort(key=lambda x: x[0], reverse=True)
    for idx, (_, coords) in enumerate(valid_polys[:2]):
        atype = "direct" if idx == 0 else "alternative"
        shapes.append(Shape(label="drivable", kind="polygon", points=coords, attributes={"area_type": atype}))
    return shapes
