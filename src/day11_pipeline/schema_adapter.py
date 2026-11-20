"""Unified schema adapter and deterministic geometry validators for Road v1.0."""
from __future__ import annotations

import math
from typing import Iterable

from road_lab.cvat_xml import Image, Shape, Tag
from road_lab.taxonomy import (
    FISHEYE_CAMERAS,
    SHAPE_LABELS,
    SIDE_CAMERAS,
    TAG_ATTRIBUTE,
    TAG_LABELS,
    expected_camera,
    image_slot,
)


def compute_edge_zone(x1: float, y1: float, x2: float, y2: float, width: int, height: int, radius_ratio: float = 0.8) -> bool:
    """Match road_check.py: center distance > 0.8 * width / 2."""
    cx, cy = width / 2.0, height / 2.0
    r = radius_ratio * width / 2.0
    bx, by = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    return math.hypot(bx - cx, by - cy) > r


def clip_point(x: float, y: float, width: int, height: int) -> tuple[float, float]:
    return (max(0.0, min(float(width - 1), x)), max(0.0, min(float(height - 1), y)))


def ensure_near_to_far(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Road v1.0: polylines must be drawn from near the vehicle (larger y) to far (smaller y)."""
    if len(points) >= 2 and points[0][1] < points[-1][1]:
        return list(reversed(points))
    return points


def polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def validate_image_schema(img: Image) -> list[str]:
    """Return list of schema/geometry violations for one CVAT Image."""
    errors: list[str] = []
    cam = img.tag_value("camera")
    exp_cam = expected_camera(img.name)
    if exp_cam and cam != exp_cam:
        errors.append(f"{img.name}: camera tag {cam!r} != expected {exp_cam!r}")

    for tag_name, allowed in TAG_LABELS.items():
        val = img.tag_value(tag_name, TAG_ATTRIBUTE)
        if val not in allowed:
            errors.append(f"{img.name}: tag {tag_name}={val!r} not in {allowed}")

    is_fisheye = cam in FISHEYE_CAMERAS
    is_side = cam in SIDE_CAMERAS

    for s in img.shapes:
        spec = SHAPE_LABELS.get(s.label)
        if not spec:
            errors.append(f"{img.name}: unknown label {s.label!r}")
            continue
        if s.kind != spec["type"]:
            errors.append(f"{img.name}: {s.label} kind={s.kind} != {spec['type']}")
        for attr, allowed in spec["select"].items():
            if s.attributes.get(attr) not in allowed:
                errors.append(f"{img.name}: {s.label}.{attr}={s.attributes.get(attr)!r} invalid")
        for attr in spec["checkbox"]:
            if s.attributes.get(attr) not in {"true", "false"}:
                errors.append(f"{img.name}: {s.label}.{attr}={s.attributes.get(attr)!r} invalid")

        if s.kind == "rectangle" and len(s.points) == 2:
            (x1, y1), (x2, y2) = s.points
            if abs(y2 - y1) < 8.0 or abs(x2 - x1) < 4.0:
                errors.append(f"{img.name}: {s.label} box too small ({abs(x2-x1):.1f}x{abs(y2-y1):.1f})")
        elif s.kind == "polyline":
            if len(s.points) < 2:
                errors.append(f"{img.name}: {s.label} polyline < 2 points")
            elif is_fisheye and len(s.points) < 4:
                errors.append(f"{img.name}: fisheye {s.label} has only {len(s.points)} points (<4)")
            if s.points[0][1] < s.points[-1][1] - 2.0:
                errors.append(f"{img.name}: {s.label} drawn far-to-near")
            if s.label == "lane" and is_side and s.attributes.get("position") != "other":
                errors.append(f"{img.name}: side camera lane position must be 'other'")
        elif s.kind == "polygon":
            if len(s.points) < 3 or polygon_area(s.points) < 50.0:
                errors.append(f"{img.name}: {s.label} polygon degenerate")

    return errors


def build_tags(camera: str, timeofday: str, weather: str, source: str = "real") -> list[Tag]:
    return [
        Tag("camera", {"value": camera}),
        Tag("timeofday", {"value": timeofday}),
        Tag("weather", {"value": weather}),
        Tag("source", {"value": source}),
    ]
