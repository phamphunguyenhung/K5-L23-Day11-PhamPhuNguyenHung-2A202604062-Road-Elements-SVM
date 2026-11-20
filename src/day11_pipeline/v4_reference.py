"""Phase 2: Human Annotation Reference Engine — extract style profile, taxonomy contract, and difficult cases."""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import LineString, Polygon

from road_lab.taxonomy import expected_camera

ROOT = Path(__file__).resolve().parents[2]
BASELINE_DIR = ROOT / "artifacts" / "day11" / "baseline"
REF_DIR = ROOT / "artifacts" / "day11" / "reference"


def _poly_stats(pts: list[tuple[float, float]]) -> dict:
    if len(pts) < 3:
        return {"area": 0.0, "valid": False, "n_pts": len(pts)}
    p = Polygon(pts)
    return {
        "area": round(float(p.area), 1),
        "valid": bool(p.is_valid),
        "n_pts": len(pts),
        "y_min": round(min(y for _, y in pts), 1),
        "y_max": round(max(y for _, y in pts), 1),
    }


def _line_stats(pts: list[tuple[float, float]]) -> dict:
    if len(pts) < 2:
        return {"length": 0.0, "n_pts": len(pts), "near_to_far": False}
    ls = LineString(pts)
    spacings = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)]
    return {
        "length": round(float(ls.length), 1),
        "n_pts": len(pts),
        "mean_spacing_px": round(sum(spacings) / len(spacings), 1) if spacings else 0.0,
        "near_to_far": pts[0][1] >= pts[-1][1],
        "y_min": round(min(y for _, y in pts), 1),
        "y_max": round(max(y for _, y in pts), 1),
    }


def build_reference_artifacts() -> dict:
    REF_DIR.mkdir(parents=True, exist_ok=True)
    examples: list[dict] = []
    difficult: list[dict] = []
    geom_stats: dict[str, list[dict]] = defaultdict(list)
    attr_dist: dict[str, Counter] = defaultdict(Counter)
    taxonomy_contract: dict = {}

    for job_name in ["job_60", "job_59"]:
        jdir = BASELINE_DIR / job_name
        meta = json.loads((jdir / "meta.json").read_text(encoding="utf-8"))
        labels_raw = json.loads((jdir / "labels.json").read_text(encoding="utf-8")).get("results", [])
        ann = json.loads((jdir / "annotations.json").read_text(encoding="utf-8"))

        frames = {i: f["name"] for i, f in enumerate(meta.get("frames", []))}
        id_to_label = {l["id"]: l["name"] for l in labels_raw}
        attr_id_to_name = {a["id"]: a["name"] for l in labels_raw for a in l.get("attributes", [])}
        if not taxonomy_contract:
            taxonomy_contract = {
                l["name"]: {
                    "type": l["type"],
                    "attributes": {a["name"]: a["values"] for a in l.get("attributes", [])},
                }
                for l in labels_raw
            }

        by_frame: dict[int, list[dict]] = defaultdict(list)
        for s in ann.get("shapes", []):
            by_frame[s["frame"]].append(s)

        for fidx, fname in sorted(frames.items()):
            cam = expected_camera(fname) or "front"
            fshapes = by_frame.get(fidx, [])
            if not fshapes:
                difficult.append({"job": job_name, "frame": fidx, "file": fname, "camera": cam, "reason": "unannotated"})
                continue

            has_drivable = False
            lane_positions = []
            for s in fshapes:
                lbl = id_to_label.get(s["label_id"], "unknown")
                prov = "human_created" if s.get("source") == "manual" else str(s.get("source", "unknown"))
                pts = [(float(s["points"][i]), float(s["points"][i + 1])) for i in range(0, len(s["points"]), 2)]
                attrs = {attr_id_to_name.get(a["spec_id"], str(a["spec_id"])): a["value"] for a in s.get("attributes", [])}
                for k, v in attrs.items():
                    attr_dist[f"{lbl}.{k}"][v] += 1

                if lbl == "drivable":
                    has_drivable = True
                    st = _poly_stats(pts)
                    geom_stats[f"{cam}:{lbl}"].append(st)
                elif lbl in {"lane", "road_curb"}:
                    st = _line_stats(pts)
                    geom_stats[f"{cam}:{lbl}"].append(st)
                    if lbl == "lane":
                        lane_positions.append(attrs.get("position", ""))
                elif lbl == "crosswalk":
                    geom_stats[f"{cam}:{lbl}"].append(_poly_stats(pts))

                examples.append({
                    "job": job_name,
                    "frame": fidx,
                    "file": fname,
                    "camera": cam,
                    "shape_id": s["id"],
                    "label": lbl,
                    "type": s["type"],
                    "provenance": prov,
                    "attributes": attrs,
                    "points": pts,
                })

            if not has_drivable:
                difficult.append({"job": job_name, "frame": fidx, "file": fname, "camera": cam, "reason": "missing_drivable"})
            if cam in {"front", "fisheye_front", "fisheye_rear"} and lane_positions and "R1" not in lane_positions:
                difficult.append({"job": job_name, "frame": fidx, "file": fname, "camera": cam, "reason": "missing_R1_position"})

    (REF_DIR / "annotation_examples.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in examples) + "\n", encoding="utf-8"
    )
    (REF_DIR / "difficult_cases.jsonl").write_text(
        "\n".join(json.dumps(d, ensure_ascii=False) for d in difficult) + "\n", encoding="utf-8"
    )
    (REF_DIR / "taxonomy_contract.json").write_text(json.dumps(taxonomy_contract, indent=2, ensure_ascii=False), encoding="utf-8")

    summary_stats = {}
    for k, items in sorted(geom_stats.items()):
        n_pts = [x["n_pts"] for x in items]
        summary_stats[k] = {
            "count": len(items),
            "median_pts": sorted(n_pts)[len(n_pts) // 2],
            "min_pts": min(n_pts),
            "max_pts": max(n_pts),
            "y_min_p10": sorted(x["y_min"] for x in items)[max(0, int(len(items) * 0.1))],
            "y_max_p90": sorted(x["y_max"] for x in items)[min(len(items) - 1, int(len(items) * 0.9))],
        }
    (REF_DIR / "geometry_statistics.json").write_text(json.dumps(summary_stats, indent=2, ensure_ascii=False), encoding="utf-8")

    style_profile = {
        "total_human_examples": len(examples),
        "difficult_cases_count": len(difficult),
        "attribute_distributions": {k: dict(v) for k, v in sorted(attr_dist.items())},
        "geometry_summary": summary_stats,
    }
    (REF_DIR / "annotation_style_profile.json").write_text(json.dumps(style_profile, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"examples": len(examples), "difficult": len(difficult), "categories": len(summary_stats)}


if __name__ == "__main__":
    print(json.dumps(build_reference_artifacts(), indent=2))
