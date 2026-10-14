# 2. Kế hoạch 10 tuần

Bám theo kế hoạch chung của đề cương; cột "Điều chỉnh" là chỗ nhóm chủ động lệch để giảm rủi ro.
Mốc nộp: **Giai đoạn 1 – tuần 5/6**, **Giai đoạn 2 – tuần 9**, **thuyết trình – tuần 10**
(xác nhận lại ngày chính xác với giảng viên).

| Tuần | Đề cương yêu cầu | Việc cụ thể của nhóm | Sản phẩm | Điều chỉnh |
|---|---|---|---|---|
| 1–3 | Đăng ký đề tài, lập kế hoạch | Đăng ký đề tài 13; chốt dataset HDFS_v1 và xin GV duyệt; dựng `docker compose` (HDFS, Spark, ES, Kibana); đẩy dữ liệu mẫu lên HDFS; phân công | Đề tài đã duyệt, kế hoạch, hạ tầng chạy được | **Tải & mô tả dữ liệu sớm** (đề cương xếp ở tuần 8–9 nhưng cần để chạy baseline) |
| 4–5 | Lý thuyết công nghệ/mô hình | Tóm tắt lý thuyết: HDFS, Spark (RDD/DataFrame/MLlib), log parsing/Drain, KMeans, Isolation Forest, Elasticsearch/Kibana; ví dụ nhỏ; chạy `02_parse_logs` trên mẫu | `docs/03-ly-thuyet.md`, parser + test | |
| 6–7 | Baseline + **nộp báo cáo tiến độ GĐ1** | Hoàn thiện `03_extract_features`, `04_detect_anomalies` (KMeans), `05_evaluate`; có số Precision/Recall/F1 đầu tiên; nhận diện điểm cần cải thiện | Báo cáo tiến độ + bảng kết quả baseline | |
| 8–9 | Dữ liệu, trực quan hóa, báo cáo, slide, **nộp GĐ2** | Chạy toàn bộ dữ liệu; thêm Isolation Forest + z-score, so sánh; `06_index_elasticsearch`; dựng dashboard Kibana; viết báo cáo + slide; rà soát đúng cấu trúc | Báo cáo hoàn chỉnh, slide, source code, hướng dẫn chạy | |
| 10 | Thuyết trình, phản biện | Tập demo (có sẵn video dự phòng), chuẩn bị câu hỏi phản biện | Buổi thuyết trình | |

## Checklist nộp bài (Classroom)
- [ ] Source code (zip repo, không kèm dữ liệu lớn; có link tải dữ liệu)
- [ ] File Word báo cáo – đúng cấu trúc ở `docs/05-dan-y-bao-cao.md`
- [ ] File PPT báo cáo
- [ ] Hướng dẫn cài đặt/chạy (`README.md`)
- [ ] Bảng phân công và mức đóng góp (`docs/04-phan-cong.md`)
- [ ] Báo cáo không lỗi chính tả; không sao chép (điểm 0 nếu trùng bài)

## Rubric tự kiểm tra (thang 10)
| Tiêu chí | Điểm | Chúng ta cần chứng minh |
|---|---|---|
| Tính ứng dụng của kĩ thuật | 1.0 | Bài toán thực tế, vì sao dùng Big Data |
| Lưu trữ và xử lý/phân tích dữ liệu | 2.0 | HDFS + Spark, tiền xử lý, mô tả dữ liệu, thời gian chạy |
| Mô hình/công nghệ xử lý | 2.5 | KMeans + baseline, chọn tham số, metric, so sánh, hạn chế |
| Trực quan hóa/Xây dựng ứng dụng | 2.5 | Dashboard Kibana thể hiện rõ lỗi + cảnh báo |
| Trình bày báo cáo | 1.0 | Đúng cấu trúc, rõ ràng |
| Phân công và phối hợp | 1.0 | Lịch tuần + commit/đóng góp từng người |
