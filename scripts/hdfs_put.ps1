# Đưa dữ liệu thô lên HDFS (chạy sau khi `docker compose --profile bigdata up -d` và namenode đã sẵn sàng)
# Dùng:  .\scripts\hdfs_put.ps1            # bản đầy đủ data/raw/HDFS.log (nếu chưa có thì dùng data/raw/HDFS_2k.log)
# Thư mục ./data của máy được mount (chỉ đọc) vào namenode tại /data.
$ErrorActionPreference = "Stop"

$full = Test-Path "data/raw/HDFS.log"
$raw = if ($full) { "/data/raw/HDFS.log" } else { "/data/raw/HDFS_2k.log" }
docker exec logad-namenode hdfs dfs -mkdir -p /logad/raw
docker exec logad-namenode hdfs dfs -put -f $raw /logad/raw/HDFS.log
if (Test-Path "data/raw/preprocessed/anomaly_label.csv") {
    docker exec logad-namenode hdfs dfs -put -f /data/raw/preprocessed/anomaly_label.csv /logad/raw/anomaly_label.csv
}
docker exec logad-namenode hdfs dfs -ls -h /logad/raw
