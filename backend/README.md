# Backend (FastAPI)

Hợp đồng API: [`../api/openapi.yaml`](../api/openapi.yaml) (viết trước, hai phía cùng bám).

Dùng env Anaconda `logad` (tạo từ `environment.yml` ở thư mục gốc, xem README gốc):

```bash
conda activate logad
python -m uvicorn app.main:app --reload --port 8000    # http://localhost:8000/docs
python -m pytest -q                                     # 17 test, gồm test hợp đồng
```

## Nguồn dữ liệu (`LOGAD_DATA_SOURCE`)
| Giá trị | Ý nghĩa |
|---|---|
| `demo` (mặc định) | Dữ liệu **mô phỏng** theo hình dạng HDFS_v1, tính điểm bằng numpy. `meta.is_synthetic = true`. |
| `elasticsearch` | Đọc kết quả thật từ pipeline Spark. **Chưa cài đặt** — xem `app/repositories/elastic.py` (có bản đồ index → endpoint). |

Router chỉ phụ thuộc `Repository` (`app/repositories/base.py`), nên chuyển sang dữ liệu thật không phải sửa API.

## Test hợp đồng
`tests/test_contract.py` kiểm tra: cùng tập route/operationId/tham số, cùng thuộc tính + `required` + enum của schema,
và phản hồi thật của từng endpoint hợp lệ với schema trong `openapi.yaml`. Đổi API → sửa `openapi.yaml` trước.
