"""Non-destructive merge-fill: learn from user's manual annotations and fill missing shapes on CVAT Tasks #60/#61."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import requests
from dotenv import dotenv_values
from cvat_sdk import make_client

from road_lab.taxonomy import FISHEYE_CAMERAS, SIDE_CAMERAS, expected_camera
from .module_a_objects import detect_objects
from .module_b_freespace import detect_freespace_and_crosswalk
from .module_c_lines import detect_lanes_and_curbs
from .module_d_ignore import compute_ignore_mask

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "out"


def _iou(b1, b2) -> float:
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    a1 = max(0.0, b1[2] - b1[0]) * max(0.0, b1[3] - b1[1])
    a2 = max(0.0, b2[2] - b2[0]) * max(0.0, b2[3] - b2[1])
    return inter / max(1e-6, a1 + a2 - inter)


def _shape_to_cvat_json(s, frame_idx: int, label_map: dict[str, dict]) -> dict:
    linfo = label_map[s.label]
    pts = [float(v) for pt in s.points for v in pt]
    attrs = [
        {"spec_id": linfo["attrs"][k], "value": str(v)}
        for k, v in s.attributes.items()
        if k in linfo["attrs"]
    ]
    return {
        "type": s.kind,
        "frame": frame_idx,
        "label_id": linfo["id"],
        "points": pts,
        "occluded": s.occluded,
        "z_order": 0,
        "group": 0,
        "source": "manual",
        "attributes": attrs,
    }


def merge_fill_task(url: str, hdrs: dict, tid: int) -> dict:
    meta = requests.get(f"{url}/api/tasks/{tid}/data/meta", headers=hdrs, timeout=10).json()
    frames = {i: f["name"] for i, f in enumerate(meta.get("frames", []))}
    labels_raw = requests.get(f"{url}/api/labels?task_id={tid}&page_size=50", headers=hdrs, timeout=10).json().get("results", [])
    label_id_to_name = {l["id"]: l["name"] for l in labels_raw}
    label_map = {
        l["name"]: {"id": l["id"], "attrs": {a["name"]: a["id"] for a in l.get("attributes", [])}}
        for l in labels_raw
    }

    ann = requests.get(f"{url}/api/tasks/{tid}/annotations", headers=hdrs, timeout=15).json()
    existing = ann.get("shapes", [])
    by_frame: dict[int, list[dict]] = {}
    for s in existing:
        by_frame.setdefault(s["frame"], []).append(s)

    to_create: list[dict] = []
    for fidx, fname in sorted(frames.items()):
        img_path = DATA_DIR / fname
        bgr = cv2.imread(str(img_path))
        if bgr is None:
            continue
        cam = expected_camera(fname) or "front"
        ignore_mask = compute_ignore_mask(bgr, cam)
        cur_shapes = by_frame.get(fidx, [])
        cur_labels = {label_id_to_name.get(s["label_id"], "") for s in cur_shapes}
        cur_boxes = [s["points"] for s in cur_shapes if s["type"] == "rectangle" and len(s["points"]) == 4]

        # 1. Fill missing drivable
        if "drivable" not in cur_labels:
            fs = detect_freespace_and_crosswalk(bgr, cam, ignore_mask)
            for s in fs:
                if s.label == "drivable":
                    to_create.append(_shape_to_cvat_json(s, fidx, label_map))

        # 2. Fill missing lane
        if "lane" not in cur_labels:
            lanes = detect_lanes_and_curbs(bgr, cam, ignore_mask)
            for s in lanes:
                to_create.append(_shape_to_cvat_json(s, fidx, label_map))

        # 3. Fill missing traffic_light / traffic_sign (non-overlapping)
        objs, _ = detect_objects(bgr, cam, ignore_mask)
        for s in objs:
            b = [s.points[0][0], s.points[0][1], s.points[1][0], s.points[1][1]]
            if not any(_iou(b, cb) > 0.3 for cb in cur_boxes):
                to_create.append(_shape_to_cvat_json(s, fidx, label_map))
                cur_boxes.append(b)

    if to_create:
        r = requests.patch(
            f"{url}/api/tasks/{tid}/annotations?action=create",
            headers=hdrs,
            json={"shapes": to_create, "tags": [], "tracks": []},
            timeout=20,
        )
        r.raise_for_status()

    return {"task_id": tid, "existing_shapes": len(existing), "added_shapes": len(to_create)}


def main() -> int:
    vals = dotenv_values(ROOT / ".env")
    url = vals.get("CVAT_URL") or os.environ.get("CVAT_URL", "http://localhost:8080")
    tok = vals.get("CVAT") or vals.get("CVAT_PAT") or os.environ.get("CVAT_PAT", "")
    hdrs = {"Authorization": f"Bearer {tok}"}

    res = []
    for tid in [60, 61]:
        res.append(merge_fill_task(url, hdrs, tid))

    # Export readback and run lint
    with make_client(host=url, access_token=tok) as client:
        for tid, out_name in [(60, "readback-front.zip"), (61, "readback-fisheye.zip")]:
            out_p = OUT_DIR / out_name
            if out_p.exists():
                out_p.unlink()
            client.tasks.retrieve(tid).export_dataset("CVAT for images 1.1", filename=str(out_p), include_images=False)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    lint = subprocess.run(
        [sys.executable, "-m", "road_lab.road_check", "lint", str(OUT_DIR / "readback-front.zip"), str(OUT_DIR / "readback-fisheye.zip")],
        cwd=str(ROOT), env=env, capture_output=True, text=True,
    )
    print(json.dumps({"merge_results": res, "lint_exit_code": lint.returncode, "lint_tail": lint.stdout.splitlines()[-3:]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
