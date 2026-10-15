# Frontend React: build tĩnh rồi phục vụ bằng nginx (không chạy root), proxy /api sang backend.
# Build từ thư mục gốc dự án (cần api/openapi.yaml để sinh kiểu TypeScript):
#   docker build -f frontend/Dockerfile -t logad-web .

# ── giai đoạn 1: build ──
FROM node:22-alpine AS build
WORKDIR /app

# cài thư viện trước để tận dụng cache
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci

# hợp đồng API + mã nguồn; `npm run build` tự chạy gen:api (prebuild) rồi tsc + vite build
COPY api ./api
COPY frontend ./frontend
RUN cd frontend && npm run build

# ── giai đoạn 2: phục vụ ──
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=4s --start-period=10s --retries=5 \
    CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
