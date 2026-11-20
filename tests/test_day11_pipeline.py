"""Unit tests for Day 11 pipeline schema adapter and ignore/ODD helpers."""
from __future__ import annotations

import numpy as np

from day11_pipeline.module_d_ignore import classify_odd_tags, compute_ignore_mask
from day11_pipeline.schema_adapter import (
    build_tags,
    compute_edge_zone,
    ensure_near_to_far,
    validate_image_schema,
)
from road_lab.cvat_xml import Image, Shape


def test_edge_zone_matches_road_check_radius():
    # 1280x966 -> r = 0.8 * 1280 / 2 = 512
    assert not compute_edge_zone(620, 460, 660, 500, 1280, 966)
    assert compute_edge_zone(20, 460, 60, 500, 1280, 966)


def test_ensure_near_to_far_reverses_far_to_near():
    pts = [(600.0, 400.0), (620.0, 650.0)]
    fixed = ensure_near_to_far(pts)
    assert fixed[0][1] > fixed[-1][1]


def test_validate_image_schema_valid_and_invalid():
    img = Image(
        name="B05_05780_MVL.png",
        width=1280,
        height=966,
        shapes=[
            Shape(
                label="lane",
                kind="polyline",
                points=[(100, 700), (200, 650), (300, 600), (400, 560)],
                attributes={"position": "other", "style": "solid", "color": "white", "kind": "single"},
            )
        ],
        tags=build_tags("fisheye_left", "day", "clear", "real"),
    )
    assert validate_image_schema(img) == []

    bad = img.copy()
    bad.shapes[0].attributes["position"] = "L1"
    assert any("side camera" in e for e in validate_image_schema(bad))


def test_ignore_mask_and_odd_tags():
    dummy = np.full((966, 1280, 3), 120, dtype=np.uint8)
    mask = compute_ignore_mask(dummy, "fisheye_left")
    assert mask[950, 640]
    odd = classify_odd_tags(dummy, "B05_05780_MVL.png")
    assert odd["camera"] == "fisheye_left"
    assert odd["source"] == "real"
