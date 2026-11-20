"""Visual overlay renderer for Road v1.0 CVAT annotations."""
from __future__ import annotations

from pathlib import Path
import cv2
import numpy as np

from road_lab.cvat_xml import Image


COLOR_BGR = {
    "lane": (0, 212, 255),
    "road_curb": (14, 127, 255),
    "crosswalk": (194, 119, 227),
    "drivable": (44, 160, 44),
    "traffic_light": (40, 39, 214),
    "traffic_sign": (180, 119, 31),
}


def render_overlay(img_path: Path, cvat_img: Image, out_path: Path) -> None:
    bgr = cv2.imread(str(img_path))
    if bgr is None:
        return
    overlay = bgr.copy()

    # 1. Polygons first (alpha blend)
    for s in cvat_img.shapes:
        if s.kind == "polygon" and len(s.points) >= 3:
            pts = np.array([[int(round(x)), int(round(y))] for x, y in s.points], dtype=np.int32)
            col = COLOR_BGR.get(s.label, (0, 255, 0))
            cv2.fillPoly(overlay, [pts], col)
            cv2.polylines(bgr, [pts], True, col, 2)

    bgr = cv2.addWeighted(overlay, 0.28, bgr, 0.72, 0)

    # 2. Polylines & Boxes
    for s in cvat_img.shapes:
        col = COLOR_BGR.get(s.label, (255, 255, 255))
        if s.kind == "polyline" and len(s.points) >= 2:
            pts = np.array([[int(round(x)), int(round(y))] for x, y in s.points], dtype=np.int32)
            cv2.polylines(bgr, [pts], False, col, 3)
            # Mark start point (near vehicle) with filled circle
            cv2.circle(bgr, tuple(pts[0]), 6, (0, 0, 255), -1)
            pos = s.attributes.get("position", "")
            cv2.putText(bgr, f"{s.label}:{pos}", (int(pts[0][0]) + 6, int(pts[0][1]) - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 2)
        elif s.kind == "rectangle" and len(s.points) == 2:
            (x1, y1), (x2, y2) = s.points
            p1, p2 = (int(round(x1)), int(round(y1))), (int(round(x2)), int(round(y2)))
            cv2.rectangle(bgr, p1, p2, col, 2)
            tag_txt = s.attributes.get("color", s.attributes.get("group", ""))
            ez = " EZ" if s.attributes.get("edge_zone") == "true" else ""
            cv2.putText(bgr, f"{s.label}({tag_txt}{ez})", (p1[0], max(15, p1[1] - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)

    # 3. Header banner with tags
    tags_str = " | ".join(f"{t.label}={t.attributes.get('value', '')}" for t in cvat_img.tags)
    cv2.rectangle(bgr, (0, 0), (bgr.shape[1], 28), (245, 247, 250), -1)
    cv2.putText(bgr, f"{cvat_img.name}  [{tags_str}]  shapes={len(cvat_img.shapes)}",
                (10, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (20, 25, 35), 1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), bgr)
