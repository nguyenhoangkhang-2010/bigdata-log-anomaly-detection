# Dữ liệu

| Thư mục | Nội dung |
|---|---|
| `raw/` | Dữ liệu gốc tải về (không commit). `HDFS_v1/HDFS.log`, `HDFS_v1/preprocessed/anomaly_label.csv` |
| `interim/` | Kết quả trung gian chạy local (mẫu nhỏ để thử) |
| `processed/` | Bảng metric, ảnh biểu đồ xuất ra cho báo cáo |

## Nguồn

**LogHub – HDFS_v1** (https://github.com/logpai/loghub, bản ghi Zenodo):
- ~11.2 triệu dòng log, ~1.5 GB, thu thập từ cụm Hadoop 200+ node trên Amazon EC2.
- Gom theo `block_id`: ~575 nghìn block, ~16,8 nghìn block bất thường (~2,9 %) đã gán nhãn bởi chuyên gia.
- `anomaly_label.csv`: `BlockId,Label` (`Normal` / `Anomaly`).

> Các số liệu trên lấy từ mô tả công bố của LogHub/DeepLog – **kiểm tra lại sau khi tải** và ghi số đo thật vào báo cáo.

## Tải

```bash
python scripts/download_loghub.py --sample   # 2k dòng để thử parser
python scripts/download_loghub.py            # bản đầy đủ
```

Dự phòng nếu cần thêm dữ liệu: `BGL`, `Thunderbird`, `OpenStack` (cùng LogHub) để thử khái quát hóa.
