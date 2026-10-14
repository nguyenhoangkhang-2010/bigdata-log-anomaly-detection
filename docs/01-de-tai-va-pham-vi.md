# 1. Đề tài và phạm vi

**Đề tài 13 – Phân tích dữ liệu nhật ký hệ thống để phát hiện bất thường**
(Môn Nhập môn Big Data)

## Gợi ý của đề cương → cách nhóm hiện thực

| Gợi ý trong đề cương | Lựa chọn của nhóm |
|---|---|
| Dữ liệu log từ máy chủ, ứng dụng hoặc mạng | LogHub **HDFS_v1** (log cụm Hadoop, có nhãn theo block) |
| Lưu trữ trên HDFS hoặc Elasticsearch | **Cả hai**: HDFS lưu thô + parquet trung gian; Elasticsearch lưu kết quả để truy vấn/dashboard |
| Spark xử lý và trích xuất đặc trưng | PySpark: parse regex → template/event → vector đếm event theo block + thống kê theo cửa sổ thời gian |
| Phân cụm hoặc phát hiện bất thường | **KMeans** (chính, Spark MLlib); baseline **Isolation Forest** (sklearn) và **z-score** đột biến lỗi |
| Dashboard thống kê lỗi và cảnh báo bất thường | **Kibana**: lỗi theo component/mức độ/thời gian, danh sách block bất thường, cảnh báo đột biến |

## Bài toán
- **Đầu vào:** ~11 triệu dòng log HDFS (≈1,5 GB) – chưa gắn nhãn khi huấn luyện.
- **Đầu ra:** (a) điểm bất thường + cờ cảnh báo cho từng block; (b) thống kê lỗi theo thời gian/component; (c) dashboard.
- **Giá trị:** giảm công sức đọc log thủ công, phát hiện sớm sự cố (block mất, ghi lỗi, replication bất thường).

## Phạm vi
**Trong phạm vi:** xử lý batch trên Spark; phát hiện bất thường không giám sát; đánh giá bằng nhãn có sẵn; dashboard.
**Ngoài phạm vi (hướng phát triển):** streaming thời gian thực (Kafka + Spark Structured Streaming), mô hình học sâu (DeepLog), tự động hành động khi có cảnh báo.

## Tính chất dữ liệu lớn (đưa vào báo cáo)
- *Volume:* hàng triệu dòng, GB dữ liệu text.
- *Velocity:* log sinh liên tục (mô phỏng bằng replay nếu có làm streaming).
- *Variety:* bán cấu trúc – text tự do cần parse thành template.
- *Veracity:* nhãn bất thường rất lệch (~3 %), nhiễu từ template không ổn định.

## Các câu hỏi nghiên cứu
1. Biểu diễn bag-of-events + TF-IDF có đủ để KMeans tách block bất thường không?
2. KMeans (phân tán) so với Isolation Forest (đơn máy): chênh lệch Precision/Recall/F1 và thời gian chạy?
3. Tăng số worker / số partition ảnh hưởng thế nào đến thời gian xử lý (scalability)?
