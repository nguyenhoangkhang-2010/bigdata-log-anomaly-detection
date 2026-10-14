# Submit 1 job Spark lên cụm trong Docker (src/ đã mount vào /opt/project/src, PYTHONPATH đã set).
# Dùng:  .\scripts\submit.ps1 02_parse_logs.py
#        .\scripts\submit.ps1 06_index_elasticsearch.py -Es    # thêm connector Elasticsearch
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Job,
    [switch]$Es
)
$ErrorActionPreference = "Stop"

$args2 = @("exec", "-w", "/opt/project", "logad-spark-master",
           "/opt/spark/bin/spark-submit", "--master", "spark://spark-master:7077")
if ($Es) { $args2 += @("--packages", "org.elasticsearch:elasticsearch-spark-30_2.12:8.15.3") }
$args2 += "/opt/project/jobs/$Job"

docker @args2
