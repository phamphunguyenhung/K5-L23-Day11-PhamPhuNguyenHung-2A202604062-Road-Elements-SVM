"""Module C: Lane & Curb polyline detector (near-to-far, fisheye arc sampling, L1/R1 & side-camera rules)."""
from __future__ import annotations

import cv2
import numpy as np

from road_lab.cvat_xml import Shape
from road_lab.taxonomy import FISHEYE_CAMERAS, SIDE_CAMERAS
from .schema_adapter import ensure_near_to_far


def _paint_mask(img_bgr: np.ndarray, ignore_mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    white = (gray > 165) & (hsv[:, :, 1] < 60) & (~ignore_mask)
    yellow = (hsv[:, :, 0] >= 14) & (hsv[:, :, 0] <= 36) & (hsv[:, :, 1] > 65) & (hsv[:, :, 2] > 110) & (~ignore_mask)
    return white, yellow


def _track_lane_side(
    paint: np.ndarray,
    yellow: np.ndarray,
    y_rows: list[int],
    x_min: int,
    x_max: int,
    default_x_fn,
) -> tuple[list[tuple[float, float]], str, str]:
    pts: list[tuple[float, float]] = []
    paint_hits = 0
    yellow_hits = 0
    prev_x = None

    for y in y_rows:
        y0, y1 = max(0, y - 4), min(paint.shape[0], y + 5)
        band = np.any(paint[y0:y1, x_min:x_max], axis=0)
        xs = np.where(band)[0] + x_min
        if len(xs) > 0:
            if prev_x is not None:
                near_xs = xs[np.abs(xs - prev_x) < 70]
                if len(near_xs) > 0:
                    xs = near_xs
            cx = float(np.median(xs))
            prev_x = cx
            pts.append((cx, float(y)))
            paint_hits += 1
            if np.any(yellow[y0:y1, max(0, int(cx) - 8) : min(paint.shape[1], int(cx) + 9)]):
                yellow_hits += 1
        else:
            cx = default_x_fn(y) if prev_x is None else prev_x
            pts.append((float(cx), float(y)))

    pts = ensure_near_to_far(pts)
    style = "dashed" if 1 <= paint_hits < max(2, len(y_rows) * 0.65) else "solid"
    color = "yellow" if yellow_hits >= max(1, paint_hits // 2) and yellow_hits > 0 else "white"
    return pts, style, color


def detect_lanes_and_curbs(
    img_bgr: np.ndarray,
    camera: str,
    ignore_mask: np.ndarray,
) -> list[Shape]:
    """Detect L1/R1 (or position=other on side fisheye) polylines drawn near-to-far."""
    h, w = img_bgr.shape[:2]
    is_fisheye = camera in FISHEYE_CAMERAS
    is_side = camera in SIDE_CAMERAS

    white, yellow = _paint_mask(img_bgr, ignore_mask)
    paint = white | yellow

    y_bot = int(h * (0.70 if is_fisheye else 0.94))
    y_top = int(h * (0.50 if is_fisheye else 0.59))
    n_pts = 8 if is_fisheye else 6
    y_rows = [int(y) for y in np.linspace(y_bot, y_top, n_pts)]

    shapes: list[Shape] = []
    if is_side:
        # Side cameras: horizontal/curved boundary lines, position MUST be 'other'
        pts, style, color = _track_lane_side(
            paint, yellow, y_rows, int(w * 0.15), int(w * 0.85),
            lambda y: w * 0.50,
        )
        shapes.append(
            Shape(
                label="lane",
                kind="polyline",
                points=pts,
                attributes={"position": "other", "style": style, "color": color, "kind": "single"},
            )
        )
        return shapes

    # Front / Fisheye-Front / Fisheye-Rear: L1 (left) and R1 (right)
    l_pts, l_style, l_color = _track_lane_side(
        paint, yellow, y_rows, int(w * 0.10), int(w * 0.49),
        lambda y: w * (0.42 - 0.22 * (y - y_top) / max(1, y_bot - y_top)),
    )
    r_pts, r_style, r_color = _track_lane_side(
        paint, yellow, y_rows, int(w * 0.51), int(w * 0.90),
        lambda y: w * (0.58 + 0.22 * (y - y_top) / max(1, y_bot - y_top)),
    )

    shapes.append(
        Shape(
            label="lane",
            kind="polyline",
            points=l_pts,
            attributes={"position": "L1", "style": l_style, "color": l_color, "kind": "single"},
        )
    )
    shapes.append(
        Shape(
            label="lane",
            kind="polyline",
            points=r_pts,
            attributes={"position": "R1", "style": r_style, "color": r_color, "kind": "single"},
        )
    )
    return shapes
