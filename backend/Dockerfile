# Backend FastAPI. Build từ thư mục gốc dự án:
#   docker build -f backend/Dockerfile -t logad-api .
# (context là thư mục gốc để image có thể mang theo api/openapi.yaml làm tài liệu hợp đồng)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# cài thư viện trước để tận dụng cache layer khi chỉ sửa code
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/app ./app
COPY api/openapi.yaml ./api/openapi.yaml

# chạy bằng user thường, không dùng root
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

ENV LOGAD_DATA_SOURCE=auto
ENV LOGAD_SERVING_DIR=/data/serving

EXPOSE 8000

# bộ dữ liệu mô phỏng dựng khi khởi động (~4 giây) nên cho thời gian chờ rộng
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
