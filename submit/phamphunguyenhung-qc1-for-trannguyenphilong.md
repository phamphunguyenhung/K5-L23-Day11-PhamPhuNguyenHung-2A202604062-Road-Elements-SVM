# Phiếu QC 1 — Road v1.0

Lô được kiểm (học viên): Trần Nguyên Phi Long (2A202604058, `trannguyenphilong`)   Người kiểm (học viên): Phạm Phú Nguyên Hùng (2A202604062)  
Ngày: 2026-11-21                          Phiên bản guideline: Road v1.0  
File được kiểm (tên + `revision` trong manifest): `trannguyenphilong-front.zip`, `trannguyenphilong-fisheye.zip`, `trannguyenphilong-manifest.json` · `revision` 1  
Số ảnh kiểm: 6 (+ 1 ảnh thêm B11, ghi riêng)   Số nhãn đã kiểm (shape + tag): 78 (54 shape + 24 tag)  

Sáu ảnh kiểm: A05, A06, A07, A08, A12 (front) và B03 (fisheye_rear). Chọn theo các điểm cần soi: không có vạch (A05), đèn và biển nhiều (A06, A08, A12), vạch dưới cầu và vạch dọc xe tải (A06, A07), fisheye có nhiều biển và vạch cong (B03). Ảnh thêm B11 (camera lùi vào ô đỗ) chỉ xem để ghi nhận, không tính vào mẫu.  
Cách kiểm: mở XML, vẽ overlay từng nhãn kèm thuộc tính (position, style, color, kind, group, facing) lên ảnh gốc trong `data/`, phóng to chỗ khó nhìn (A07 vạch dọc xe tải, B03 các biển, A08 các đèn); thêm `road_check lint` cho cả lô. Không có đáp án (GT) của coach để đối chiếu, nên đây là đánh giá bằng mắt trên ảnh.  
Số nhãn theo ảnh: A05 2 + 4 tag · A06 15 + 4 · A07 6 + 4 · A08 19 + 4 · A12 8 + 4 · B03 4 + 4 (tổng 54 shape + 24 tag).  
Id nhãn là thứ tự phần tử trong `<image>` của `annotations.xml`, đếm từ 0, tính cả tag (kiểm lại bằng overlay).

## Tổng hợp theo mã
| Mã | Loại lỗi | Số mục kiểm | Số lỗi | Mức |
| --- | --- | ---: | ---: | --- |
| QC1-01 tag camera | sai thuộc tính / bỏ sót | 6 (tag camera, 6 ảnh) | 0 | nặng |
| QC1-02 đủ L1, R1 | bỏ sót | 6 (ảnh front/rear: A05, A06, A07, A08, A12, B03) | 0 xác nhận; 3 ảnh chờ coach | nặng |
| QC1-03 position | sai thuộc tính / thừa | 11 (lane) | 0 | nặng |
| QC1-04 tâm vạch, chiều, điểm dừng | sai phạm vi / bỏ sót | 11 (lane) | 2 | chính |
| QC1-05 vạch đứt, che | sai phạm vi / sai thuộc tính | 11 (lane) | 0 | chính |
| QC1-06 style, color, kind | sai thuộc tính | 11 (lane) | 1 | chính |
| QC1-07 vùng lái | sai phạm vi / bỏ sót / thừa | 11 (8 drivable + 3 crosswalk) | 0 | chính |
| QC1-08 đèn, màu | bỏ sót / sai phạm vi / sai thuộc tính | 18 (box đèn) | 0 | nặng / chính |
| QC1-09 facing, type, group, biển phụ | sai thuộc tính | 29 (18 box đèn + 11 box biển) | 0 | chính |
| QC1-10 hình in, đủ biển | bỏ sót / sai phạm vi | 17 (11 box biển + 6 biển thấy được mà chưa có box) | 6 | chính |
| QC1-11 fisheye | sai phạm vi / sai thuộc tính | 3 (polyline fisheye B03; ảnh không có box nên không có `edge_zone` để kiểm) | 0 | chính |
| QC1-12 file | lỗi file | 3 (2 zip + manifest) | 0 | nhẹ / nặng |

