"""Module D: Ignore-region mask (ego vehicle + lens border) & ODD tagger (camera/timeofday/weather/source)."""
from __future__ import annotations

import cv2
import numpy as np

from road_lab.taxonomy import FISHEYE_CAMERAS, expected_camera


def compute_ignore_mask(img_bgr: np.ndarray, camera: str) -> np.ndarray:
    """Return boolean mask (H, W) where True = ignore region (lens vignette + ego body)."""
    h, w = img_bgr.shape[:2]
    mask = np.zeros((h, w), dtype=bool)
    if camera not in FISHEYE_CAMERAS:
        return mask

    # 1. Lens border / black vignette corners
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    mask |= gray < 8

    # 2. Ego-vehicle body occlusion near bottom of WoodScape fisheye cameras
    yy, xx = np.mgrid[0:h, 0:w]
    nx = (xx - w * 0.5) / (w * 0.5)
    if camera in {"fisheye_front", "fisheye_rear"}:
        # Bottom bumper / hood arc in central region
        ego_y = h * (0.72 + 0.14 * (nx ** 2))
        mask |= yy >= ego_y
    else:
        # Side mirrors / doors occupy bottom ~25% in MVL / MVR
        ego_y = h * (0.74 + 0.12 * (nx ** 2))
        mask |= yy >= ego_y

    return mask


def classify_odd_tags(img_bgr: np.ndarray, filename: str) -> dict[str, str]:
    """Classify camera, timeofday, weather, source deterministically from filename & image stats."""
    cam = expected_camera(filename) or "front"
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h, w = img_bgr.shape[:2]
    upper = hsv[: int(h * 0.45), :, :]
    road = hsv[int(h * 0.55) : int(h * 0.90), :, :]

    mean_v = float(np.mean(hsv[:, :, 2]))
    upper_v = float(np.mean(upper[:, :, 2]))
    upper_s = float(np.mean(upper[:, :, 1]))
    contrast = float(np.std(hsv[:, :, 2]))

    if mean_v < 65 or upper_v < 55:
        timeofday = "night"
    elif mean_v < 100 and upper_v < 110:
        timeofday = "dusk"
    else:
        timeofday = "day"

    # Weather heuristic: low saturation + low contrast -> overcast/fog; high road specular -> rain
    road_glare = float(np.mean((road[:, :, 2] > 210) & (road[:, :, 1] < 35)))
    if contrast < 32 and upper_v > 120 and upper_s < 28:
        weather = "fog"
    elif road_glare > 0.12 and timeofday != "night":
        weather = "rain"
    elif upper_s < 45 and upper_v < 175 and timeofday == "day":
        weather = "overcast"
    else:
        weather = "clear"

    return {
        "camera": cam,
        "timeofday": timeofday,
        "weather": weather,
        "source": "real",
    }
