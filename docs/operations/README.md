# 运维文档

## 部署指南

### Docker 部署（推荐）

#### 前置要求

- Docker 20.10+
- Docker Compose 2.0+

#### 快速启动

```bash
# 1. 克隆仓库
git clone <repository-url>
cd quark_strm

# 2. 准备运行时文件
cp .env.example .env
cp config.example.yaml config.yaml

# 3. 编辑 .env / config.yaml 填入必要配置
# 至少按需设置 SMART_MEDIA_QUARK_COOKIE、SMART_MEDIA_EMBY_URL、
# SMART_MEDIA_EMBY_API_KEY 等真实凭据

# 4. 启动服务
docker compose up -d

# 5. 查看日志
docker compose logs -f

# 6. 停止服务
docker compose down
```

#### 启用监控栈

```bash
docker compose --profile monitoring up -d
```

#### 更新镜像

```bash
docker compose pull
docker compose up -d
```

#### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `QUARK_STRM_IMAGE` | 部署镜像标签 | `ghcr.io/242282218/smart_media/quark-strm:latest` |
| `SMART_MEDIA_EMBY_PROXY_PORT` | Emby 专用代理暴露端口 | `18097` |
| `SMART_MEDIA_LOG_FORMAT` | 容器日志格式 | `json` |
| `SMART_MEDIA_LOG_LEVEL` | 应用日志级别 | `INFO` |
| `TZ` | 容器时区 | `Asia/Shanghai` |

#### Compose 挂载约定

- `./config.yaml:/app/config.yaml`
- `./quark_strm.db:/app/quark_strm.db`
- `./strm:/app/strm`
- `./logs:/app/logs`

容器内始终通过 `CONFIG_PATH=/app/config.yaml` 读取配置，敏感值优先使用 `.env` 覆盖 `config.yaml`。

### 源码部署

#### 后端部署

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 初始化数据库
python -c "from app.core.db import init_db; init_db()"

# 3. 启动服务（生产环境）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# 4. 使用 Gunicorn（可选）
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

#### 前端部署

```bash
# 1. 构建前端
cd web
npm install
npm run build

# 2. 配置 Nginx
# 将 dist/ 目录部署到 Nginx
```

#### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /path/to/web/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # WebSocket 支持
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 监控与告警

### 健康检查端点

| 端点 | 说明 |
|------|------|
| `/health` | 综合健康状态（包含启动告警与组件状态） |
| `/health/live` | 存活探针 |
| `/health/ready` | 就绪探针 |
| `/ready` | 就绪探针别名（Docker healthcheck 使用此端点） |
| `/metrics` | Prometheus 指标 |

### Prometheus 配置示例

```yaml
scrape_configs:
  - job_name: 'quark_strm'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### Grafana 仪表盘

导入仪表盘配置（待补充）：
- 系统资源监控
- API 请求延迟
- 错误率统计
- 任务执行状态

## 日志管理

### 日志配置

```yaml
# config.yaml
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: json  # json, text
  output: file  # file, stdout
  file:
    path: logs/app.log
    max_size: 100MB
    backup_count: 7
```

### 日志位置

| 环境 | 日志路径 |
|------|----------|
| Docker | `/app/logs/` |
| 源码部署 | `./logs/` |

### 日志分析

```bash
# 查看错误日志
tail -f logs/app.log | grep ERROR

# 统计错误数量
grep -c ERROR logs/app.log

# 使用 jq 分析 JSON 日志
cat logs/app.log | jq 'select(.level == "ERROR")'
```

## 备份与恢复

### 数据库备份

```bash
# 备份 SQLite 数据库
cp quark_strm.db quark_strm.db.backup.$(date +%Y%m%d)

# 压缩备份
tar -czf quark_strm.backup.$(date +%Y%m%d).tar.gz quark_strm.db config.yaml
```

### 配置备份

```bash
# 备份配置文件
cp config.yaml config.yaml.backup.$(date +%Y%m%d)
```

### 恢复流程

```bash
# 1. 停止服务
docker compose down

# 2. 恢复数据库
cp quark_strm.db.backup.* quark_strm.db

# 3. 恢复配置
cp config.yaml.backup.* config.yaml

# 4. 重启服务
docker compose up -d
```

## 性能调优

### 数据库优化

```bash
# 分析慢查询
sqlite3 quark_strm.db "PRAGMA query_optimizer_statistics;"

# 重建索引
sqlite3 quark_strm.db "REINDEX;"
```

### 连接池配置

```python
# app/config/settings.py
DATABASE_POOL_SIZE = 10      # 连接池大小
DATABASE_MAX_OVERFLOW = 20   # 最大溢出连接数
DATABASE_POOL_TIMEOUT = 30   # 超时时间（秒）
```

## 常见问题

### 服务无法启动

```bash
# 检查端口占用
netstat -tulpn | grep 8000

# 检查日志
docker compose logs app

# 检查配置
python -c "from app.config.settings import settings; print(settings)"
```

### 数据库锁定

```bash
# SQLite 锁定时的解决方案
# 1. 停止所有写入操作
# 2. 等待事务完成
# 3. 必要时重启服务
```

## 待办事项

- [ ] 补充 Grafana 仪表盘配置
- [ ] 添加自动化备份脚本
- [ ] 补充扩容指南
- [ ] 添加灾难恢复流程

## 参考链接

- [架构文档](../architecture/README.md)
- [开发文档](../development/README.md)
- [API 文档](../api/README.md)
