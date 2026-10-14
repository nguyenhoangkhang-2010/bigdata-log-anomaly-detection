# Phát hiện bất thường từ nhật ký hệ thống (Đề tài 13 – Nhập môn Big Data)

Pipeline: **LogHub HDFS_v1 → HDFS → Spark (parse, đặc trưng, KMeans/IForest/z-score) → Elasticsearch → API → giao diện web**.

Quy trình phát triển: **API-first** — [`api/openapi.yaml`](api/openapi.yaml) là hợp đồng gốc; backend và frontend cùng bám theo, Docker làm sau.

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
docker-compose.yml   HDFS + Spark + Elasticsearch + Kibana (chưa chạy thử)
```

## Môi trường Anaconda (làm một lần)
Dùng **một env riêng tên `logad`** cho dự án này (đừng dùng chung với `bigdata-transport` hay env khác để khỏi xung đột phiên bản `pyspark`).
[`environment.yml`](environment.yml) cài sẵn Python 3.11, OpenJDK 17 (cho PySpark chạy local) và toàn bộ thư viện của pipeline + backend.

```powershell
cd D:\DaiHoc\HocKy1_Nam4_Nam2026\BigData\project-final
conda env create -f environment.yml      # tạo env "logad" (vài phút, tải khoảng 0,5–1 GB)
conda activate logad
```
Sau này thêm thư viện: sửa `requirements.txt` / `backend/requirements.txt` rồi `conda env update -f environment.yml --prune`.
Muốn xóa để làm lại: `conda env remove -n logad`.

Node.js (cho frontend) dùng bản cài sẵn trên máy (cần Node ≥ 20); không bắt buộc cài trong conda.

## Chạy giao diện + API (không cần Docker, dùng dữ liệu mô phỏng)
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

> Giao diện hiển thị thanh đen **"DỮ LIỆU MÔ PHỎNG"** khi `meta.is_synthetic = true`. Các chỉ số mô hình trong chế độ này
> tính trên dữ liệu mô phỏng nên **không được đưa vào báo cáo**.

## Chạy pipeline Spark (cần Docker)
```powershell
conda activate logad
cp .env.example .env
docker compose up -d                                  # HDFS:9870 Spark:8080 ES:9200 Kibana:5601
python scripts/download_loghub.py --sample            # hoặc bỏ --sample để tải bản đầy đủ
.\scripts\hdfs_put.ps1
.\scripts\submit.ps1 02_parse_logs.py                 # … 03, 04, 05
.\scripts\submit.ps1 06_index_elasticsearch.py -Es
```

## Trạng thái
| Phần | Trạng thái |
|---|---|
| `api/openapi.yaml` (12 endpoint) | ✅ |
| Backend FastAPI + 17 test (gồm test hợp đồng) | ✅ chạy với dữ liệu mô phỏng |
| `ElasticsearchRepository` | ⬜ chưa cài đặt – chờ pipeline có kết quả thật |
| Frontend 6 trang + chi tiết block, sáng/tối, responsive | ✅ đã kiểm tra bằng ảnh chụp (desktop, 390px, chế độ tối) |
| `parsing.py` + test | ✅ |
| `features`, `models/*`, `evaluation`, `es_sink` (pipeline Spark) | ⬜ stub + TODO |
| `docker-compose.yml`, `scripts/*` | 🟡 viết, **chưa pull image / chạy thử** |
| Docker hóa backend + frontend | ⬜ bước tiếp theo |
| `docs/*` | 🟡 dàn ý, điền dần |

Kế hoạch: [docs/02-ke-hoach-10-tuan.md](docs/02-ke-hoach-10-tuan.md).
