# Phát hiện bất thường từ nhật ký hệ thống (Đề tài 13 – Nhập môn Big Data)

Pipeline: **LogHub HDFS_v1 → Spark (parse, đặc trưng, KMeans/IForest/z-score) → Elasticsearch (lưu trữ) → API → giao diện web**.

Lưu trữ: đề bài cho chọn **HDFS hoặc Elasticsearch**; dự án chọn **Elasticsearch** làm nơi lưu kết quả (575.061 block, 763.904 dòng log, thống kê lỗi, đột biến, mẫu sự kiện). Trung gian giữa các bước Spark là Parquet trên đĩa.

Quy trình phát triển: **API-first** — [`api/openapi.yaml`](api/openapi.yaml) là hợp đồng gốc; backend và frontend cùng bám theo; Docker đóng gói ứng dụng (api + web) và hạ tầng Big Data.

## Cấu trúc thư mục
```
api/openapi.yaml  hợp đồng API (nguồn sự thật duy nhất)
backend/          FastAPI: schemas, routes, repositories (demo | files | elasticsearch), test hợp đồng
frontend/         React + Vite + TypeScript, kiểu API sinh từ openapi.yaml
configs/          pipeline.yaml – cấu hình pipeline Spark
src/logad/        thư viện pipeline: parsing, features, models/, evaluation, es_sink
jobs/             6 job Spark theo thứ tự 01 → 06 (mỗi job có run(spark, cfg) và chạy được bằng spark-submit)
scripts/          tải dữ liệu, chạy pipeline trên máy, sinh dữ liệu mô phỏng có nhãn, đẩy HDFS, submit job
dashboard/        Kibana: index template + saved objects (phương án phụ)
data/ notebooks/ tests/ docs/ models/
docker-compose.yml   api + web (mặc định) · profile bigdata: HDFS + Spark · profile search: Elasticsearch + Kibana
*/Dockerfile         backend/Dockerfile, frontend/Dockerfile (+ nginx.conf)
```

## Môi trường Anaconda (làm một lần)
Dùng **một env riêng tên `logad`** cho dự án này (đừng dùng chung với `bigdata-transport` hay env khác để khỏi xung đột phiên bản `pyspark`).
[`environment.yml`](environment.yml) cài Python 3.11 và OpenJDK 17 (cho PySpark chạy local); thư viện Python cài bằng pip ở bước 2.
Làm trong **Anaconda Prompt**, tại thư mục gốc dự án:

```bat
cd /d D:\DaiHoc\HocKy1_Nam4_Nam2026\BigData\bigdata-log-anomaly-detection
conda env create -f environment.yml                                  &:: bước 1: tạo env "logad"
conda activate logad
pip install -r requirements.txt -r backend/requirements-dev.txt     &:: bước 2: ~0,5 GB (pyspark ~320 MB)
```
Tách hai bước vì nếu để conda tự gọi pip lúc tạo env, trên Windows có thể lỗi `gzip module is not available`.
Thêm thư viện về sau: sửa `requirements.txt` (pipeline) hoặc `backend/requirements.txt` (thư viện chạy backend, cũng là thứ vào image Docker) / `backend/requirements-dev.txt` (test, lint), rồi chạy lại lệnh `pip install` ở bước 2.
Muốn làm lại từ đầu: `conda env remove -n logad`.

Chạy Spark local trên Windows: dùng `get_spark(cfg, local=True)` (đã tự trỏ `PYSPARK_PYTHON` về Python của env).
Cảnh báo `winutils.exe` khi chạy Spark là vô hại, bỏ qua được.

Node.js (cho frontend) dùng bản cài sẵn trên máy (cần Node ≥ 20); không bắt buộc cài trong conda.

## Chạy bằng Docker (một lệnh, dùng dữ liệu mô phỏng)
Cần Docker Desktop đang chạy.
```bat
docker compose up -d --build                  &:: giao diện http://localhost:3000 · Swagger http://localhost:8000/docs
docker compose down                           &:: dừng
```
Mặc định chỉ bật **api + web** (nhẹ). Nếu cổng 8000 đang bị uvicorn local giữ, đổi cổng: `set API_PORT=8010` trước lệnh `docker compose` (hoặc ghi vào `.env`, xem `.env.example`).
Web được phục vụ bằng nginx (chạy không phải root) và tự chuyển `/api` sang backend, nên không cần cấu hình CORS.

## Chạy giao diện + API không dùng Docker (dùng dữ liệu mô phỏng)
```powershell
# terminal 1 – backend (đã `conda activate logad`)
cd backend
python -m uvicorn app.main:app --reload --port 8000     # docs: http://localhost:8000/docs

# terminal 2 – frontend
cd frontend
npm install
npm run dev                                              # http://localhost:5173
```
Test: `cd backend; python -m pytest -q` · `cd frontend; npm run typecheck; npm run build`

Trong VS Code: `Ctrl+Shift+P` → *Python: Select Interpreter* → chọn `logad`.

> Giao diện hiển thị dải xanh **"Dữ liệu mô phỏng"** ở đầu trang khi `meta.is_synthetic = true`. Các chỉ số mô hình trong chế độ này
> tính trên dữ liệu mô phỏng nên **không được đưa vào báo cáo**.

