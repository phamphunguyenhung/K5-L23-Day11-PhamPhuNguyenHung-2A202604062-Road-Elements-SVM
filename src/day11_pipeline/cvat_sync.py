"""Sync Day 11 Road v1.0 project, tasks, and CVAT 1.1 annotations to local CVAT with readback verification."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import dotenv_values
from cvat_sdk import make_client
from cvat_sdk.core.proxies.tasks import ResourceType

from road_lab.cvat_xml import load as load_cvat
from road_lab.taxonomy import raw_labels

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "out"
QA_DIR = OUT_DIR / "qa"


def _wait_task(client, tid: int, timeout: int = 180):
    for _ in range(timeout):
        t = client.tasks.retrieve(tid)
        if getattr(t, "size", 0):
            return t
        time.sleep(1)
    raise TimeoutError(f"Task {tid} did not become ready")


def _count_cvat(path: Path) -> tuple[int, int, int]:
    imgs = load_cvat(path)
    return len(imgs), sum(len(i.shapes) for i in imgs), sum(len(i.tags) for i in imgs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--project", default="d11-road-phamphunguyenhung")
    args = ap.parse_args()

    vals = dotenv_values(ROOT / ".env")
    url = vals.get("CVAT_URL") or os.environ.get("CVAT_URL", "http://localhost:8080")
    tok = vals.get("CVAT") or vals.get("CVAT_PAT") or os.environ.get("CVAT_PAT", "")
    if not tok:
        raise SystemExit("CVAT token missing in .env (expected CVAT=... or CVAT_PAT=...)")

    front_imgs = sorted([p for p in DATA_DIR.iterdir() if p.name.startswith("A") and p.suffix.lower() in {".jpg", ".png"}])
    fish_imgs = sorted([p for p in DATA_DIR.iterdir() if p.name.startswith("B") and p.suffix.lower() in {".jpg", ".png"}])
    front_zip = OUT_DIR / "phamphunguyenhung-front.zip"
    fish_zip = OUT_DIR / "phamphunguyenhung-fisheye.zip"

    if args.dry_run:
        print(json.dumps({
            "mode": "dry-run",
            "cvat_url": url,
            "project": args.project,
            "tasks": [
                {"name": "front", "images": len(front_imgs), "ann_zip": str(front_zip.relative_to(ROOT))},
                {"name": "fisheye", "images": len(fish_imgs), "ann_zip": str(fish_zip.relative_to(ROOT))},
            ],
        }, indent=2))
        return 0

    with make_client(host=url, access_token=tok) as client:
        me = client.api_client.users_api.retrieve_self()[0]
        projs = client.api_client.projects_api.list(search=args.project, page_size=20)[0].results
        proj = next((p for p in projs if p.name == args.project), None)
        if proj is None:
            proj = client.projects.create(spec={"name": args.project, "labels": raw_labels()})
            print(f"Created project #{proj.id} '{proj.name}'")
        else:
            print(f"Using existing project #{proj.id} '{proj.name}'")

        existing_tasks = {
            t.name: t for t in client.api_client.tasks_api.list(project_id=proj.id, page_size=50)[0].results
        }

        evidence = {"cvat_url": url, "user": me.username, "project_id": proj.id, "project_name": proj.name, "tasks": []}
        specs = [
            ("front", front_imgs, front_zip, OUT_DIR / "readback-front.zip"),
            ("fisheye", fish_imgs, fish_zip, OUT_DIR / "readback-fisheye.zip"),
        ]
        for tname, imgs, ann_zip, rb_zip in specs:
            if tname in existing_tasks:
                task = client.tasks.retrieve(existing_tasks[tname].id)
                print(f"Using existing task #{task.id} '{tname}'")
            else:
                task = client.tasks.create_from_data(
                    spec={"name": tname, "project_id": proj.id},
                    resource_type=ResourceType.LOCAL,
                    resources=[str(p) for p in imgs],
                )
                task = _wait_task(client, task.id)
                print(f"Created task #{task.id} '{tname}' ({task.size} frames)")

            task.import_annotations("CVAT 1.1", filename=str(ann_zip))
            task.export_dataset("CVAT for images 1.1", filename=str(rb_zip), include_images=False)

            exp_counts = _count_cvat(ann_zip)
            rb_counts = _count_cvat(rb_zip)
            match = (exp_counts == rb_counts)
            print(f"  [{tname}] uploaded={exp_counts} readback={rb_counts} match={match}")
            evidence["tasks"].append({
                "name": tname,
                "task_id": task.id,
                "url": f"{url}/tasks/{task.id}",
                "frames": task.size,
                "uploaded_counts": {"images": exp_counts[0], "shapes": exp_counts[1], "tags": exp_counts[2]},
                "readback_counts": {"images": rb_counts[0], "shapes": rb_counts[1], "tags": rb_counts[2]},
                "readback_match": match,
            })

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    lint_proc = subprocess.run(
        [sys.executable, "-m", "road_lab.road_check", "lint", str(OUT_DIR / "readback-front.zip"), str(OUT_DIR / "readback-fisheye.zip")],
        cwd=str(ROOT), env=env, capture_output=True, text=True,
    )
    evidence["readback_lint_exit_code"] = lint_proc.returncode
    (QA_DIR / "cvat_sync.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Readback lint exit_code={lint_proc.returncode}")
    return 0 if lint_proc.returncode == 0 and all(t["readback_match"] for t in evidence["tasks"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
