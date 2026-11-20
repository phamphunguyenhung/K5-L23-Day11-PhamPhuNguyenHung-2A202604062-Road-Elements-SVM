"""Step 1b: Zero-shot Grounding-DINO traffic_sign detector for Job #59 (front) with dry-run & visual preview."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import cv2
import requests
import torch
from dotenv import dotenv_values
from PIL import Image as PILImage
from transformers import pipeline

from road_lab.taxonomy import expected_camera
from .module_a_objects import _classify_sign_group

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
PREVIEW_DIR = ROOT / "out" / "step1b_signs_preview"


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
    ap.add_argument("--thresh", type=float, default=0.26)
    args = ap.parse_args()

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    vals = dotenv_values(ROOT / ".env")
    url = vals.get("CVAT_URL") or os.environ.get("CVAT_URL", "http://localhost:8080")
    tok = vals.get("CVAT") or vals.get("CVAT_PAT") or os.environ.get("CVAT_PAT", "")
    hdrs = {"Authorization": f"Bearer {tok}"}

    tid, jid = 60, 59
    meta = requests.get(f"{url}/api/tasks/{tid}/data/meta", headers=hdrs, timeout=10).json()
    frames = {i: f["name"] for i, f in enumerate(meta.get("frames", []))}
    labels_raw = requests.get(f"{url}/api/labels?task_id={tid}&page_size=50", headers=hdrs, timeout=10).json().get("results", [])
    linfo = next(
        {"id": l["id"], "attrs": {a["name"]: a["id"] for a in l.get("attributes", [])}}
        for l in labels_raw if l["name"] == "traffic_sign"
    )

    ann = requests.get(f"{url}/api/jobs/{jid}/annotations", headers=hdrs, timeout=15).json()
    by_frame: dict[int, list[dict]] = {}
    for s in ann.get("shapes", []):
        by_frame.setdefault(s["frame"], []).append(s)

    dev = 0 if torch.cuda.is_available() else -1
    det = pipeline("zero-shot-object-detection", model="IDEA-Research/grounding-dino-tiny", device=dev)

    to_create = []
    proposals = []
    for fidx, fname in sorted(frames.items()):
        img_path = DATA_DIR / fname
        bgr = cv2.imread(str(img_path))
        if bgr is None:
            continue
        h, w = bgr.shape[:2]
        cur_boxes = [s["points"] for s in by_frame.get(fidx, []) if s["type"] == "rectangle" and len(s["points"]) == 4]

        pil = PILImage.open(img_path).convert("RGB")
        preds = det(pil, candidate_labels=["traffic sign."], threshold=args.thresh)

        vis = bgr.copy()
        for cb in cur_boxes:
            cv2.rectangle(vis, (int(cb[0]), int(cb[1])), (int(cb[2]), int(cb[3])), (255, 180, 0), 2)

        added_here = 0
        for r in preds:
            bx = r["box"]
            x1, y1, x2, y2 = float(max(0, bx["xmin"])), float(max(0, bx["ymin"])), float(min(w - 1, bx["xmax"])), float(min(h - 1, bx["ymax"]))
            bw, bh = x2 - x1, y2 - y1
            # Reject < 8 px height, oversized false boxes (> 22% image), or overlaps with existing boxes
            if bh < 8.0 or bw < 6.0 or bw > w * 0.25 or bh > h * 0.30:
                continue
            b = [x1, y1, x2, y2]
            if any(_iou(b, cb) > 0.25 for cb in cur_boxes):
                continue

            crop = bgr[int(y1) : int(y2) + 1, int(x1) : int(x2) + 1]
            grp = _classify_sign_group(crop)
            attrs = {"group": grp, "facing": "front", "edge_zone": "false"}
            to_create.append({
                "type": "rectangle",
                "frame": fidx,
                "label_id": linfo["id"],
                "points": [x1, y1, x2, y2],
                "occluded": False,
                "z_order": 0,
                "group": 0,
                "source": "manual",
                "attributes": [{"spec_id": linfo["attrs"][k], "value": v} for k, v in attrs.items()],
            })
            cur_boxes.append(b)
            added_here += 1
            proposals.append({"file": fname, "score": round(float(r["score"]), 3), "h_px": round(bh, 1), "group": grp})
            cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), (0, 220, 0), 2)
            cv2.putText(vis, f"{grp} {r['score']:.2f}", (int(x1), max(14, int(y1) - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 220, 0), 1)

        if added_here:
            cv2.imwrite(str(PREVIEW_DIR / f"{fname}.jpg"), vis)

    if args.sync and to_create:
        r = requests.patch(f"{url}/api/jobs/{jid}/annotations?action=create", headers=hdrs, json={"shapes": to_create, "tags": [], "tracks": []}, timeout=20)
        r.raise_for_status()

    print(json.dumps({"job_id": jid, "synced": args.sync, "new_traffic_signs": len(to_create), "proposals": proposals}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
