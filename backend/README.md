# Backend (FastAPI)

Hợp đồng API: [`../api/openapi.yaml`](../api/openapi.yaml) (viết trước, hai phía cùng bám).

Dùng env Anaconda `logad` (tạo từ `environment.yml` ở thư mục gốc, xem README gốc):

```bash
conda activate logad
python -m uvicorn app.main:app --reload --port 8000    # http://localhost:8000/docs
python -m pytest -q                                     # 31 test, gồm test hợp đồng
ruff check .                                            # lint (cấu hình ở ruff.toml)
```

Cần **Python ≥ 3.11** (code dùng `datetime.UTC`); env `logad` đã là 3.11.

## Thư viện và Docker
- `requirements.txt`: chỉ thư viện **chạy** backend; đây cũng là thứ duy nhất được cài vào image Docker.
- `requirements-dev.txt`: thêm pytest, httpx, jsonschema, ruff… cho phát triển (env `logad` cài file này).
- `Dockerfile`: Python 3.12-slim, chạy bằng user thường (uid 10001), có `HEALTHCHECK` gọi `/api/v1/health`.
  Build từ **thư mục gốc dự án**: `docker build -f backend/Dockerfile -t logad-api .` (hoặc `docker compose up -d --build`).

## Endpoint
Danh sách đầy đủ nằm trong `../api/openapi.yaml` và trang `/docs` khi chạy. Có thêm
`GET /api/v1/anomalies/export` (CSV, cùng bộ lọc với danh sách, tối đa `limit` dòng, mặc định 1000).
Route này khai báo **trước** `/anomalies/{block_id}` trong `app/routes.py`, đừng đổi thứ tự.

## Nguồn dữ liệu (`LOGAD_DATA_SOURCE`)
| Giá trị | Ý nghĩa |
|---|---|
| `auto` (mặc định) | Elasticsearch có dữ liệu → `files` (thư mục serving) → `demo`. |
| `demo` | Dữ liệu **mô phỏng** theo hình dạng HDFS_v1, tính điểm bằng numpy. `meta.is_synthetic = true`. |
| `files` | Đọc **kết quả thật** của pipeline từ thư mục do job 07 xuất (`LOGAD_SERVING_DIR`, mặc định `data/interim/logad/results/serving`). Không cần Elasticsearch. Cần `pandas`, `pyarrow`. |
| `elasticsearch` | Đọc kết quả thật từ Elasticsearch (`LOGAD_ELASTICSEARCH_URL`, prefix index `LOGAD_ES_INDEX_PREFIX`, mặc định `logad`). Bản đồ index → endpoint ở đầu `app/repositories/elastic.py`. Test chạy trên Elasticsearch thật và tự bỏ qua nếu không có. |

Router chỉ phụ thuộc `Repository` (`app/repositories/base.py`), nên chuyển sang dữ liệu thật không phải sửa API.

## Test hợp đồng
`tests/test_contract.py` kiểm tra: cùng tập route/operationId/tham số, cùng thuộc tính + `required` + enum của schema,
và phản hồi thật của từng endpoint hợp lệ với schema trong `openapi.yaml`. Đổi API → sửa `openapi.yaml` trước.
