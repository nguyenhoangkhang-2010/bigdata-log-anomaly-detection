# Submit 1 job Spark lên cụm trong Docker (driver chạy trong container spark-master; src/ jobs/ configs/ data/ đã mount).
# Dùng:  .\scripts\submit.ps1 02_parse_logs.py
#        $env:LOGAD_SERVING_DIR = "data/interim/hdfs_run/serving"; .\scripts\submit.ps1 07_export_serving.py
# Bộ nhớ: worker 8g (SPARK_WORKER_MEMORY), executor 7g, driver 4g. Chỉnh bằng biến môi trường SPARK_EXECUTOR_MEMORY / SPARK_DRIVER_MEMORY.
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Job
)
$ErrorActionPreference = "Stop"

$execMem = if ($env:SPARK_EXECUTOR_MEMORY) { $env:SPARK_EXECUTOR_MEMORY } else { "7g" }
$drvMem = if ($env:SPARK_DRIVER_MEMORY) { $env:SPARK_DRIVER_MEMORY } else { "4g" }
$envArgs = @()
if ($env:LOGAD_SERVING_DIR) { $envArgs += @("-e", "LOGAD_SERVING_DIR=$($env:LOGAD_SERVING_DIR)") }

# dfs.replication=1: cụm demo chỉ có 1 datanode, ghi 1 bản sao để HDFS không báo under-replicated.
# Spark ghi log ra stderr; Windows PowerShell 5.1 coi mỗi dòng stderr của lệnh ngoài là lỗi, nên hạ mức cảnh báo và in dạng chuỗi thường
$ErrorActionPreference = "Continue"
docker exec @envArgs -w /opt/project logad-spark-master /opt/spark/bin/spark-submit `
    --master spark://spark-master:7077 `
    --driver-memory $drvMem --executor-memory $execMem --conf spark.driver.maxResultSize=0 `
    --conf spark.hadoop.dfs.replication=1 `
    /opt/project/jobs/$Job 2>&1 | ForEach-Object { "$_" }
if ($LASTEXITCODE -ne 0) { throw "Job $Job lỗi (mã $LASTEXITCODE)" }
