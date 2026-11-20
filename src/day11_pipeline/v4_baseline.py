"""Phase 0 & 1: Discover environment and create immutable baseline snapshots for Job #60 and Job #59."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import dotenv_values
from cvat_sdk import make_client

ROOT = Path(__file__).resolve().parents[2]
BASELINE_DIR = ROOT / "artifacts" / "day11" / "baseline"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_job(url: str, tok: str, tid: int, jid: int, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    hdrs = {"Authorization": f"Bearer {tok}"}

    meta = requests.get(f"{url}/api/tasks/{tid}/data/meta", headers=hdrs, timeout=10).json()
    labels = requests.get(f"{url}/api/labels?task_id={tid}&page_size=50", headers=hdrs, timeout=10).json()
    ann = requests.get(f"{url}/api/jobs/{jid}/annotations", headers=hdrs, timeout=15).json()
    job_info = requests.get(f"{url}/api/jobs/{jid}", headers=hdrs, timeout=10).json()

    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "labels.json").write_text(json.dumps(labels, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "annotations.json").write_text(json.dumps(ann, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "job.json").write_text(json.dumps(job_info, indent=2, ensure_ascii=False), encoding="utf-8")

    zip_path = out_dir / f"job_{jid}_cvat11.zip"
    if not zip_path.exists():
        with make_client(host=url, access_token=tok) as c:
            c.tasks.retrieve(tid).export_dataset("CVAT for images 1.1", filename=str(zip_path), include_images=False)

    files = ["meta.json", "labels.json", "annotations.json", "job.json", zip_path.name]
    checksums = {fn: _sha256(out_dir / fn) for fn in files}
    manifest = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "task_id": tid,
        "job_id": jid,
        "state": job_info.get("state"),
        "stage": job_info.get("stage"),
        "frames": len(meta.get("frames", [])),
        "shapes": len(ann.get("shapes", [])),
        "tags": len(ann.get("tags", [])),
        "shape_ids": [s["id"] for s in ann.get("shapes", [])],
        "checksums_sha256": checksums,
    }
    (out_dir / "snapshot_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> int:
    vals = dotenv_values(ROOT / ".env")
    url = vals.get("CVAT_URL") or os.environ.get("CVAT_URL", "http://localhost:8080")
    tok = vals.get("CVAT") or vals.get("CVAT_PAT") or os.environ.get("CVAT_PAT", "")
    m60 = snapshot_job(url, tok, 61, 60, BASELINE_DIR / "job_60")
    m59 = snapshot_job(url, tok, 60, 59, BASELINE_DIR / "job_59")
    print(json.dumps({"job_60": {k: v for k, v in m60.items() if k != "shape_ids"}, "job_59": {k: v for k, v in m59.items() if k != "shape_ids"}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
