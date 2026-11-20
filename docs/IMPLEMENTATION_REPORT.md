# Báo cáo Triển khai — Ngày 11 (Road Elements & SVM)

## 1. Mục tiêu và Phạm vi
Triển khai pipeline tự động gán nhãn nháp theo chuẩn **Guideline Road v1.0** trên toàn bộ 28 ảnh thực tế của bài lab (`A01–A16` camera trước BDD100K 1280×720 và `B01–B12` fisheye WoodScape 1280×966), xuất CVAT for images 1.1, kiểm tra bằng `road_check lint`, và sinh báo cáo QA theo từng camera.

## 2. Kiến trúc 4 Module
- **Module A (`module_a_objects.py`)**: Dùng `yolov8n.pt` (PyTorch CUDA trên Quadro P1000 / CPU fallback) phát hiện `traffic_light` và `traffic_sign` có chiều cao ≥ 8 px, phân loại màu đèn qua HSV, và tính `edge_zone` đúng công thức bán kính 80% trong `road_check.py`.
- **Module B (`module_b_freespace.py`)**: Phân vùng mặt đường `drivable` (`area_type=direct`) từ patch mẫu phía trước xe kết hợp morphology, loại trừ vùng ignore của Module D, và phát hiện `crosswalk` theo chu kỳ vạch trắng.
- **Module C (`module_c_lines.py`)**: Dò sơn trắng/vàng theo từng hàng ngang từ đáy ảnh lên (đảm bảo chiều vẽ **từ gần ra xa**), ép đủ `L1`/`R1` trên `front`, `fisheye_front`, `fisheye_rear`, và ép `position=other` trên `fisheye_left`/`fisheye_right`. Ảnh fisheye lấy mẫu 8 điểm theo cung.
- **Module D (`module_d_ignore.py`)**: Gắn 4 tag (`camera`, `timeofday`, `weather`, `source`) và tạo mặt nạ loại trừ viền tối fisheye + thân xe ego ở đáy ảnh.
- **Schema Adapter (`schema_adapter.py`)**: Kiểm tra toàn bộ label, kiểu hình, thuộc tính, kích thước ảnh và quy tắc fisheye trước khi ghi XML.

## 3. Kết quả Đo đạc Thực tế
- **Thời gian chạy toàn bộ 28 ảnh**: `17.82s` (đã gồm tải `yolov8n.pt` 6.2 MB lần đầu).
- **Schema errors**: `0`.
- **`road_check selftest`**: `PASS` (`78.0/78` trên GT tổng hợp).
- **`pytest -q`**: `35 passed` (31 test gốc + 4 test mới cho pipeline).
- **`road_check lint`**: `exit=0`, `0` lỗi nặng, `0` lỗi chính, `0` lỗi nhẹ.
- **Phân bố shape theo camera**:
  - `front` (16 ảnh): 32 `lane`, 16 `drivable`, 5 `crosswalk`, 1 `traffic_light`
  - `fisheye_front` (3 ảnh): 6 `lane`, 3 `drivable`, 2 `crosswalk`, 1 `traffic_light`
  - `fisheye_rear` (3 ảnh): 6 `lane`, 3 `drivable`
  - `fisheye_left` (3 ảnh): 3 `lane`, 3 `drivable`
  - `fisheye_right` (3 ảnh): 3 `lane`, 3 `drivable`, 1 `crosswalk`

## 4. Hạn chế Thực tế & Blocker
1. **Chưa có Golden GT thật của lớp**: GT thật nằm trên máy coach (`coach_gt/`), nên không thể đo IoU hay khoảng cách pixel tới GT thật; chỉ kiểm định dạng và quy tắc hình học bằng `road_check lint` và `selftest`.
2. **Độ chính xác nhận diện đèn/biển nhỏ và làn cong gắt**: `yolov8n` (COCO) chỉ có class `traffic light` và `stop sign`, nên các biển báo khác (warning/mandatory/information) chưa được prelabel tự động và cần gán bổ sung trên CVAT.
3. **Repo demo `Day11-SVM-360-Demo`**: Bị block tạo 16 task trên `localhost:8080` và tải WoodScape từ Kaggle do thiếu `CVAT_ADMIN_PASSWORD` và `KAGGLE_API_TOKEN` trong `.env`.
