# Dữ liệu

| Thư mục | Nội dung |
|---|---|
| `raw/` | Dữ liệu gốc tải về (không commit). `HDFS.log`, `preprocessed/anomaly_label.csv` |
| `interim/` | Kết quả trung gian và tệp phục vụ: `logad/` (chạy local), `hdfs_run/serving/` (chạy trên cụm), `synthetic*/` (dữ liệu mô phỏng để thử code) |
| `processed/` | Bảng metric, ảnh biểu đồ xuất ra cho báo cáo |

## Nguồn

**LogHub – HDFS_v1** (https://github.com/logpai/loghub, bản ghi Zenodo):
- 11.175.629 dòng log, 1,58 GB (đã đếm trên bản tải về). Theo README của chính LogHub: sinh ra trong một private cloud chạy các workload benchmark,
  được gán nhãn thủ công bằng luật viết tay.
- Gom theo `block_id`: 575.061 block, 16.838 block bất thường (2,93 %), đã đếm từ `anomaly_label.csv`.
- `anomaly_label.csv`: `BlockId,Label` (`Normal` / `Anomaly`).

> Các số trên đã kiểm tra bằng cách đếm trực tiếp trên dữ liệu đã tải.

## Tải

```bash
python scripts/download_loghub.py --sample   # 2k dòng để thử parser
python scripts/download_loghub.py            # bản đầy đủ
```

Dự phòng nếu cần thêm dữ liệu: `BGL`, `Thunderbird`, `OpenStack` (cùng LogHub) để thử khái quát hóa.
