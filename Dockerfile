FROM node:22-alpine AS frontend-builder

WORKDIR /web

COPY web/package*.json ./
RUN npm ci

COPY web/ ./
RUN npm run build-only


FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY config.clawcloud.example.yaml ./config.clawcloud.example.yaml
COPY --from=frontend-builder /web/dist ./web_dist

RUN mkdir -p /data/logs /data/strm /app/output /app/tmp

EXPOSE 8000

ENV CONFIG_PATH=/data/config.yaml
ENV PORT=8000
ENV WEB_CONCURRENCY=1

CMD ["sh", "-c", "if [ ! -f \"$CONFIG_PATH\" ]; then cp /app/config.clawcloud.example.yaml \"$CONFIG_PATH\"; fi && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1}"]
