# Kịch bản demo (khoảng 8–10 phút)

Số liệu dưới đây là kết quả thật của lần chạy trên cụm HDFS + Spark (dữ liệu LogHub HDFS_v1). Nếu chạy lại pipeline, số có thể lệch nhẹ
(KMeans chọn k khác nhau giữa các lần), hãy xem lại trang Mô hình trước khi nói.

## Chuẩn bị (làm trước 10 phút)
1. Mở Docker Desktop, chờ đủ 8 container: `docker ps` thấy `logad-namenode, datanode, spark-master, spark-worker, elasticsearch, kibana, api, web`.
   Nếu thiếu: `docker compose --profile bigdata --profile search up -d`
2. Mở sẵn 6 tab trình duyệt theo đúng thứ tự dưới đây. Kibana lần đầu mở có hộp "Your data is not secure": bấm Dismiss.
3. Kiểm tra nhanh: http://localhost:3000/api/v1/health phải trả `"data_source":"elasticsearch"`.

| Tab | Link |
|---|---|
| 1 HDFS | http://localhost:9870/explorer.html#/logad |
| 2 Spark | http://localhost:8080 |
| 3 Web | http://localhost:3000 |
| 4 Kibana | http://localhost:5601/app/dashboards#/view/logad-dashboard |
| 5 Elasticsearch | http://localhost:9200/_cat/indices/logad-*?v |
| 6 Sơ đồ | `docs/06-kien-truc.md` (hoặc slide kiến trúc) |

## Mở đầu (30 giây)
"Đề tài 13: phát hiện bất thường trong nhật ký hệ thống. Dữ liệu là log HDFS_v1 của LogHub: 11,2 triệu dòng, 575 nghìn block.
Mỗi block là một vòng đời ghi dữ liệu; hệ thống tìm những block có hành vi lạ."

## 1. Lưu trữ và xử lý (2 phút)
- **Tab HDFS**: thư mục `/logad` có `raw` (1,5 GB log thô, 12 block 128 MB), `parsed` (330 MB, 12,6 triệu hàng đã parse), `features`, `results`.
  "Log thô nằm trên HDFS, mọi bước trung gian của Spark đọc và ghi trên HDFS."
- **Tab Spark**: 1 worker 8 lõi, 8 GB. Lịch sử job bị xóa mỗi khi cụm khởi động lại, nên để thấy job thật hãy chạy sống một job nhẹ trong lúc nói
  (13 giây): `.\scripts\submit.ps1 01_ingest_to_hdfs.py`, rồi tải lại tab Spark sẽ thấy ứng dụng trong *Completed Applications*; terminal in ra
  "11,175,629 dòng log thô" đọc từ `hdfs://namenode:9000/logad/raw/HDFS.log`.
  "Spark làm bốn việc: parse, trích đặc trưng, chạy KMeans, đánh giá."
- **Tab Elasticsearch**: 6 index; `logad-anomalies` 575.061 tài liệu, `logad-logs` ~805 nghìn tài liệu.
  "Kết quả cuối được nạp vào Elasticsearch để web và Kibana truy vấn nhanh."

## 2. Web dashboard (4 phút)
1. **Tổng quan** (`/`): 11.175.629 dòng, 17.451 block bị gắn cờ (3,0%), 0 ERROR, 362.793 WARN, 167 cảnh báo.
   Chỉ biểu đồ lỗi theo thời gian: các đỉnh WARN; nói rõ "dataset này chỉ có INFO và WARN".
2. **Bất thường** (`/anomalies`): danh sách xếp theo điểm. Thử gõ mã block vào ô tìm, đổi sang IForest để thấy hai mô hình không đồng ý hoàn toàn.
3. **Chi tiết block** (bấm block đầu danh sách, ví dụ `blk_-5051155910414339630`): 16 dòng log; ba mô hình chấm: KMeans 1,157 (gắn cờ),
   Isolation Forest 0,629 (gắn cờ), Z-score 0 (không). Mục "Vì sao khác thường": block có 2 lần `writeBlock received exception java.io.EOFException`
   và `PacketResponder … Interrupted` mà block bình thường hầu như không có (kỳ vọng ~0). Nhãn LogHub là Anomaly.
   "Hệ thống không chỉ báo 'bất thường' mà chỉ ra sự kiện nào gây ra."
