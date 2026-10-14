# Đưa dữ liệu thô lên HDFS (chạy sau khi `docker compose up -d` và namenode đã sẵn sàng)
# Dùng:  .\scripts\hdfs_put.ps1
$ErrorActionPreference = "Stop"

docker exec logad-namenode hdfs dfs -mkdir -p /logad/raw
docker exec logad-namenode hdfs dfs -put -f /data/raw/HDFS_v1/HDFS.log /logad/raw/HDFS.log
docker exec logad-namenode hdfs dfs -put -f /data/raw/HDFS_v1/preprocessed/anomaly_label.csv /logad/raw/anomaly_label.csv
docker exec logad-namenode hdfs dfs -ls -h /logad/raw
