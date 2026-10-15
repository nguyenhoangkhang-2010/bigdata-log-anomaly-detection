# Dashboard Kibana

Mục tiêu (theo đề cương): **thống kê lỗi** và **cảnh báo sự kiện bất thường**, đọc trực tiếp từ Elasticsearch.

## Mở dashboard
```bat
docker compose --profile search up -d elasticsearch kibana    &:: lần đầu tải ~1 GB image Kibana
python dashboard/kibana/build_saved_objects.py                &:: sinh dashboard/kibana/saved_objects/dashboard.ndjson
curl -X POST -H "kbn-xsrf: true" --form file=@dashboard/kibana/saved_objects/dashboard.ndjson "http://localhost:5601/api/saved_objects/_import?overwrite=true"
```
Rồi mở **http://localhost:5601/app/dashboards#/view/logad-dashboard**. (Cần đã nạp dữ liệu vào Elasticsearch bằng job 06.)

Nên đặt Kibana hiển thị giờ UTC cho khớp trang web (log HDFS không có múi giờ):
`curl -X POST -H "kbn-xsrf: true" -H "Content-Type: application/json" http://localhost:5601/api/kibana/settings -d "{\"changes\":{\"dateFormat:tz\":\"UTC\"}}"`

## 11 panel
| Panel | Index | Cách tính |
|---|---|---|
| Dòng nhật ký | `logad-error-stats` | tổng `n` |
| Dòng WARN | `logad-error-stats` | tổng `n`, `level : WARN` |
| Block bị KMeans gắn cờ | `logad-anomalies` | đếm, `kmeans_flag : true` |
| Đột biến lỗi | `logad-spikes` | đếm |
| Dòng WARN theo thời gian | `logad-error-stats` | tổng `n` theo `ts` |
| Component sinh nhiều WARN nhất | `logad-error-stats` | tổng `n` theo `component` |
| Block bất thường theo thời gian | `logad-anomalies` | đếm cờ KMeans theo `first_ts` |
| Phân bố điểm KMeans theo nhãn thật | `logad-anomalies` | histogram `kmeans_score`, tách `label` |
| Mô hình nào gắn cờ | `logad-anomalies` | tỉ lệ `flagged_by` |
| Block bất thường điểm cao nhất / Component có đột biến mạnh nhất | `logad-anomalies`, `logad-spikes` | bảng |

Khoảng thời gian mặc định đặt cứng 09–12/11/2008 vì đây là log cũ (không phải "15 phút gần nhất").

## Ghi chú kỹ thuật
- Dashboard sinh bằng mã (`build_saved_objects.py`) để chỉnh sửa/tái tạo được, thay vì dựng tay trên giao diện.
- NDJSON phải có `coreMigrationVersion`/`typeMigrationVersion`, nếu thiếu Kibana coi là đối tượng rất cũ và lỗi 500 khi import Lens.
- Ảnh chụp dashboard để dùng trong báo cáo: `docs/figures/`.
