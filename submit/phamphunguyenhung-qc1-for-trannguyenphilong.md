# Phiếu QC 1 — Road v1.0

Lô được kiểm (học viên): Trần Nguyên Phi Long (2A202604058, `trannguyenphilong`)   Người kiểm (học viên): Phạm Phú Nguyên Hùng (2A202604062)  
Ngày: 2026-11-21                          Phiên bản guideline: Road v1.0  
File được kiểm (tên + `revision` trong manifest): `trannguyenphilong-front.zip`, `trannguyenphilong-fisheye.zip`, revision 1  
Số ảnh kiểm: 6 (+ 22 ảnh thêm, ghi riêng)   Số nhãn đã kiểm (shape + tag): 279 (167 shape + 112 tag, 28 ảnh: 16 front, 12 fisheye)  

Phương pháp: dùng công cụ hỗ trợ kiểm tra dữ liệu XML (`road_check lint`, script đối chiếu tag và thuộc tính) cho cả 28 ảnh, và xem overlay trực quan 5 ảnh A05, A06, A07, A12, B11. Các ảnh còn lại mới kiểm ở mức dữ liệu nên chưa kết luận hoàn toàn về chất lượng nhãn.

## Tổng hợp theo mã
| Mã | Loại lỗi | Số mục kiểm | Số lỗi | Mức |
| --- | --- | ---: | ---: | --- |
| QC1-01 tag camera | sai thuộc tính / bỏ sót | 28 | 0 | nặng |
| QC1-02 đủ L1, R1 | bỏ sót | 16 ảnh front | 0 xác nhận, 3 chờ xác nhận (A05, A07, A12) | nặng |
| QC1-03 position | sai thuộc tính / thừa | 48 lane | 0 xác nhận, 1 nghi (A12) | nặng |
| QC1-04 tâm vạch, chiều, điểm dừng | sai phạm vi / bỏ sót | 48 lane | 2 nghi (A06 L1, A07 R2) | chính |
| QC1-05 vạch đứt, che | sai phạm vi / sai thuộc tính | | chưa kiểm | chính |
| QC1-06 style, color, kind | sai thuộc tính | | chưa kiểm | chính |
| QC1-07 vùng lái | sai phạm vi / bỏ sót / thừa | 37 drivable | 0 | chính |
| QC1-08 đèn, màu | bỏ sót / sai phạm vi / sai thuộc tính | 31 đèn | chưa kiểm | nặng / chính |
| QC1-09 facing, type, group, biển phụ | sai thuộc tính | | chưa kiểm | chính |
| QC1-10 hình in, đủ biển | bỏ sót / sai phạm vi | 27 biển | chưa kiểm | chính |
| QC1-11 fisheye | sai phạm vi / sai thuộc tính | 12 ảnh fisheye | 0 xác nhận, 1 chờ xác nhận (B11) | chính |
| QC1-12 file | lỗi file | 2 zip | 0 | nhẹ / nặng |

Đã kiểm và chưa thấy lỗi:
- 28/28 ảnh có đủ 4 tag `camera`, `timeofday`, `weather`, `source`.
- Tag camera khớp hậu tố tên file (FV, RV, MVL, MVR).
- Lane ở camera hai bên (B05–B08, B10, B12) đều `position=other`.
- Không có polygon `drivable` bị suy biến.
- Hai file ZIP và manifest khớp nhau (front 16 ảnh, fisheye 12 ảnh, `contains_images=false`), không thấy lỗi cấu trúc.

## Danh sách lỗi (mỗi lỗi một dòng)
Các dòng dưới là nghi vấn cần kiểm tra thêm, chưa tính là lỗi chắc chắn.

| # | Mã | Ảnh | Nhãn (label, id) | Mức | Mô tả ngắn |
| --- | --- | --- | --- | --- | --- |
| 1 | QC1-02 | A05 | lane L1, R1 | nặng | Thiếu L1 và R1. Đường không thấy vạch rõ, có xe đỗ hai bên. Cần xác nhận có được bỏ qua không. |
| 2 | QC1-02 | A07 | lane L1 | nặng | Thiếu L1. Bên trái là dải phân cách bê tông, chưa thấy vạch kẻ. |
| 3 | QC1-02 | A12 | lane R1 | nặng | Thiếu R1. Sau vạch qua đường không thấy rõ vạch bên phải. |
| 4 | QC1-03 / 04 | A12 | lane L1 (4 điểm) | nặng / chính | Một đoạn polyline ngắn giữa đường, chưa rõ có bám đúng vạch thực tế không. |
| 5 | QC1-04 | A06 | lane L1 (3 điểm) | chính | Đoạn vẽ hơi ngắn, có khả năng dừng trước khi hết vạch. |
| 6 | QC1-04 | A07 | lane R2 (23 điểm) | chính | Polyline đi qua khu vực bánh xe tải, cần xem lại đường vẽ có đúng vị trí không. |

## Ca mơ hồ
| Ảnh | Câu hỏi cho lead | Lời đáp (nếu có) |
| --- | --- | --- |
| A05, A07, A12 | Các ảnh thiếu L1/R1: coach đã xác nhận không thấy vạch (miễn QC1-02) chưa? Nếu chưa, đây là lỗi nặng. | |
| A12 | Đoạn lane L1 giữa đường có bám vạch thật không, hay là vẽ thừa? | |
| B11 | Ảnh fisheye bãi đỗ xe chưa có shape. Phần đường nhựa có phải gán `drivable` không, hay là bãi đỗ nên bị loại? | |

## Quyết định
Lỗi nặng: 0 xác nhận   Lỗi chính: 2 / 279 nhãn = 0,7 % (nếu cả 2 nghi vấn được xác nhận, thấp hơn ngưỡng 5 %)   Lỗi nhẹ: 0   Ca chờ lead: 5  
Quyết định (Release / Hold / Rework): **Hold** (chờ xác nhận)  
Lý do (theo luật của phiếu): Chưa có lỗi nặng được xác nhận và tỉ lệ lỗi chính dưới 5 %, nhưng còn câu hỏi chưa có lời đáp ảnh hưởng tới kết luận (thiếu L1/R1 ở A05, A07, A12 và vùng `drivable` ở B11), nên theo luật là Hold. Nếu các trường hợp thiếu lane được phép bỏ qua và không có lỗi nặng thì chuyển sang Release. Nếu xác nhận có vạch bắt buộc phải gán mà đang thiếu thì Rework, cần sửa trước khi nộp.

Nhận xét: phần dữ liệu đã kiểm của Long tương đối ổn, tag và cấu trúc file đúng, chưa phát hiện lỗi nghiêm trọng chắc chắn. Cần chú ý các lane thiếu hoặc vẽ chưa sát vạch ở A05, A07, A12, và làm rõ quy định `drivable` ở bãi đỗ xe (B11).

Người kiểm: Phạm Phú Nguyên Hùng · Ngày: 2026-11-21  
Trạng thái: bản kiểm tra sơ bộ, chưa chốt kết quả cuối cùng.

Loại lỗi: bỏ sót = thiếu nhãn phải có; thừa = gán cái không phải đối tượng; sai phạm vi = hình lệch, sai chiều, dừng sai chỗ, tràn vùng. Ba loại này theo cách chia lỗi gán nhãn của ISO/IEC 5259-4 (mục 8.4.2); "sai thuộc tính" và "lỗi file" là khóa học thêm. Cách xếp mức: [thang mức lỗi](../docs/qc_severity_road_v1.0.md).
