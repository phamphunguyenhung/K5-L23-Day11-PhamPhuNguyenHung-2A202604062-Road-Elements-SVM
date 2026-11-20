"""Phase 5-8: Benchmark Baseline (HSV) vs V4 (SegFormer + Shapely) on human-annotated drivable frames."""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import Polygon

from road_lab.taxonomy import FISHEYE_CAMERAS, expected_camera
from .module_b_freespace import detect_freespace_and_crosswalk
from .module_d_ignore import compute_ignore_mask
from .v4_segformer import mask_to_shapely_polygons, predict_road_mask

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
REF_DIR = ROOT / "artifacts" / "day11" / "reference"
OUT_JSON = ROOT / "artifacts" / "day11" / "benchmark_v4.json"


def _rasterize(polys: list[list[tuple[float, float]]], h: int, w: int) -> np.ndarray:
    m = np.zeros((h, w), dtype=np.uint8)
    for pts in polys:
        if len(pts) >= 3:
            arr = np.array([[int(round(x)), int(round(y))] for x, y in pts], dtype=np.int32)
            cv2.fillPoly(m, [arr], 1)
    return m.astype(bool)


def _iou_and_bf1(pred: np.ndarray, gt: np.ndarray, tol_px: int = 8) -> tuple[float, float]:
    inter = int(np.sum(pred & gt))
    union = int(np.sum(pred | gt))
    iou = inter / union if union else 0.0

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    p_b = cv2.morphologyEx(pred.astype(np.uint8), cv2.MORPH_GRADIENT, k) > 0
    g_b = cv2.morphologyEx(gt.astype(np.uint8), cv2.MORPH_GRADIENT, k) > 0
    if not np.any(p_b) or not np.any(g_b):
        return iou, 0.0
    dk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * tol_px + 1, 2 * tol_px + 1))
    g_dil = cv2.dilate(g_b.astype(np.uint8), dk) > 0
    p_dil = cv2.dilate(p_b.astype(np.uint8), dk) > 0
    prec = float(np.sum(p_b & g_dil)) / max(1, int(np.sum(p_b)))
    rec = float(np.sum(g_b & p_dil)) / max(1, int(np.sum(g_b)))
    bf1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
    return iou, bf1


def run_benchmark() -> dict:
    examples = [json.loads(line) for line in (REF_DIR / "annotation_examples.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    gt_by_file: dict[str, list[list[tuple[float, float]]]] = defaultdict(list)
    for ex in examples:
        if ex["label"] == "drivable" and ex["provenance"] == "human_created":
            gt_by_file[ex["file"]].append([tuple(p) for p in ex["points"]])

    base_ious, base_bf1s, base_times = [], [], []
    v4_ious, v4_bf1s, v4_times = [], [], []
    v4_invalid = 0
    per_cam: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for fname, gt_polys in sorted(gt_by_file.items()):
        bgr = cv2.imread(str(DATA_DIR / fname))
        if bgr is None:
            continue
        h, w = bgr.shape[:2]
        cam = expected_camera(fname) or "front"
        is_fish = cam in FISHEYE_CAMERAS
        ignore = compute_ignore_mask(bgr, cam)
        gt_mask = _rasterize(gt_polys, h, w)

        # Baseline HSV
        t0 = time.perf_counter()
        b_shapes = [s for s in detect_freespace_and_crosswalk(bgr, cam, ignore) if s.label == "drivable"]
        base_times.append(time.perf_counter() - t0)
        b_mask = _rasterize([s.points for s in b_shapes], h, w)
        bi, bb = _iou_and_bf1(b_mask, gt_mask)
        base_ious.append(bi)
        base_bf1s.append(bb)
        per_cam[cam]["baseline_iou"].append(bi)

        # V4 SegFormer + Shapely
        t1 = time.perf_counter()
        rmask = predict_road_mask(bgr, ignore)
        v4_shapes = mask_to_shapely_polygons(rmask, w, h, is_fish)
        v4_times.append(time.perf_counter() - t1)
        for s in v4_shapes:
            if not Polygon(s.points).is_valid:
                v4_invalid += 1
        v_mask = _rasterize([s.points for s in v4_shapes], h, w)
        vi, vb = _iou_and_bf1(v_mask, gt_mask)
        v4_ious.append(vi)
        v4_bf1s.append(vb)
        per_cam[cam]["v4_iou"].append(vi)
        per_cam[cam]["v4_bf1"].append(vb)

    summary = {
        "evaluated_frames": len(gt_by_file),
        "baseline_hsv": {
            "mean_iou": round(float(np.mean(base_ious)), 4) if base_ious else 0.0,
            "mean_boundary_f1": round(float(np.mean(base_bf1s)), 4) if base_bf1s else 0.0,
            "avg_sec_per_frame": round(float(np.mean(base_times)), 3) if base_times else 0.0,
        },
        "v4_segformer_shapely": {
            "mean_iou": round(float(np.mean(v4_ious)), 4) if v4_ious else 0.0,
            "mean_boundary_f1": round(float(np.mean(v4_bf1s)), 4) if v4_bf1s else 0.0,
            "invalid_polygons": v4_invalid,
            "avg_sec_per_frame": round(float(np.mean(v4_times)), 3) if v4_times else 0.0,
        },
        "per_camera": {
            cam: {k: round(float(np.mean(v)), 4) for k, v in vals.items()}
            for cam, vals in sorted(per_cam.items())
        },
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run_benchmark(), indent=2, ensure_ascii=False))
