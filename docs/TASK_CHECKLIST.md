# Day 11 — Task Checklist & Acceptance Matrix

| ID | Task | Dependency | Acceptance Criteria | Status | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| T01 | Repo & Branch Setup | gh auth | Fork `phamphunguyenhung/K5-L23-Day11-...`, `upstream` preserved, branch `feat/day11-complete` | PASS | `git remote -v`, `git branch` |
| T02 | Dataset & Selftest | `day11-data.zip` | 28 ảnh (`A01–A16`, `B01–B12`) trong `data/`, `road_check selftest` PASS | PASS | `SELFTEST PASS`, `31+4 passed` |
| T03 | Module A: Object BBoxes | `yolov8n.pt`, CUDA/CPU | Detect `traffic_light` & `traffic_sign` (≥ 8 px), `edge_zone` theo bán kính 80% | PASS | `src/day11_pipeline/module_a_objects.py` |
| T04 | Module B: Free-space Polygon | Module D mask | Segment `drivable` (`direct`) & `crosswalk` không tràn vào ego/vignette | PASS | `src/day11_pipeline/module_b_freespace.py` |
| T05 | Module C: Lane & Curb Polyline | Module D mask | Vẽ từ gần ra xa, đủ L1/R1, fisheye ≥ 4 điểm theo cung, side camera `position=other` | PASS | `src/day11_pipeline/module_c_lines.py` |
| T06 | Module D: Ignore & ODD Tags | `taxonomy.py` | Đủ 4 tag (`camera`, `timeofday`, `weather`, `source`), ego/lens mask cho fisheye | PASS | `src/day11_pipeline/module_d_ignore.py` |
| T07 | Schema Adapter & Export | `road_lab.cvat_xml` | Export `out/phamphunguyenhung-front.zip` & `fisheye.zip` (CVAT 1.1, không kèm ảnh) | PASS | `out/phamphunguyenhung-manifest.json` |
| T08 | Lint & Verification Gate | `road_check` | `road_check lint` 0 lỗi nặng/chính/nhẹ, `verify_all.py` PASS, 28 overlays | PASS | `out/qa/index.html`, `out/qa/metrics.json` |
| T09 | Demo 16-Task Local CVAT (`Day11-SVM-360-Demo`) | `CVAT_ADMIN_PASSWORD`, `KAGGLE_API_TOKEN` | Tải WoodScape từ Kaggle và tạo 16 task + GT job trên `localhost:8080` | BLOCKED | Thiếu `CVAT_ADMIN_PASSWORD` và `KAGGLE_API_TOKEN` trong `.env` |
