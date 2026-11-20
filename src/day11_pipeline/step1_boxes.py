"""Step 1: Inspect existing traffic_light/traffic_sign boxes and preview new yolo26l proposals (dry-run by default)."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import cv2
import requests
from dotenv import dotenv_values

from road_lab.taxonomy import expected_camera
from .module_a_objects import detect_objects
from .module_d_ignore import compute_ignore_mask

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
PREVIEW_DIR = ROOT / "out" / "step1_boxes_preview"


def _iou(b1: list[float], b2: list[float]) -> float:
    x1, y1 = max(b1[0], b2[0]), max(b1[1], b2[1])
    x2, y2 = min(b1[2], b2[2]), min(b1[3], b2[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    a1 = max(0.0, b1[2] - b1[0]) * max(0.0, b1[3] - b1[1])
    a2 = max(0.0, b2[2] - b2[0]) * max(0.0, b2[3] - b2[1])
    return inter / max(1e-6, a1 + a2 - inter)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sync", action="store_true")
    args = ap.parse_args()

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    vals = dotenv_values(ROOT / ".env")
    url = vals.get("CVAT_URL") or os.environ.get("CVAT_URL", "http://localhost:8080")
    tok = vals.get("CVAT") or vals.get("CVAT_PAT") or os.environ.get("CVAT_PAT", "")
    hdrs = {"Authorization": f"Bearer {tok}"}

    report = []
    for tid, jid, tname in [(60, 59, "front"), (61, 60, "fisheye")]:
        meta = requests.get(f"{url}/api/tasks/{tid}/data/meta", headers=hdrs, timeout=10).json()
        frames = {i: f["name"] for i, f in enumerate(meta.get("frames", []))}
        labels_raw = requests.get(f"{url}/api/labels?task_id={tid}&page_size=50", headers=hdrs, timeout=10).json().get("results", [])
        id_to_label = {l["id"]: l["name"] for l in labels_raw}
        label_map = {
            l["name"]: {"id": l["id"], "attrs": {a["name"]: a["id"] for a in l.get("attributes", [])}}
            for l in labels_raw
        }

        ann = requests.get(f"{url}/api/jobs/{jid}/annotations", headers=hdrs, timeout=15).json()
        by_frame: dict[int, list[dict]] = {}
        for s in ann.get("shapes", []):
            by_frame.setdefault(s["frame"], []).append(s)

        to_create = []
        existing_box_count = 0
        proposed_items = []

        for fidx, fname in sorted(frames.items()):
            bgr = cv2.imread(str(DATA_DIR / fname))
            if bgr is None:
                continue
            cam = expected_camera(fname) or "front"
            ignore = compute_ignore_mask(bgr, cam)
            cur = by_frame.get(fidx, [])
            cur_boxes = [
                (id_to_label.get(s["label_id"], ""), s["points"])
                for s in cur
                if s["type"] == "rectangle" and len(s["points"]) == 4
            ]
            existing_box_count += len(cur_boxes)

            objs, _ = detect_objects(bgr, cam, ignore, conf_thresh=0.25)
            new_objs = []
            for s in objs:
                b = [s.points[0][0], s.points[0][1], s.points[1][0], s.points[1][1]]
                if not any(_iou(b, cb) > 0.3 for _, cb in cur_boxes):
                    new_objs.append(s)
                    linfo = label_map[s.label]
                    to_create.append({
                        "type": "rectangle",
                        "frame": fidx,
                        "label_id": linfo["id"],
                        "points": [float(v) for pt in s.points for v in pt],
                        "occluded": False,
                        "z_order": 0,
                        "group": 0,
                        "source": "manual",
                        "attributes": [{"spec_id": linfo["attrs"][k], "value": str(v)} for k, v in s.attributes.items() if k in linfo["attrs"]],
                    })
                    proposed_items.append({
                        "file": fname,
                        "label": s.label,
                        "box_h_px": round(b[3] - b[1], 1),
                        "attrs": s.attributes,
                    })

            if cur_boxes or new_objs:
                vis = bgr.copy()
                for lbl, cb in cur_boxes:
                    cv2.rectangle(vis, (int(cb[0]), int(cb[1])), (int(cb[2]), int(cb[3])), (255, 180, 0), 2)
                    cv2.putText(vis, f"EX:{lbl}", (int(cb[0]), max(14, int(cb[1]) - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 180, 0), 1)
                for s in new_objs:
                    (x1, y1), (x2, y2) = s.points
                    cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), (0, 220, 0), 2)
                    txt = s.attributes.get("color", s.attributes.get("group", ""))
                    ez = " EZ" if s.attributes.get("edge_zone") == "true" else ""
                    cv2.putText(vis, f"NEW:{s.label}({txt}{ez})", (int(x1), max(14, int(y1) - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 0), 1)
                cv2.imwrite(str(PREVIEW_DIR / f"{fname}.jpg"), vis)

        synced = False
        if args.sync and to_create:
            r = requests.patch(f"{url}/api/jobs/{jid}/annotations?action=create", headers=hdrs, json={"shapes": to_create, "tags": [], "tracks": []}, timeout=20)
            r.raise_for_status()
            synced = True

        report.append({
            "job_id": jid,
            "task": tname,
            "existing_boxes": existing_box_count,
            "new_proposed_boxes": len(to_create),
            "synced": synced,
            "proposals": proposed_items,
        })

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
