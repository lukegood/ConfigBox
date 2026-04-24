FROM node:22-alpine AS frontend

WORKDIR /ui
ARG NPM_REGISTRY=https://registry.npmmirror.com
COPY frontend/package*.json ./
RUN npm config set registry ${NPM_REGISTRY} \
    && npm ci --no-audit --no-fund
COPY frontend ./
RUN npm run build

FROM python:3.12-slim AS backend

ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --timeout 120 -i ${PIP_INDEX_URL} -r requirements.txt

COPY app ./app
COPY --from=frontend /ui/dist ./app/static

RUN mkdir -p /data /config/claude /config/codex \
    && chmod -R a+rX /app \
    && chmod -R 0777 /data /config

USER 1000:1000

EXPOSE 8787

CMD ["python", "-m", "app.main"]
