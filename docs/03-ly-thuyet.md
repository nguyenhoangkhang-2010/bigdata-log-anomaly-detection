# 3. Cơ sở lý thuyết (dàn ý ghi chú – điền dần ở tuần 4–5)

> Mỗi mục cần: định nghĩa ngắn → cơ chế hoạt động → vì sao chọn cho đề tài → 1 ví dụ minh họa nhỏ.

## 3.1 Dữ liệu nhật ký (log) và bài toán phát hiện bất thường
- [ ] Cấu trúc log, log không cấu trúc → có cấu trúc
- [ ] Các loại bất thường: điểm (point), ngữ cảnh (contextual), tập thể (collective)
- [ ] Quy trình chuẩn: thu thập → parse → nhóm theo phiên → đặc trưng → phát hiện (He et al., *Loghub*, *Experience Report: System Log Analysis for Anomaly Detection*)

## 3.2 Lưu trữ và xử lý phân tán
- [ ] HDFS: NameNode/DataNode, block, replication; vì sao phù hợp file log lớn ghi một lần
- [ ] Apache Spark: RDD vs DataFrame, lazy evaluation, shuffle, partition; so sánh MapReduce
- [ ] Spark MLlib: Pipeline, VectorAssembler, KMeans, ClusteringEvaluator
- [ ] Parquet: lưu cột, nén, predicate pushdown

## 3.3 Trích xuất template log
- [ ] Mask bằng regex (cách dùng trong skeleton) – ưu/nhược
- [ ] Drain / Drain3: cây độ sâu cố định (tùy chọn nâng cấp)

## 3.4 Mô hình
- [ ] Bag-of-events, TF-IDF cho event
- [ ] KMeans: hàm mục tiêu, khởi tạo k-means||, chọn k (elbow/silhouette); điểm bất thường = khoảng cách tới tâm
- [ ] Isolation Forest: ý tưởng cô lập bằng cây ngẫu nhiên, độ dài đường đi
- [ ] Z-score cho chuỗi thời gian số lỗi

## 3.5 Đánh giá
- [ ] Dữ liệu mất cân bằng (~3 %): vì sao không dùng Accuracy
- [ ] Precision, Recall, F1, PR-AUC; chọn ngưỡng

## 3.6 Elasticsearch và Kibana
- [ ] Inverted index, mapping, index template
- [ ] Kibana: Lens/Dashboard, saved objects, (tùy chọn) alerting rule
