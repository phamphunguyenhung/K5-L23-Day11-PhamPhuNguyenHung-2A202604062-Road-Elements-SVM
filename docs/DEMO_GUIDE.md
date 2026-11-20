# Demo Guide — Day 11 Road v1.0 Pipeline

## 1. Chạy lại toàn bộ pipeline
Trên Windows PowerShell:
```powershell
.\scripts\run_all.ps1
```
Hoặc trên Linux/macOS:
```bash
bash scripts/run_all.sh
```

## 2. Xem Dashboard QA và Overlay
1. Mở `out/qa/index.html` trên trình duyệt để xem bảng thống kê theo camera, trạng thái PASS/BLOCKED và 5 ca khó cần rà tay.
2. Mở thư mục `out/overlays/` để kiểm tra trực quan 28 ảnh đã vẽ `lane`, `drivable`, `crosswalk`, `traffic_light`, `traffic_sign` và tag ảnh.

## 3. Import lên CVAT lớp (`cvat.edufun.ai`)
1. Mở project `d11-road-<tên>` trên CVAT.
2. Trong task `front` / `fisheye`, chọn **Actions → Upload annotations → CVAT 1.1** và tải lên `out/phamphunguyenhung-front.zip` hoặc `out/phamphunguyenhung-fisheye.zip`.
3. Rà lại 5 ca khó trong `out/qa/index.html`, bổ sung biển báo giao thông ngoài `stop sign` nếu có, rồi export lại và chạy `road_check lint`.
