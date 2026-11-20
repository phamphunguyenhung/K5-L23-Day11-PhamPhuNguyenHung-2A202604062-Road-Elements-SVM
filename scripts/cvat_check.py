"""Unified CLI tool for Day 11 CVAT inspection, lint/manifest export, auto-fix, and verification."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import requests
from dotenv import dotenv_values
from cvat_sdk import make_client

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "out"


def _env() -> tuple[str, str, dict]:
    vals = dotenv_values(ROOT / ".env")
    url = vals.get("CVAT_URL") or os.environ.get("CVAT_URL", "http://localhost:8080")
    tok = vals.get("CVAT") or vals.get("CVAT_PAT") or os.environ.get("CVAT_PAT", "")
    if not tok:
        raise SystemExit("Missing CVAT token in .env (expected CVAT=... or CVAT_PAT=...)")
    return url, tok, {"Authorization": f"Bearer {tok}"}


def _run_py(module_or_script: list[str]) -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, *module_or_script], cwd=str(ROOT), env=env).returncode


def cmd_status() -> int:
    url, _, hdrs = _env()
    for tid, jid, name in [(60, 59, "front"), (61, 60, "fisheye")]:
        j = requests.get(f"{url}/api/jobs/{jid}", headers=hdrs, timeout=10).json()
        ann = requests.get(f"{url}/api/jobs/{jid}/annotations", headers=hdrs, timeout=15).json()
        labels = {
            l["id"]: l["name"]
            for l in requests.get(f"{url}/api/labels?task_id={tid}&page_size=50", headers=hdrs, timeout=10).json().get("results", [])
        }
        cnt = Counter(labels.get(s["label_id"], "?") for s in ann.get("shapes", []))
        print(f"Task #{tid} ({name}) | Job #{jid} state={j.get('state')} | shapes={len(ann.get('shapes', []))} {dict(cnt)} | tags={len(ann.get('tags', []))}")
    return 0


def cmd_lint(name: str, revision: int) -> int:
    url, tok, _ = _env()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fz = OUT_DIR / f"{name}-front.zip"
    bz = OUT_DIR / f"{name}-fisheye.zip"
    mf = OUT_DIR / f"{name}-manifest.json"
    for p in [fz, bz]:
        if p.exists():
            p.unlink()
    with make_client(host=url, access_token=tok) as c:
        c.tasks.retrieve(60).export_dataset("CVAT for images 1.1", filename=str(fz), include_images=False)
        c.tasks.retrieve(61).export_dataset("CVAT for images 1.1", filename=str(bz), include_images=False)
    return _run_py([
        "-m", "road_lab.road_check", "lint", str(fz), str(bz),
        "--manifest", str(mf), "--name", name, "--revision", str(revision),
    ])


def cmd_complete() -> int:
    url, _, hdrs = _env()
    for jid in [59, 60]:
        r = requests.patch(f"{url}/api/jobs/{jid}", json={"state": "completed"}, headers=hdrs, timeout=10)
        r.raise_for_status()
        print(f"Job #{jid} -> state={r.json().get('state')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Day 11 CVAT QA & Automation CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="Show CVAT Job #59 and #60 status and shape/tag counts")
    p_lint = sub.add_parser("lint", help="Export CVAT 1.1 zips and run road_check lint --manifest")
    p_lint.add_argument("--name", default="phamphunguyenhung")
    p_lint.add_argument("--revision", type=int, default=1)
    sub.add_parser("fix", help="Auto-fix position/direction/density/duplicate lint issues on CVAT")
    sub.add_parser("complete", help="Mark Job #59 and #60 as completed on CVAT")
    sub.add_parser("verify", help="Run full verification gate (selftest, pytest, lint, overlays)")
    args = ap.parse_args()

    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "lint":
        return cmd_lint(args.name, args.revision)
    if args.cmd == "fix":
        return _run_py(["-m", "day11_pipeline.fix_cvat_lint"])
    if args.cmd == "complete":
        return cmd_complete()
    if args.cmd == "verify":
        return _run_py([str(ROOT / "scripts" / "verify_all.py")])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