## Chạy pipeline trên máy (Spark local, không cần Docker/HDFS)
```bat
conda activate logad
python scripts/download_loghub.py --sample         &:: bản mẫu thật 2.000 dòng (không nhãn)
python scripts/run_local_pipeline.py               &:: chạy 02 → 05 + 07, kết quả ở data/interim/logad
python scripts/run_local_pipeline.py --synthetic   &:: dữ liệu MÔ PHỎNG có nhãn: để kiểm tra cả bước đánh giá (số liệu không dùng cho báo cáo)
python scripts/run_local_pipeline.py --only 04,05  &:: chỉ chạy một số bước
```
Có bản đầy đủ thì tự dùng: `data/raw/HDFS.log` + `data/raw/preprocessed/anomaly_label.csv` (đường dẫn trong `configs/pipeline.yaml`; chạy thử nhanh bằng `dataset.sample_lines`).
Trên **Windows**, Spark không ghi được file nếu thiếu `winutils`, nên `logad/storage.py` cho từng partition tự ghi parquet bằng pyarrow (không kéo dữ liệu về driver).
Bộ nhớ driver/số lõi chỉnh trong `spark.local_*` của `configs/pipeline.yaml`.

**Xem kết quả thật trên giao diện.** Bước 07 gom kết quả thành tệp nhỏ ở `data/interim/logad/results/serving`. Từ đó có hai đường:
```bat
docker compose --profile search up -d --build elasticsearch api web   &:: bật Elasticsearch + api + web (http://localhost:3000)
set ES_HOST=http://localhost:9200
python scripts/run_local_pipeline.py --only 06                        &:: nạp serving vào Elasticsearch (~85 giây, 575k block + 764k dòng log)
```
Backend ở chế độ `auto` (mặc định) chọn nguồn theo thứ tự: **Elasticsearch có dữ liệu → tệp serving → dữ liệu mô phỏng**; xem `/api/v1/health` để biết đang dùng nguồn nào.
Không có Elasticsearch thì vẫn xem được bằng tệp serving. Banner "dữ liệu mô phỏng" chỉ hiện khi rơi về dữ liệu mô phỏng.

**Quy trình đánh giá:** các mô hình học KHÔNG giám sát. Nhãn chỉ dùng để (1) chọn k của KMeans trên nửa `val` của các block và
(2) chấm điểm trên nửa `test` còn lại (chia cố định theo băm `block_id`, xem `logad/splits.py`). Chưa có nhãn thì dùng `k_default`.

## Chạy pipeline Spark trong cụm Docker (nặng: vài GB image)
> Chưa kiểm thử: image `apache/spark:3.5.3-python3` chưa có pandas, pyarrow, scikit-learn, elasticsearch mà job 04 và 06 cần,
> nên cần dựng image Spark riêng (việc của nhánh `feat/infra-docker`) trước khi chạy cụm.

```powershell
conda activate logad
cp .env.example .env
docker compose --profile bigdata --profile search up -d   # HDFS:9870 Spark:8080 ES:9200 Kibana:5601 (cùng api + web)
python scripts/download_loghub.py --sample            # hoặc bỏ --sample để tải bản đầy đủ
.\scripts\hdfs_put.ps1
.\scripts\submit.ps1 02_parse_logs.py                 # … 03, 04, 05
.\scripts\submit.ps1 06_index_elasticsearch.py -Es
```

## Trạng thái
| Phần | Trạng thái |
|---|---|
| `api/openapi.yaml` (12 endpoint) | ✅ |
| Backend FastAPI + 53 test (gồm test hợp đồng) | ✅ |
| `ElasticsearchRepository` (+ `FilesRepository`) | ✅ 13 endpoint, test chạy trên Elasticsearch thật; đã đối chiếu kết quả với bản đọc tệp trên dữ liệu đầy đủ |
| Frontend 6 trang + chi tiết block, sáng/tối, responsive, xuất CSV | ✅ đã kiểm tra bằng ảnh chụp (desktop, 390px, chế độ tối) |
| Pipeline Spark 02→05: parse, đặc trưng, KMeans/Isolation Forest/z-score, đánh giá (+ 40 test) | ✅ chạy xuyên suốt ở chế độ local trên bản mẫu thật và dữ liệu mô phỏng có nhãn |
| Bộ che template: 192 → 14 template trên bản mẫu thật (LogHub gốc: 29 cho toàn bộ HDFS_v1) | ✅ có test đối chiếu |
| Job 06 + `es_load` (nạp vào Elasticsearch) | ✅ đã nạp dữ liệu đầy đủ (575.061 block, 763.904 dòng log) vào Elasticsearch 8.15 thật |
| Pipeline trên dữ liệu đầy đủ HDFS_v1 (11,2 triệu dòng) | ✅ chạy local ~7 phút. Chạy trong cụm Docker/HDFS: ⬜ không làm (đề cho chọn HDFS hoặc Elasticsearch) |
| Docker: api + web (build, chạy, healthcheck, proxy nginx) | ✅ đã build và chạy thử |
| Docker: Elasticsearch | ✅ chạy, healthcheck, web đọc từ đây |
| Docker: HDFS, Spark, Kibana | ⬜ chưa chạy thử (không bắt buộc) |
| `scripts/*` | 🟡 viết, chưa chạy thử trên cụm |
| `docs/*` | 🟡 dàn ý, điền dần |

Kế hoạch: [docs/02-ke-hoach-10-tuan.md](docs/02-ke-hoach-10-tuan.md).
