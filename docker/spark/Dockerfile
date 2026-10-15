# Spark cho pipeline LogAD: image chính thức + các thư viện Python mà job 02-07 cần
# (pandas_udf của KMeans cần pandas/pyarrow trên MỌI executor; Isolation Forest cần scikit-learn ở driver).
#   docker build -f docker/spark/Dockerfile -t logad-spark:dev .
FROM apache/spark:3.5.3-python3

USER root
RUN python3 -m pip install --no-cache-dir "numpy<2" "pandas>=2.0,<2.3" "pyarrow>=14,<18" scikit-learn pyyaml "elasticsearch>=8.15,<9" \
    && mkdir -p /opt/project && chown spark:spark /opt/project
USER spark
WORKDIR /opt/project
