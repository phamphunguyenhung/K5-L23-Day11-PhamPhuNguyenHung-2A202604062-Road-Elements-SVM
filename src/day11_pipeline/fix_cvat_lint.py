"""Deterministic fixer for Job #59 and Job #60 CVAT annotations to resolve lint errors."""
from __future__ import annotations

import math
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import requests
from dotenv import dotenv_values
from cvat_sdk import make_client

from road_lab.taxonomy import FISHEYE_CAMERAS, SIDE_CAMERAS, expected_camera

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "out"


def _dedup_pts(pts: list[tuple[float, float]], min_dist: float = 1.5) -> list[tuple[float, float]]:
    if len(pts) <= 3:
        return pts
    out = [pts[0]]
    for p in pts[1:]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) >= min_dist:
            out.append(p)
    return out if len(out) >= 3 else pts


def _densify_to_4(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = list(pts)
    while len(out) < 4 and len(out) >= 2:
        # Split longest segment
        best_i = max(range(len(out) - 1), key=lambda i: math.hypot(out[i + 1][0] - out[i][0], out[i + 1][1] - out[i][1]))
        mx = (out[best_i][0] + out[best_i + 1][0]) * 0.5
        my = (out[best_i][1] + out[best_i + 1][1]) * 0.5
        out.insert(best_i + 1, (mx, my))
    return out


def fix_job(url: str, hdrs: dict, tid: int, jid: int) -> dict:
    meta = requests.get(f"{url}/api/tasks/{tid}/data/meta", headers=hdrs, timeout=10).json()
    frames = {i: f["name"] for i, f in enumerate(meta.get("frames", []))}
    labels_raw = requests.get(f"{url}/api/labels?task_id={tid}&page_size=50", headers=hdrs, timeout=10).json().get("results", [])
    id_to_label = {l["id"]: l["name"] for l in labels_raw}
    pos_spec_id = None
    for l in labels_raw:
        if l["name"] == "lane":
            for a in l.get("attributes", []):
                if a["name"] == "position":
                    pos_spec_id = a["id"]

    ann = requests.get(f"{url}/api/jobs/{jid}/annotations", headers=hdrs, timeout=15).json()
    shapes = ann.get("shapes", [])
    by_frame: dict[int, list[dict]] = defaultdict(list)
    for s in shapes:
        by_frame[s["frame"]].append(s)

    updated: list[dict] = []

    for fidx, fshapes in sorted(by_frame.items()):
        fname = frames.get(fidx, "")
        cam = expected_camera(fname) or "front"
        is_fish = cam in FISHEYE_CAMERAS
        is_side = cam in SIDE_CAMERAS
        w = meta["frames"][fidx].get("width", 1280)

        lanes_in_frame = []
        for s in fshapes:
            lbl = id_to_label.get(s["label_id"], "")
            pts = [(float(s["points"][i]), float(s["points"][i + 1])) for i in range(0, len(s["points"]), 2)]
            changed = False

            # 1. Polyline near-to-far & fisheye density >= 4
            if lbl in {"lane", "road_curb"} and len(pts) >= 2:
                if pts[0][1] < pts[-1][1] - 2.0:
                    pts = list(reversed(pts))
                    changed = True
                if is_fish and len(pts) < 4:
                    pts = _densify_pts = _densify_to_4(pts)
                    changed = True

            # 2. Polygon duplicate point cleanup
            if lbl in {"drivable", "crosswalk"} and len(pts) >= 4:
                dpts = _dedup_pts(pts)
                if len(dpts) != len(pts):
                    pts = dpts
                    changed = True

            if changed:
                s["points"] = [v for pt in pts for v in pt]
                s["_dirty"] = True

            if lbl == "lane":
                lanes_in_frame.append((s, pts))

        # 3. Assign lane position
        if lanes_in_frame and pos_spec_id is not None:
            if is_side:
                for s, _ in lanes_in_frame:
                    for a in s.get("attributes", []):
                        if a["spec_id"] == pos_spec_id and a["value"] != "other":
                            a["value"] = "other"
                            s["_dirty"] = True
            else:
                cx = w * 0.50
                # Sort by near-point x (pts[0][0])
                lefts = sorted([(s, pts[0][0]) for s, pts in lanes_in_frame if pts[0][0] < cx], key=lambda x: x[1], reverse=True)
                rights = sorted([(s, pts[0][0]) for s, pts in lanes_in_frame if pts[0][0] >= cx], key=lambda x: x[1])
                if not rights and len(lefts) >= 2:
                    # All on left of center -> rightmost becomes R1
                    rights = [lefts.pop(0)]
                elif not lefts and len(rights) >= 2:
                    lefts = [rights.pop(0)]

                assigns: list[tuple[dict, str]] = []
                for idx, (s, _) in enumerate(lefts):
                    assigns.append((s, "L1" if idx == 0 else ("L2" if idx == 1 else "other")))
                for idx, (s, _) in enumerate(rights):
                    assigns.append((s, "R1" if idx == 0 else ("R2" if idx == 1 else "other")))

                for s, new_pos in assigns:
                    found = False
                    for a in s.get("attributes", []):
                        if a["spec_id"] == pos_spec_id:
                            found = True
                            if a["value"] != new_pos:
                                a["value"] = new_pos
                                s["_dirty"] = True
                    if not found:
                        s.setdefault("attributes", []).append({"spec_id": pos_spec_id, "value": new_pos})
                        s["_dirty"] = True

    for s in shapes:
        if s.pop("_dirty", False):
            updated.append(s)

    if updated:
        r = requests.patch(
            f"{url}/api/jobs/{jid}/annotations?action=update",
            headers=hdrs,
            json={"shapes": updated, "tags": [], "tracks": []},
            timeout=20,
        )
        r.raise_for_status()

    return {"job_id": jid, "updated_shapes": len(updated)}


def main() -> int:
    vals = dotenv_values(ROOT / ".env")
    url = vals.get("CVAT_URL") or os.environ.get("CVAT_URL", "http://localhost:8080")
    tok = vals.get("CVAT") or vals.get("CVAT_PAT") or os.environ.get("CVAT_PAT", "")
    hdrs = {"Authorization": f"Bearer {tok}"}

    r59 = fix_job(url, hdrs, 60, 59)
    r60 = fix_job(url, hdrs, 61, 60)
    print("Fixed:", r59, r60)

    fz = OUT_DIR / "phamphunguyenhung-front.zip"
    bz = OUT_DIR / "phamphunguyenhung-fisheye.zip"
    for p in [fz, bz]:
        if p.exists():
            p.unlink()
    with make_client(host=url, access_token=tok) as c:
        c.tasks.retrieve(60).export_dataset("CVAT for images 1.1", filename=str(fz), include_images=False)
        c.tasks.retrieve(61).export_dataset("CVAT for images 1.1", filename=str(bz), include_images=False)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.run(
        [
            sys.executable, "-m", "road_lab.road_check", "lint",
            str(fz), str(bz),
            "--manifest", str(OUT_DIR / "phamphunguyenhung-manifest.json"),
            "--name", "phamphunguyenhung",
            "--revision", "1",
        ],
        cwd=str(ROOT), env=env, capture_output=True, text=True,
    )
    print("Lint exit=", proc.returncode)
    print(proc.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
