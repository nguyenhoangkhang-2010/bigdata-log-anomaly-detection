# Phát hiện bất thường từ nhật ký hệ thống (Đề tài 13 – Nhập môn Big Data)

Pipeline: **LogHub HDFS_v1 → HDFS → Spark (parse, đặc trưng, KMeans/IForest/z-score) → Elasticsearch → API → giao diện web**.

Quy trình phát triển: **API-first** — [`api/openapi.yaml`](api/openapi.yaml) là hợp đồng gốc; backend và frontend cùng bám theo; Docker đóng gói ứng dụng (api + web) và hạ tầng Big Data.

## Cấu trúc thư mục
```
api/openapi.yaml  hợp đồng API (nguồn sự thật duy nhất)
backend/          FastAPI: schemas, routes, repositories (demo | elasticsearch), test hợp đồng
frontend/         React + Vite + TypeScript, kiểu API sinh từ openapi.yaml
configs/          pipeline.yaml – cấu hình pipeline Spark
src/logad/        thư viện pipeline: parsing, features, models/, evaluation, es_sink
jobs/             6 job Spark theo thứ tự 01 → 06
scripts/          tải dữ liệu, đẩy lên HDFS, submit job
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

## Chạy pipeline Spark (cần Docker, nặng: vài GB image)
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
| Backend FastAPI + 31 test (gồm test hợp đồng) | ✅ chạy với dữ liệu mô phỏng |
| `ElasticsearchRepository` | ⬜ chưa cài đặt – chờ pipeline có kết quả thật |
| Frontend 6 trang + chi tiết block, sáng/tối, responsive, xuất CSV | ✅ đã kiểm tra bằng ảnh chụp (desktop, 390px, chế độ tối) |
| `parsing.py` + test | ✅ |
| `features`, `models/*`, `evaluation`, `es_sink` (pipeline Spark) | ⬜ stub + TODO |
| Docker: api + web (build, chạy, healthcheck, proxy nginx) | ✅ đã build và chạy thử |
| Docker: HDFS, Spark, Elasticsearch, Kibana | 🟡 tag image đã xác minh tồn tại, **chưa pull/chạy thử** |
| `scripts/*` | 🟡 viết, chưa chạy thử trên cụm |
| `docs/*` | 🟡 dàn ý, điền dần |

Kế hoạch: [docs/02-ke-hoach-10-tuan.md](docs/02-ke-hoach-10-tuan.md).
