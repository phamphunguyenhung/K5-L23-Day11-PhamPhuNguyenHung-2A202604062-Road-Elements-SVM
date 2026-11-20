"""Day 11 Human-Guided CVAT Autolabel Factory V4 — unified reproducible entrypoint."""
from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2
import requests
from dotenv import dotenv_values
from cvat_sdk import make_client

from road_lab.cvat_xml import Image, Shape, load as load_cvat
from road_lab.taxonomy import FISHEYE_CAMERAS, SIDE_CAMERAS, expected_camera
from .module_a_objects import detect_objects
from .module_c_lines import detect_lanes_and_curbs
from .module_d_ignore import compute_ignore_mask
from .overlay import render_overlay
from .schema_adapter import build_tags
from .v4_segformer import mask_to_shapely_polygons, predict_road_mask

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "out"
V4_OVERLAY_DIR = OUT_DIR / "v4_overlays"
QA_DIR = OUT_DIR / "qa"
ARTIFACTS_DIR = ROOT / "artifacts" / "day11"


def _shape_to_cvat_json(s: Shape, frame_idx: int, label_map: dict[str, dict]) -> dict:
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


def run_v4(sync: bool = False) -> dict:
    t0 = time.perf_counter()
    V4_OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    vals = dotenv_values(ROOT / ".env")
    url = vals.get("CVAT_URL") or os.environ.get("CVAT_URL", "http://localhost:8080")
    tok = vals.get("CVAT") or vals.get("CVAT_PAT") or os.environ.get("CVAT_PAT", "")
    hdrs = {"Authorization": f"Bearer {tok}"}

    proposals_summary: list[dict] = []
    sync_results: list[dict] = []

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
        existing_shapes = ann.get("shapes", [])
        by_frame: dict[int, list[dict]] = {}
        for s in existing_shapes:
            by_frame.setdefault(s["frame"], []).append(s)

        to_create: list[dict] = []
        for fidx, fname in sorted(frames.items()):
            bgr = cv2.imread(str(DATA_DIR / fname))
            if bgr is None:
                continue
            h, w = bgr.shape[:2]
            cam = expected_camera(fname) or "front"
            is_fish = cam in FISHEYE_CAMERAS
            ignore = compute_ignore_mask(bgr, cam)
            cur = by_frame.get(fidx, [])
            cur_labels = {id_to_label.get(s["label_id"], "") for s in cur}

            added_here: list[Shape] = []
            # Safe additive proposal: only propose missing drivable (via SegFormer + Shapely)
            if "drivable" not in cur_labels:
                rmask = predict_road_mask(bgr, ignore)
                fs = mask_to_shapely_polygons(rmask, w, h, is_fish)
                for s in fs:
                    to_create.append(_shape_to_cvat_json(s, fidx, label_map))
                    added_here.append(s)

            # On completely empty frame (e.g. A05), also propose road-masked lanes
            if not cur:
                rmask = predict_road_mask(bgr, ignore)
                road_ignore = ignore | (~rmask)
                lanes = detect_lanes_and_curbs(bgr, cam, road_ignore)
                for s in lanes:
                    to_create.append(_shape_to_cvat_json(s, fidx, label_map))
                    added_here.append(s)

            if added_here:
                ov_path = V4_OVERLAY_DIR / f"{fname}.jpg"
                cv_img = Image(name=fname, width=w, height=h, shapes=added_here, tags=build_tags(cam, "day", "clear"))
                render_overlay(DATA_DIR / fname, cv_img, ov_path)
                proposals_summary.append({
                    "job": jid,
                    "frame": fidx,
                    "file": fname,
                    "camera": cam,
                    "added": dict(Counter(s.label for s in added_here)),
                    "overlay": f"../v4_overlays/{ov_path.name}",
                })

        if sync and to_create:
            r = requests.patch(
                f"{url}/api/jobs/{jid}/annotations?action=create",
                headers=hdrs,
                json={"shapes": to_create, "tags": [], "tracks": []},
                timeout=20,
            )
            r.raise_for_status()
            after = requests.get(f"{url}/api/jobs/{jid}/annotations", headers=hdrs, timeout=15).json()
            sync_results.append({
                "job_id": jid,
                "before_shapes": len(existing_shapes),
                "added_shapes": len(to_create),
                "after_shapes": len(after.get("shapes", [])),
                "readback_match": len(after.get("shapes", [])) == len(existing_shapes) + len(to_create),
            })
        else:
            sync_results.append({
                "job_id": jid,
                "mode": "dry-run" if not sync else "no-op",
                "before_shapes": len(existing_shapes),
                "proposed_shapes": len(to_create),
            })

    bench_path = ARTIFACTS_DIR / "benchmark_v4.json"
    bench = json.loads(bench_path.read_text(encoding="utf-8")) if bench_path.exists() else {}
    diff_path = ARTIFACTS_DIR / "reference" / "difficult_cases.jsonl"
    difficult = [json.loads(l) for l in diff_path.read_text(encoding="utf-8").splitlines() if l.strip()] if diff_path.exists() else []

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_sec": round(time.perf_counter() - t0, 2),
        "sync": sync,
        "sync_results": sync_results,
        "proposals": proposals_summary,
        "benchmark": bench,
        "top5_review_cases": difficult[:5],
    }
    (QA_DIR / "v4_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_review_html(report, QA_DIR / "v4_review.html")
    return report


def _write_review_html(rep: dict, out_path: Path) -> None:
    b = rep.get("benchmark", {})
    base = b.get("baseline_hsv", {})
    v4 = b.get("v4_segformer_shapely", {})
    sync_rows = "".join(
        f"<tr><td>Job #{r['job_id']}</td><td>{r['before_shapes']}</td>"
        f"<td>{r.get('added_shapes', r.get('proposed_shapes', 0))}</td>"
        f"<td>{r.get('after_shapes', r['before_shapes'])}</td>"
        f"<td>{'PASS' if r.get('readback_match', True) else 'FAIL'}</td></tr>"
        for r in rep["sync_results"]
    )
    prop_cards = "".join(
        f"<div class='card'><img src='{html.escape(p['overlay'])}' alt='{html.escape(p['file'])}'/>"
        f"<div class='meta'><strong>{html.escape(p['file'])}</strong> ({html.escape(p['camera'])})<br/>"
        f"Added: {html.escape(str(p['added']))}</div></div>"
        for p in rep["proposals"][:6]
    )
    top5 = "".join(
        f"<tr><td>{html.escape(str(d['job']))}</td><td>{html.escape(d['file'])}</td><td>{html.escape(d['camera'])}</td><td>{html.escape(d['reason'])}</td></tr>"
        for d in rep["top5_review_cases"]
    )
    doc = f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><title>Day 11 V4 Human-Guided Factory Review</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;background:#f8fafc;color:#0f172a;margin:0;padding:24px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:20px}}
.kpi{{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:14px}}
.kpi .v{{font-size:22px;font-weight:700}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e2e8f0;margin-bottom:20px}}
th,td{{padding:8px 10px;border-bottom:1px solid #e2e8f0;text-align:left;font-size:14px}} th{{background:#f1f5f9}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}}
.card{{background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden}}
.card img{{width:100%;height:auto;display:block}} .card .meta{{padding:10px;font-size:13px}}
</style></head><body>
<h1>Day 11 — Human-Guided CVAT Autolabel Factory V4</h1>
<p>Generated: {html.escape(rep['generated_at_utc'])} · Elapsed: {rep['elapsed_sec']}s · Mode: {'LIVE SYNC' if rep['sync'] else 'DRY RUN'}</p>
<div class="grid">
  <div class="kpi"><div>Baseline HSV IoU</div><div class="v">{base.get('mean_iou', 0):.4f}</div></div>
  <div class="kpi"><div>V4 SegFormer+Shapely IoU</div><div class="v">{v4.get('mean_iou', 0):.4f}</div></div>
  <div class="kpi"><div>Boundary F1 (HSV → V4)</div><div class="v">{base.get('mean_boundary_f1', 0):.4f} → {v4.get('mean_boundary_f1', 0):.4f}</div></div>
  <div class="kpi"><div>Invalid Polygons (V4)</div><div class="v">{v4.get('invalid_polygons', 0)}</div></div>
</div>
<h2>Safe CVAT Sync Status</h2>
<table><thead><tr><th>Job</th><th>Before</th><th>Added/Proposed</th><th>After</th><th>Readback</th></tr></thead><tbody>{sync_rows}</tbody></table>
<h2>Top 5 Priority Review Cases</h2>
<table><thead><tr><th>Job</th><th>File</th><th>Camera</th><th>Reason</th></tr></thead><tbody>{top5}</tbody></table>
<h2>V4 Drivable Proposals Preview</h2>
<div class="cards">{prop_cards}</div>
</body></html>"""
    out_path.write_text(doc, encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sync", action="store_true")
    args = ap.parse_args()
    out = run_v4(sync=args.sync)
    print(json.dumps({"sync_results": out["sync_results"], "proposals_count": len(out["proposals"]), "elapsed_sec": out["elapsed_sec"]}, indent=2))