4. **Sự kiện** (`/events`): cột Độ nghiêng 37,3 nghĩa là mẫu sự kiện đó chỉ xuất hiện trong block bị gắn cờ.
   Ví dụ `writeBlock … received exception … Connection reset by peer`.
5. **Mô hình** (`/models`): KMeans Precision 0,889 / Recall 0,923 / **F1 0,906**; Isolation Forest F1 0,569; Z-score F1 0,010.
   Chỉ ma trận nhầm lẫn của KMeans: bắt đúng 7.753 trong 8.399 block bất thường thật ở nửa test.

## 3. Kibana (1 phút)
Mở dashboard: 4 con số lớn, biểu đồ WARN theo thời gian, component sinh nhiều WARN nhất (`dfs.DataNode$DataXceiver`), phân bố điểm KMeans theo nhãn thật.
"Cùng dữ liệu trong Elasticsearch, Kibana cho thống kê lỗi và cảnh báo mà không cần viết thêm mã."

## Kết (30 giây)
"Pipeline đi từ HDFS qua Spark đến Elasticsearch, web và Kibana. KMeans đạt F1 0,906 không cần nhãn khi huấn luyện;
Isolation Forest và Z-score là baseline để so sánh."

## Câu hỏi thầy có thể hỏi (trả lời đúng sự thật)
| Câu hỏi | Trả lời |
|---|---|
| Dữ liệu có phải dữ liệu mẫu không? | Không. Đây là toàn bộ HDFS_v1 (11.175.629 dòng, 575.061 block), log thật của LogHub thu từ cụm Hadoop; kết quả do pipeline của nhóm tính. |
| 17.451 có phải số bất thường thật? | Không. Số thật theo nhãn là 16.838. 17.451 là số block KMeans gắn cờ; ngưỡng đặt ở phân vị 97 nên luôn gần 3%. Chất lượng đo bằng Precision/Recall. |
| Mô hình có dùng nhãn khi huấn luyện không? | Không. Học không giám sát. Nhãn chỉ dùng chọn k (nửa val) và chấm điểm (nửa test). Mô hình được fit trên toàn bộ block, kể cả nửa test, nhưng không thấy nhãn. |
| Vì sao Z-score gần như vô dụng? | Z-score đếm dòng WARN/ERROR của block. Trong HDFS_v1 các lỗi như `writeBlock … received exception` được ghi ở mức INFO, và dataset không có ERROR, nên tín hiệu rất yếu. |
| Sao 54 mẫu sự kiện mà LogHub liệt kê 29? | Bộ che template của nhóm (regex) còn tách nhỏ hơn bản tham chiếu. Không làm sai kết quả nhưng chưa gộp tối ưu. |
| Chạy Spark có phân tán thật không? | Chạy trên cụm Spark standalone trong Docker nhưng chỉ có 1 worker trên 1 máy, nên là mô phỏng cụm, không phải nhiều máy thật. |
| HDFS có nhân bản không? | Cụm demo chỉ có 1 datanode nên không có bản sao. |
| Web đọc từ HDFS hay Elasticsearch? | Từ Elasticsearch. HDFS lưu dữ liệu thô và trung gian của Spark; Elasticsearch lưu kết quả để truy vấn. |
| Trang Nhật ký có đủ 11 triệu dòng không? | Không. Có dòng WARN và mọi dòng của block bị gắn cờ (~760 nghìn dòng). Hơn 10 triệu dòng INFO của block bình thường không nạp. |

## Nếu có sự cố
- Web không lên: `docker compose --profile search up -d api web`, chờ 10 giây.
- Web báo dữ liệu mô phỏng (banner vàng): Elasticsearch chưa lên. Chạy `docker compose --profile search up -d elasticsearch`, đợi healthy, rồi `docker compose restart api`.
- Elasticsearch trống sau khi xóa volume: nạp lại bằng
  `$env:ES_HOST="http://localhost:9200"; $env:LOGAD_SERVING_DIR="data/interim/hdfs_run/serving"; python scripts/run_local_pipeline.py --only 06`
- Kibana chưa có dashboard: `python dashboard/kibana/build_saved_objects.py` rồi import lại (xem `dashboard/kibana/README.md`).
