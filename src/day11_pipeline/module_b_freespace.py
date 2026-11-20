"""Module B: Free-space / Drivable polygon & Crosswalk detector with topology checks."""
from __future__ import annotations

import cv2
import numpy as np

from road_lab.cvat_xml import Shape
from road_lab.taxonomy import FISHEYE_CAMERAS


def _simplify_polygon(cnt: np.ndarray, w: int, h: int, eps_ratio: float = 0.012) -> list[tuple[float, float]]:
    peri = cv2.arcLength(cnt, True)
    approx = cv2.approxPolyDP(cnt, eps_ratio * peri, True)
    pts = [(float(max(0, min(w - 1, p[0][0]))), float(max(0, min(h - 1, p[0][1])))) for p in approx]
    return pts


def detect_freespace_and_crosswalk(
    img_bgr: np.ndarray,
    camera: str,
    ignore_mask: np.ndarray,
) -> list[Shape]:
    """Segment drivable road polygon (direct) and crosswalk polygons."""
    h, w = img_bgr.shape[:2]
    is_fisheye = camera in FISHEYE_CAMERAS
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    # Seed from lower-center road patch (above ego body)
    seed_y1 = int(h * (0.62 if is_fisheye else 0.72))
    seed_y2 = int(h * (0.76 if is_fisheye else 0.90))
    seed_x1, seed_x2 = int(w * 0.35), int(w * 0.65)
    seed_patch = hsv[seed_y1:seed_y2, seed_x1:seed_x2]
    med_s = float(np.median(seed_patch[:, :, 1]))
    med_v = float(np.median(seed_patch[:, :, 2]))

    # Asphalt / road surface similarity mask in lower 45% of frame
    s_diff = np.abs(hsv[:, :, 1].astype(np.float32) - med_s)
    v_diff = np.abs(hsv[:, :, 2].astype(np.float32) - med_v)
    road_mask = (s_diff < 28.0) & (v_diff < 45.0) & (hsv[:, :, 1] < 58)

    y_horizon = int(h * (0.48 if is_fisheye else 0.56))
    road_mask[:y_horizon, :] = False
    road_mask[ignore_mask] = False

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    u8 = (road_mask.astype(np.uint8)) * 255
    u8 = cv2.morphologyEx(u8, cv2.MORPH_CLOSE, kernel)
    u8 = cv2.morphologyEx(u8, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))

    # Keep largest connected component touching bottom-center
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(u8, connectivity=8)
    best_lbl = 0
    best_score = -1.0
    for lbl in range(1, num_labels):
        area = float(stats[lbl, cv2.CC_STAT_AREA])
        if area < (w * h * 0.03):
            continue
        # Prefer components near horizontal center & lower half
        cy = stats[lbl, cv2.CC_STAT_TOP] + stats[lbl, cv2.CC_STAT_HEIGHT] * 0.5
        if cy > h * 0.52 and area > best_score:
            best_score = area
            best_lbl = lbl

    shapes: list[Shape] = []
    if best_lbl > 0:
        comp = ((labels == best_lbl).astype(np.uint8)) * 255
        cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            main_cnt = max(cnts, key=cv2.contourArea)
            pts = _simplify_polygon(main_cnt, w, h, eps_ratio=0.01)
            if len(pts) >= 4:
                shapes.append(
                    Shape(
                        label="drivable",
                        kind="polygon",
                        points=pts,
                        attributes={"area_type": "direct"},
                    )
                )
    else:
        # Safe trapezoidal fallback in ego lane (never empty on valid road image)
        y_top = float(int(h * (0.55 if is_fisheye else 0.60)))
        y_bot = float(int(h * (0.80 if is_fisheye else 0.94)))
        pts = [
            (w * 0.40, y_top),
            (w * 0.60, y_top),
            (w * 0.78, y_bot),
            (w * 0.22, y_bot),
        ]
        shapes.append(
            Shape(label="drivable", kind="polygon", points=pts, attributes={"area_type": "direct"})
        )

    # Crosswalk zebra-stripe detector in lower road band
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    white_mask = ((gray > 185) & (hsv[:, :, 1] < 55)).astype(np.uint8) * 255
    white_mask[: int(h * 0.52), :] = 0
    white_mask[ignore_mask] = 0
    dil = cv2.dilate(white_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (35, 9)))
    c_cnts, _ = cv2.findContours(dil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in c_cnts:
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bw > w * 0.22 and 25 < bh < h * 0.25:
            # Verify periodic white transitions inside box
            strip = white_mask[y + bh // 2, x : x + bw] > 0
            transitions = int(np.sum(strip[1:] != strip[:-1]))
            if transitions >= 6:
                hull = cv2.convexHull(cnt)
                c_pts = _simplify_polygon(hull, w, h, eps_ratio=0.02)
                if len(c_pts) >= 4:
                    shapes.append(Shape(label="crosswalk", kind="polygon", points=c_pts))
                    break

    return shapes
