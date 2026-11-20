"""Capture the 4 required report screenshots into out/screenshots/ using Playwright."""
from __future__ import annotations

import html
import os
import zipfile
from pathlib import Path

from dotenv import dotenv_values
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "out"
SHOTS = OUT_DIR / "screenshots"


def _extract_lane_xml_snippet() -> str:
    with zipfile.ZipFile(OUT_DIR / "phamphunguyenhung-front.zip") as zf:
        xml = zf.read("annotations.xml").decode("utf-8")
    lines = xml.splitlines()
    for i, ln in enumerate(lines):
        if '<polyline label="lane"' in ln:
            return "\n".join(lines[max(0, i - 2) : min(len(lines), i + 10)])
    return "\n".join(lines[:20])


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    vals = dotenv_values(ROOT / ".env")
    url = vals.get("CVAT_URL") or os.environ.get("CVAT_URL", "http://localhost:8080")
    tok = vals.get("CVAT") or vals.get("CVAT_PAT") or os.environ.get("CVAT_PAT", "")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="msedge")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, extra_http_headers={"Authorization": f"Bearer {tok}"})
        page = ctx.new_page()

        # Seed token into localStorage on origin first
        page.goto(url, wait_until="domcontentloaded")
        page.evaluate(f"localStorage.setItem('token', {tok!r});")

        # 1. Project #5 Labels
        page.goto(f"{url}/projects/5", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(SHOTS / "01-project-labels.png"))

        # 2. Front Job #59 frame 7 (A08)
        page.goto(f"{url}/tasks/60/jobs/59?frame=7", wait_until="networkidle", timeout=25000)
        page.wait_for_timeout(2500)
        page.screenshot(path=str(SHOTS / "02-front-annotated.png"))

        # 3. Fisheye Job #60 frame 2 (B03)
        page.goto(f"{url}/tasks/61/jobs/60?frame=2", wait_until="networkidle", timeout=25000)
        page.wait_for_timeout(2500)
        page.screenshot(path=str(SHOTS / "03-fisheye-polyline.png"))

        # 4. XML snippet screenshot
        snippet = _extract_lane_xml_snippet()
        xml_html = f"""<!doctype html><html><body style="margin:0;padding:24px;background:#ffffff;font-family:Consolas,monospace;font-size:15px;color:#0f172a">
        <div style="margin-bottom:10px;font-family:system-ui;font-weight:700">annotations.xml (out/phamphunguyenhung-front.zip)</div>
        <pre style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:8px;padding:16px;line-height:1.5">{html.escape(snippet)}</pre>
        </body></html>"""
        page.set_content(xml_html)
        page.screenshot(path=str(SHOTS / "04-xml-lane-snippet.png"))

        browser.close()
    print("Captured 4 screenshots in", SHOTS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
