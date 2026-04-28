# 运维文档

**最后同步**: 2026-04-27
**对应代码目录**: `Dockerfile`、`docker-compose.yml`、`.github/workflows/docker-deploy-test.yml`、`.github/workflows/docker-publish.yml`、`web/`

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
# 至少按需设置 SMART_MEDIA_QUARK_COOKIE、SMART_MEDIA_SECURITY_API_KEY、
# SMART_MEDIA_JWT_SECRET_KEY、SMART_MEDIA_EMBY_URL、SMART_MEDIA_EMBY_API_KEY 等真实凭据
# 生产环境还必须设置 SMART_MEDIA_ENV=production、security.require_api_key=true、
# CORS allow_origins 白名单

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
| `QUARK_STRM_FRONTEND_IMAGE` | 前端 Nginx 镜像标签，启用 `frontend` profile 时使用 | `quark-strm-frontend:local` |
| `SMART_MEDIA_ENV` | 运行环境，生产使用 `production`；兼容 `ENVIRONMENT=production` | `development` |
| `SMART_MEDIA_SECURITY_API_KEY` | 受保护接口的 canonical API Key | `` |
| `SMART_MEDIA_JWT_SECRET_KEY` | JWT 签名密钥，生产必填 | `` |
| `SMART_MEDIA_EMBY_PROXY_PORT` | Emby 专用代理暴露端口 | `18097` |
| `SMART_MEDIA_FRONTEND_PORT` | 前端 Nginx 暴露端口，启用 `frontend` profile 时使用 | `18080` |
| `SMART_MEDIA_LOG_FORMAT` | 容器日志格式 | `json` |
| `SMART_MEDIA_LOG_LEVEL` | 应用日志级别 | `INFO` |
| `TZ` | 容器时区 | `Asia/Shanghai` |

#### 生产安全与单 worker 约束

当前生产基线以单节点、单进程为默认部署形态。SQLite、进程内任务 worker、内存缓存和 WebSocket 连接状态尚未外置到共享存储或独立 worker，因此后端 Docker 镜像默认 `WEB_CONCURRENCY=1`，启动命令默认 `--workers 1`。在外部队列/锁、Redis 缓存和 WebSocket 横向扩展方案完成前，不要通过增加 Uvicorn/Gunicorn worker 做横向扩容。

#### 持久任务 worker

`/api/tasks` 和转存后的自动整理现在只负责创建数据库任务记录，不再依赖 FastAPI `BackgroundTasks` 执行长任务。应用启动时会启动单进程持久 worker，readiness 需要 `task_worker=ok` 才通过。worker 通过数据库 lease 获取任务、写入 heartbeat，并在启动时恢复过期 lease；如果进程崩溃，超时任务会在下次启动后进入 retry 或 failed。

当前 worker 仍运行在同一个后端进程内，只解决“任务脱离请求生命周期”和“崩溃后不永久 running”的问题，不等于已经支持多进程并行消费。多 worker 部署前仍需要外部锁、队列广播和幂等副作用保护。

#### 前端交付拓扑

当前支持的生产前端交付方式是 **Nginx/独立前端容器托管 SPA**。后端容器只负责 API、健康探针、Emby/Jellyfin 代理和 Prometheus 指标，不内置托管 Vue SPA，也不对普通浏览器路径做 SPA fallback。这样可以避免前端路由与 Emby 专用 gateway 的 `/{path:path}` 兜底入口互相遮蔽。

使用 compose 启动前端 profile：

```bash
docker compose --profile frontend up -d
```

访问入口：

- 后端 API 与探针：`http://127.0.0.1:8000`
- 前端 SPA：`http://127.0.0.1:18080`
- Emby 专用代理：`http://127.0.0.1:18097`

前端 Nginx 镜像由 `Dockerfile` 的 `frontend-runtime` target 构建，配置文件是 [`./nginx-spa.conf`](./nginx-spa.conf)。该配置负责托管 `web/dist`，并把 `/api/`、`/ws/`、`/ready`、`/health` 代理回后端服务。

生产环境必须满足以下条件，否则 `/ready` 返回 503，容器 healthcheck 不应变绿：

- `SMART_MEDIA_ENV=production` 或 `ENVIRONMENT=production`
- `security.require_api_key: true`
- `SMART_MEDIA_SECURITY_API_KEY` 或 `security.api_key` 非空
- `SMART_MEDIA_JWT_SECRET_KEY` 或 `security.jwt_secret_key` 非空
- `cors.allow_origins` 使用明确域名白名单，不能包含 `*`

#### Compose 挂载约定

- `./config.yaml:/app/config.yaml`
- `./quark_strm.db:/app/quark_strm.db`
- `./strm:/app/strm`
- `./logs:/app/logs`

