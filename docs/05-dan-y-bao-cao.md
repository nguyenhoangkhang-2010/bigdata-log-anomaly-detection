# 5. Dàn ý báo cáo (đúng cấu trúc đề cương)

Bản Word cuối đặt vào `docs/report/`, slide vào `docs/slides/`.

1. **Trang bìa**
2. **Lịch làm việc nhóm hàng tuần** ← `04-phan-cong.md`
3. **Công việc mỗi thành viên** ← `04-phan-cong.md`
4. **Mục lục**
5. **Giới thiệu đề tài** ← `01-de-tai-va-pham-vi.md`
   - Bối cảnh, bài toán, mục tiêu, phạm vi, đầu vào/đầu ra, giá trị
   - Mô tả dữ liệu: nguồn, quy mô, định dạng, thuộc tính, đặc trưng dữ liệu lớn (5V)
6. **Cơ sở lý thuyết** ← `03-ly-thuyet.md`
7. **Xây dựng ứng dụng, trực quan hóa dữ liệu**
   - 7.1 Kiến trúc & luồng dữ liệu (`06-kien-truc.md`), lý do chọn công nghệ
   - 7.2 Khảo sát & tiền xử lý (dòng không parse được, trùng lặp, block thiếu nhãn…)
   - 7.3 Trích đặc trưng
   - 7.4 Mô hình & tham số (KMeans, Isolation Forest, z-score)
   - 7.5 Môi trường, các bước vận hành
   - 7.6 Kết quả & đánh giá: bảng Precision/Recall/F1/PR-AUC, so sánh, phân tích lỗi, thời gian chạy theo số worker
   - 7.7 Dashboard Kibana (ảnh chụp + giải thích thông tin rút ra)
   - 7.8 Hạn chế
8. **Kết luận và định hướng phát triển** (streaming Kafka, Drain3, DeepLog/LSTM, alerting tự động)
9. **Tài liệu tham khảo**
10. **Phụ lục** (cấu hình, truy vấn, hướng dẫn cài đặt chi tiết)

## Tài liệu tham khảo gợi ý (xác minh trước khi trích dẫn)
- He et al., *Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics*.
- He et al., *Drain: An Online Log Parsing Approach with Fixed Depth Tree* (ICWS 2017).
- Xu et al., *Detecting Large-Scale System Problems by Mining Console Logs* (SOSP 2009) – bộ dữ liệu HDFS gốc.
- Liu et al., *Isolation Forest* (ICDM 2008).
- Tài liệu chính thức Apache Spark MLlib, HDFS, Elasticsearch, Kibana.
