# Final Audit — Day 11 Road Elements & SVM

## 1. Kiểm tra Bắt buộc
| Hạng mục | Lệnh / Đường dẫn | Kết quả |
| :--- | :--- | :--- |
| Selftest checker | `python -m road_lab.road_check selftest` | **PASS** (`SELFTEST PASS`, 78.0/78) |
| Unit & Pipeline Tests | `python -m pytest -q` | **PASS** (`35 passed`) |
| Lint & Manifest | `python -m road_lab.road_check lint out/phamphunguyenhung-front.zip out/phamphunguyenhung-fisheye.zip --manifest out/phamphunguyenhung-manifest.json --name phamphunguyenhung --revision 1` | **PASS** (`exit=0`, critical=0, major=0, minor=0, `contains_images=false`) |
| Verification Gate | `python scripts/verify_all.py` | **PASS** (5/5 checks PASS, 28/28 overlays) |

## 2. Artifacts Đã Sinh
- `out/phamphunguyenhung-front.zip` (2,801 bytes, sha256 `3847fc3442ca64ce55a6cbf6ff877ce2736f78eeaa2c614fed72472f5bbd56c0`)
- `out/phamphunguyenhung-fisheye.zip` (2,576 bytes, sha256 `747040946ddd89f985c2decbe12915e7077a8f7ceefe9e2a9d8a2bc932151b0`)
- `out/phamphunguyenhung-manifest.json`
- `out/qa/index.html`, `out/qa/metrics.json`, `out/qa/failures.csv`
- `out/overlays/` (28 ảnh preview)

## 3. Blocker Khách quan
- `Day11-SVM-360-Demo` (tạo 16 task trên CVAT local `http://localhost:8080` và tải WoodScape từ Kaggle): **BLOCKED** do thiếu `CVAT_ADMIN_PASSWORD` và `KAGGLE_API_TOKEN`.
- Điểm chấm thật trên `coach_gt/` và Phiếu QC 1 chéo với bạn học: cần coach và bạn ghép cặp trên lớp.
