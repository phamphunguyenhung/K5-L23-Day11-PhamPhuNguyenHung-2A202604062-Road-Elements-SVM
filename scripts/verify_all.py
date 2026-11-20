"""Verification gate for Day 11 Road v1.0 pipeline and deliverables."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)


def main() -> int:
    checks = []

    p1 = _run([sys.executable, "-m", "road_lab.road_check", "selftest"])
    checks.append(("selftest", p1.returncode == 0, p1.stdout.strip().splitlines()[-1] if p1.stdout else ""))

    p2 = _run([sys.executable, "-m", "pytest", "-q"])
    checks.append(("pytest", p2.returncode == 0, p2.stdout.strip().splitlines()[-1] if p2.stdout else ""))

    front_zip = ROOT / "out" / "phamphunguyenhung-front.zip"
    fish_zip = ROOT / "out" / "phamphunguyenhung-fisheye.zip"
    manifest = ROOT / "out" / "phamphunguyenhung-manifest.json"
    p3 = _run([sys.executable, "-m", "road_lab.road_check", "lint", str(front_zip), str(fish_zip)])
    checks.append(("road_check_lint", p3.returncode == 0, f"exit={p3.returncode}"))

    m_ok = False
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        files = data.get("files", [])
        m_ok = len(files) == 2 and all(not f.get("contains_images", True) for f in files)
    checks.append(("manifest_no_images", m_ok, str(manifest.relative_to(ROOT))))

    qa_files = [
        ROOT / "out" / "qa" / "index.html",
        ROOT / "out" / "qa" / "metrics.json",
        ROOT / "out" / "qa" / "failures.csv",
    ]
    qa_ok = all(p.exists() and p.stat().st_size > 0 for p in qa_files)
    overlays = list((ROOT / "out" / "overlays").glob("*.jpg"))
    checks.append(("qa_and_overlays", qa_ok and len(overlays) == 28, f"overlays={len(overlays)}/28"))

    all_ok = all(ok for _, ok, _ in checks)
    for name, ok, info in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {info}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
