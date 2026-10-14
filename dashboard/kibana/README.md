# Dashboard Kibana

Mục tiêu (theo đề cương): **thống kê lỗi** và **cảnh báo sự kiện bất thường**.

## Panel dự kiến
1. Tổng số dòng log / số lỗi (ERROR+WARN) / số block bất thường (metric)
2. Số lỗi theo thời gian, tách theo `level` (line/area) ← index `logad-error-stats`
3. Top component sinh lỗi (bar)
4. Phân bố `anomaly_score` và ngưỡng (histogram) ← `logad-anomalies`
5. Bảng block bất thường mới nhất: block_id, score, cụm, event nổi bật
6. Điểm đột biến (z-score > ngưỡng) trên timeline

## Cách làm
1. `docker compose up -d`, mở http://localhost:5601
2. Tạo Data View cho `logad-*`
3. Dựng Lens/Dashboard, rồi **Stack Management → Saved Objects → Export** vào `saved_objects/dashboard.ndjson`
4. Index template/mapping đặt trong `index_templates/` (JSON) và nạp bằng `curl -X PUT localhost:9200/_index_template/...`

Chụp ảnh dashboard vào `docs/figures/` để dùng trong báo cáo và slide.