Ghi chú theo mã:
- QC1-02: A05 không thấy vạch ở cả hai bên; A07 bên trái là dải phân cách bê tông; A12 bên phải chỉ có lề và xe đỗ. Cả ba không vẽ vạch, đúng luật nếu coach xác nhận không thấy vạch. Đã ghi vào mục "Ca mơ hồ".
- QC1-03: `position` đúng ở cả 11 lane (A07 R1 là vạch liền sát xe, A08 L1 là vạch đứt mờ).
- QC1-08: các đèn nhìn nghiêng (A06 #13, A08 #13, #14, #15) gán `facing = side`, đèn đi bộ (A06 #14, A08 #12, A12 #2) gán `type = pedestrian`, đèn phía sau gán `facing = back`: đều hợp lý. Vài đèn rất xa (dưới 8 px) tôi không phân biệt được nên không tính.
- QC1-09: nhóm biển hợp lý (biển cảnh báo vàng `warning`, biển tên đường xanh `information`, mũi tên một chiều `mandatory`).

## Danh sách lỗi (mỗi lỗi một dòng)
| # | Mã | Ảnh | Nhãn (label, id) | Mức | Mô tả ngắn |
| --- | --- | --- | --- | --- | --- |
| 1 | QC1-04 | A06 | lane #7 (L1 vàng) | chính | Polyline đi từ (442,416) tới (470,399), vạch vàng còn thấy thêm khoảng 10 px ở cả hai đầu: bắt đầu quanh (428,416), kéo tới khoảng (478,393) |
| 2 | QC1-04 | A12 | lane #11 (L1 đứt) | chính | Polyline dừng ở y ≈ 400, trong khi các đoạn đứt còn thấy tới khoảng (542,380): nối dài tới đoạn xa nhất |
| 3 | QC1-06 | A07 | lane #1 (R2) | chính | `style = dashed` nhưng phóng to dọc (800,300) → (1200,450) thấy một vạch trắng liền, không có chỗ ngắt: đổi thành `solid` |
| 4 | QC1-10 | B03 | traffic_sign (thiếu) | chính | Bỏ sót biển chữ nhật xanh dương `information` ~(841,240)–(872,269) |
| 5 | QC1-10 | B03 | traffic_sign (thiếu) | chính | Bỏ sót biển tròn xanh mũi tên `mandatory` ~(838,279)–(849,291) |
| 6 | QC1-10 | B03 | traffic_sign (thiếu) | chính | Bỏ sót biển tròn xanh mũi tên `mandatory` ~(913,304)–(924,317) |
| 7 | QC1-10 | B03 | traffic_sign (thiếu) | chính | Bỏ sót biển tròn xanh mũi tên `mandatory` trên cột vàng ~(1132,362)–(1156,399), nằm sát rìa ống kính nên bật `edge_zone` |
| 8 | QC1-10 | B03 | traffic_sign (thiếu) | chính | Bỏ sót biển tròn viền đỏ trắng `prohibitory` ~(173,298)–(195,324) |
| 9 | QC1-10 | B03 | traffic_sign (thiếu) | chính | Bỏ sót biển tròn cấm vào đỏ ~(260,292)–(271,302), `prohibitory` |

Ảnh không lỗi chắc chắn: A08 (chỉ còn một câu hỏi mở về hai vạch trắng liền bên trái chưa gán, xem mục "Ca mơ hồ"). Các ảnh khác trong mẫu đều có ít nhất một lỗi hoặc một ca chờ.

## Ca mơ hồ
| Ảnh | Câu hỏi cho lead | Lời đáp (nếu có) |
| --- | --- | --- |
| A05, A07, A12 | Ba ảnh thiếu L1/R1: coach đã xác nhận không thấy vạch (miễn QC1-02) chưa? Nếu chưa, đây là lỗi nặng. | (chưa có) |
| A08 | Hai vạch trắng liền bên trái làn (~(40,358) → (480,282) và ~(0,321) → (420,279)) chưa được gán. Hai vạch này có bắt buộc phải gán là L2 / `other` không? Nếu có thì thêm 2 lỗi bỏ sót (QC1-04). | (chưa có) |
| B11 | Ảnh fisheye lùi vào ô đỗ cho người khuyết tật không có shape. Ô đỗ có nằm ngoài phạm vi Road v1.0 không (không phải làn xe)? Tôi tạm chấp nhận để trống, không tính lỗi. | (chưa có) |

## Quyết định
Lỗi nặng: 0 xác nhận (3 ảnh QC1-02 chờ coach)   Lỗi chính: 9 / 78 nhãn = 11,5 %   Lỗi nhẹ: 0   Ca chờ lead: 3  
Quyết định (Release / Hold / Rework): **Rework**  
Lý do (theo luật của phiếu): Không có lỗi nặng được xác nhận, nhưng tỉ lệ lỗi chính 9 / 78 = 11,5 % vượt ngưỡng 5 %, nên theo luật là Rework. Nếu cộng 6 nhãn biển bị bỏ sót vào mẫu số (9 / 84 = 10,7 %) thì vẫn vượt. Phần lớn lỗi (6/9) là QC1-10: ảnh fisheye B03 không có box biển nào dù thấy rõ ít nhất 6 biển. Ba ca mơ hồ (QC1-02 ở A05, A07, A12; hai vạch trắng A08; B11) không làm đổi kết luận: kể cả khi cả ba được giải quyết theo hướng có lợi, 9 lỗi chính vẫn vượt 5 %.

## Ghi chú cho bạn (không chấm)
- **Lỗi chính là thiếu biển ở fisheye:** manifest của bạn có 0 `traffic_sign` ở fisheye (chỉ có 2 `traffic_light`), trong khi B03 có ít nhất 6 biển và các ảnh fisheye trước/sau thường có biển. Nên rà lại B01–B04, B09, B11 (ảnh trước/sau) để thêm biển đủ từ 8 px.
- **Vạch ngắn:** A06 L1 và A12 L1 đều dừng sớm; nối dài tới hết đoạn sơn thấy được.
- **A07 R2:** đổi `style` thành `solid`; bạn đã tự phát hiện lỗi này trong báo cáo, đúng.
- **Phiếu này đã cập nhật so với bản đầu:** bản đầu chỉ kiểm bằng dữ liệu và overlay 5 ảnh, chưa có số mục kiểm cho QC1-05, 06, 08, 09, 10. Bản này kiểm đủ 12 mã trên 6 ảnh. Hai điểm trong bản đầu tôi đã rút lại sau phản hồi của bạn: A12 L1 là vạch đứt thật (chỉ dừng sớm, không phải vẽ thừa) và A07 R2 bám đúng tâm vạch (chỉ sai `style`).
- Khi nộp lại, nhớ gửi kèm manifest `--revision 2` và giữ bản cũ trong `r1/` theo `SUBMISSION.md`.

Loại lỗi: bỏ sót = thiếu nhãn phải có; thừa = gán cái không phải đối tượng; sai phạm vi = hình lệch, sai chiều, dừng sai chỗ, tràn vùng. Ba loại này theo cách chia lỗi gán nhãn của ISO/IEC 5259-4 (mục 8.4.2); "sai thuộc tính" và "lỗi file" là khóa học thêm. Cách xếp mức: [thang mức lỗi](../docs/qc_severity_road_v1.0.md).