容器内始终通过 `CONFIG_PATH=/app/config.yaml` 读取配置，敏感值优先使用 `.env` 覆盖 `config.yaml`。认证密钥推荐使用 `SMART_MEDIA_SECURITY_API_KEY`；历史别名 `SMART_MEDIA_API_KEY` 与 `API_KEY` 仅保留兼容。

#### 本地运行产物目录约定

以下路径属于本地运行、测试或打包产物，应固定留在仓库内的约定位置，并保持未跟踪状态：

| 路径 | 用途 |
|------|------|
| `logs/` | 后端运行日志 |
| `strm/` | 生成的 `.strm` 输出 |
| `cache/` | 本地缓存数据库与中间缓存 |
| `output/` | 手工验证、诊断与临时导出产物 |
| `target/` | 持续优化脚本与覆盖率临时产物 |
| `tmp_wheel/` | 本地打包 wheel 临时目录 |
| `web/playwright-report/` | Playwright HTML 报告 |
| `web/test-results/` | Playwright 测试结果 |
| `.coverage*` | 本地覆盖率文件 |
| `.claude/` | 本地代理/工具状态目录 |

新增本地脚本或验证流程时，优先复用以上边界；如必须引入新产物目录，需同步更新 `.gitignore` 与本文档。

### 源码部署

#### 后端部署

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 初始化数据库
python -c "from app.core.db import init_db; init_db()"

# 3. 启动服务（生产环境，当前默认单 worker）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1

# 4. 使用 Gunicorn（可选，当前仍保持单 worker）
gunicorn app.main:app -w 1 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

#### 前端部署

```bash
# 1. 构建前端 Nginx 镜像
# Dockerfile 内部执行 npm ci 和 npm run build，生成 web/dist 后复制到 Nginx 镜像
docker build --target frontend-runtime -t quark-strm-frontend:local .

# 2. 启动后端 + 前端 profile
docker compose --profile frontend up -d
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

当前仓库的抓取配置示例见 [`../../prometheus.yml`](../../prometheus.yml)，监控入口与资产说明见 [`../monitoring/README.md`](../monitoring/README.md)。

### Grafana 仪表盘

当前已落地仪表盘资产：[`../monitoring/grafana-dashboard.json`](../monitoring/grafana-dashboard.json)  
建议先阅读 [`../monitoring/README.md`](../monitoring/README.md)，再导入仪表盘并校对数据源。

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

### 数据库迁移

数据库使用 SQLite `PRAGMA user_version` 跟踪 schema version。部署升级前先备份，再显式执行 migration；启动阶段也会执行向前 migration，失败会阻断启动和 readiness。

```bash
# 查看并推进到当前 schema version
python -m app.migrations.runner --db quark_strm.db
```

迁移失败时不要手工改 `PRAGMA user_version`。保留现场日志，先从备份恢复到上一版本数据库，再重新执行 migration。

### 数据库备份

不要在 WAL 模式下裸复制 `quark_strm.db`；只复制主文件可能丢失 `quark_strm.db-wal` 中的已提交事务。使用 SQLite online backup：

```bash
# 在线备份 SQLite 数据库，不覆盖已有备份文件
python -m app.migrations.backup backup --db quark_strm.db --out-dir backups

# 备份配置文件和 STRM 产物
cp config.yaml "backups/config.$(date +%Y%m%dT%H%M%S).yaml"
tar -czf "backups/strm.$(date +%Y%m%dT%H%M%S).tar.gz" strm
```

### 配置备份

```bash
# 备份配置文件，不覆盖已有文件
cp -n config.yaml "backups/config.$(date +%Y%m%dT%H%M%S).yaml"
```

### 恢复流程

```bash
# 1. 停止服务
docker compose down

# 2. 保留当前库现场
mv quark_strm.db "quark_strm.db.before-restore.$(date +%Y%m%dT%H%M%S)"

# 3. 校验并恢复数据库
python -m app.migrations.backup restore --backup backups/quark_strm.<timestamp>.db --db quark_strm.db

# 4. 按需恢复配置
cp backups/config.<timestamp>.yaml config.yaml

# 5. 校验 schema version 并重启服务
python -m app.migrations.runner --db quark_strm.db
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

- [ ] 补充 Prometheus 规则文件与 Alertmanager 资产
- [ ] 添加自动化备份脚本
- [ ] 补充扩容指南
- [ ] 添加灾难恢复流程

## 参考链接

- [架构文档](../architecture/README.md)
- [开发文档](../development/README.md)
- [API 文档](../api/README.md)
- [监控文档](../monitoring/README.md)
