# Chạy cả pipeline trên cụm Docker: dữ liệu thô, trung gian và kết quả nằm trên HDFS.
#   docker compose --profile bigdata up -d --build
#   .\scripts\run_cluster_pipeline.ps1
# Tệp phục vụ cho backend (job 07) ghi ra data/interim/hdfs_run/serving; nạp vào Elasticsearch bằng job 06 (chạy trên máy).
param([string]$Jobs = "01_ingest_to_hdfs.py,02_parse_logs.py,03_extract_features.py,04_detect_anomalies.py,05_evaluate.py,07_export_serving.py")
$ErrorActionPreference = "Stop"
if (-not $env:LOGAD_SERVING_DIR) { $env:LOGAD_SERVING_DIR = "data/interim/hdfs_run/serving" }

$t0 = Get-Date
foreach ($j in $Jobs.Split(",")) {
    $t = Get-Date
    Write-Host "=== $j ===" -ForegroundColor Cyan
    & "$PSScriptRoot\submit.ps1" $j
    Write-Host ("    ({0:N0} giây)" -f ((Get-Date) - $t).TotalSeconds)
}
Write-Host ("Xong trong {0:N0} giây" -f ((Get-Date) - $t0).TotalSeconds) -ForegroundColor Green
