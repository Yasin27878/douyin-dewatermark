# 多阶段构建：Node 编译前端 → Python 运行时托管（单容器、单 Origin）。

# --- 阶段 1：构建前端 ---
FROM node:20-alpine AS fe
WORKDIR /fe
# 先只拷依赖清单，命中 Docker 层缓存（package*.json 不变则不重装）。
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- 阶段 2：后端运行时 ---
FROM python:3.12-slim AS app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FRONTEND_DIST=/app/frontend/dist \
    AUTH_PASSWORD=""
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=fe /fe/dist ./frontend/dist

EXPOSE 8182

# 自带健康检查（slim 镜像无 curl，用 python 打 /api/health）。
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8182/api/health', timeout=3).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8182"]
