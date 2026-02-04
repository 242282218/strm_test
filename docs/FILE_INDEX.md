# 项目文件索引

本文档记录 quark_strm 项目中所有主要文件和目录的功能与用途。

**最后更新**: 2026-02-04

---

## 📁 项目根目录

```
quark_strm/
├── app/                    # 核心应用代码
├── config.yaml             # 主配置文件
├── docs/                   # 项目文档
├── scripts/                # 工具脚本
├── web/                    # 前端应用
├── data/                   # 数据存储
├── logs/                   # 日志文件
├── strm/                   # STRM 文件存储
├── tmp/                    # 临时文件
├── tests/                  # 测试代码
├── requirements.txt        # Python 依赖
├── Dockerfile              # Docker 镜像配置
└── docker-compose.yml      # Docker Compose 配置
```

---

## 🔧 核心应用 (`app/`)

### API 层 (`app/api/`)

**用途**: 定义 HTTP API 路由和端点

#### 当前 API 文件（根级别）
- `cloud_drive.py` - 云盘管理 API
- `dashboard.py` - 仪表板数据 API
- `emby.py` - Emby 集成 API
- `monitoring.py` - 监控数据 API
- `notification.py` - 通知服务 API
- `proxy.py` - 代理服务 API
- `quark.py` - 夸克云盘 API
- `quark_sdk.py` - 夸克 SDK API
- `rename.py` - 重命名服务 API
- `scrape.py` - 刮削服务 API
- `search.py` - 搜索服务 API
- `smart_rename.py` - 智能重命名 API
- `strm.py` - STRM 文件管理 API
- `strm_validator.py` - STRM 验证 API
- `system_config.py` - 系统配置 API
- `tasks.py` - 任务管理 API
- `tmdb.py` - TMDB 集成 API
- `transfer.py` - 转存服务 API

#### v1 API（新版本）
- `v1/` - 版本化 API 目录
  - 包含重构后的 API 端点

**说明**: 根级别 API 为旧版本，v1 为新版本。建议新功能使用 v1 API。

---

### 业务逻辑层 (`app/services/`)

**用途**: 实现核心业务逻辑

#### AI 服务
- `ai_parser_service.py` - AI 解析服务，用于智能识别媒体信息

#### 缓存服务
- `cache_service.py` - 缓存管理服务
- `cache_statistics.py` - 缓存统计分析
- `cache_warmer.py` - 缓存预热服务
- `link_cache.py` - 链接缓存服务
- `redis_cache.py` - Redis 缓存实现

#### 云盘服务
- `cloud_drive_service.py` - 云盘管理服务

#### 配置服务
- `config_service.py` - 配置管理服务

#### 定时任务
- `cron_service.py` - 定时任务调度服务

#### Emby 集成
- `emby_api_client.py` - Emby API 客户端
- `emby_naming_service.py` - Emby 命名规范服务
- `emby_proxy_service.py` - Emby 代理服务
- `emby_service.py` - Emby 集成服务
- `playbackinfo_hook.py` - 播放信息钩子

#### 媒体处理
- `media_organize_service.py` - 媒体整理服务
- `nfo_generator.py` - NFO 文件生成器

#### 通知服务
- `notification_service.py` - 通知服务管理
- `notification/` - 通知处理器子模块

#### 代理服务
- `proxy_service.py` - 代理服务管理

#### 夸克云盘
- `quark_api_client.py` - 夸克 API 客户端 v1
- `quark_api_client_v2.py` - 夸克 API 客户端 v2（推荐）
- `quark_sdk_service.py` - 夸克 SDK 服务
- `quark_service.py` - 夸克服务管理
- `quark_size_fetcher.py` - 文件大小获取服务

#### 重命名服务
- `rename_service.py` - 重命名服务
- `smart_rename_service.py` - 智能重命名服务

#### 评分服务
- `scoring/` - 评分服务子模块

#### 刮削服务
- `scrape_service.py` - 刮削服务，从 TMDB 获取元数据

#### 搜索服务
- `search_service.py` - 资源搜索服务

#### STRM 服务
- `strm_generator.py` - STRM 文件生成器
- `strm_service.py` - STRM 服务管理
- `strm_validator.py` - STRM 文件验证器

#### 任务管理
- `task_queue_service.py` - 任务队列服务
- `task_runner.py` - 任务执行器
- `task_scheduler.py` - 任务调度器

#### TMDB 服务
- `tmdb_service.py` - TMDB API 服务

#### 转存服务
- `transfer_service.py` - 文件转存服务

#### WebDAV 服务
- `webdav/` - WebDAV 集成子模块

---

### 核心组件 (`app/core/`)

**用途**: 提供核心基础设施组件

- `config.py` - 配置管理
- `database.py` - 数据库连接和管理
- `dependencies.py` - 依赖注入
- `encryption.py` - 加密解密功能
- `exceptions.py` - 异常定义和处理
- `logging.py` - 日志配置
- `cache.py` - LRU 缓存实现
- `metrics.py` - 性能指标收集
- `response.py` - API 响应格式化
- `retry.py` - 重试机制
- `security.py` - 安全相关功能
- `validators.py` - 数据验证器
- `websocket.py` - WebSocket 管理

---

### 数据模型 (`app/models/`)

**用途**: 定义数据库表结构（SQLAlchemy ORM）

- `base.py` - 基础模型类
- `cloud_drive.py` - 云盘数据模型
- `emby.py` - Emby 数据模型
- `quark.py` - 夸克数据模型
- `scrape.py` - 刮削数据模型
- `strm.py` - STRM 数据模型
- `task.py` - 任务数据模型

---

### 数据验证 (`app/schemas/`)

**用途**: 定义 API 请求/响应的数据验证模式（Pydantic）

- `base.py` - 基础 Schema
- `cloud_drive.py` - 云盘 Schema
- `task.py` - 任务 Schema

---

### 工具函数 (`app/utils/`)

**用途**: 通用工具函数

---

### 配置模块 (`app/config/`)

**用途**: 应用配置类定义

- `settings.py` - 配置类定义

---

## 📚 文档 (`docs/`)

### 目录结构
- `README.md` - 文档索引
- `FILE_INDEX.md` - 本文件，项目文件索引
- `structure_organization_report.md` - 结构整理报告

### 子目录
- `guides/` - 使用指南
- `architecture/` - 架构文档
- `development/` - 开发文档
  - `development_plan.md` - 开发方案
  - `history.md` - 历史指令记录
  - `test_report.md` - 测试报告
- `operations/` - 运维文档
- `api/` - API 文档

---

## 🔧 脚本工具 (`scripts/`)

### 主要脚本
- `organize_structure.py` - 项目结构整理脚本

### 子目录
- `verification/` - 验证脚本
  - `comprehensive_verification_report.py` - 综合验证报告
  - `verify_smart_rename_mapping.py` - 智能重命名映射验证
  - `verify_ui_completeness.py` - UI 完整性验证
- `utils/` - 工具脚本

---

## 🌐 前端应用 (`web/`)

**技术栈**: Vue 3 + Vite + Element Plus

详见 `web/README.md`

---

## 🗄️ 数据目录

### `data/`
**用途**: 应用数据存储
- 数据库文件
- 用户上传文件
- 缓存数据

### `logs/`
**用途**: 日志文件存储
- 应用日志
- 错误日志
- 访问日志
- 整理操作日志

### `strm/`
**用途**: STRM 文件存储
- 生成的 STRM 文件
- 按媒体类型组织

### `tmp/`
**用途**: 临时文件存储
- 临时下载文件
- 处理中的文件

---

## 🧪 测试 (`tests/`)

**用途**: 单元测试和集成测试

---

## ⚙️ 配置文件

### 根目录配置
- `config.yaml` - 主配置文件
  - API 密钥
  - 服务配置
  - 代理设置

### Python 配置
- `requirements.txt` - Python 依赖包列表
- `pyproject.toml` - 项目元数据和构建配置

### Docker 配置
- `Dockerfile` - Docker 镜像构建配置
- `docker-compose.yml` - Docker Compose 服务编排

---

## 📝 命名规范

### API 文件
- 使用**小写下划线**命名：`cloud_drive.py`
- 功能相关文件使用统一前缀：`quark_*.py`

### Service 文件
- 使用**小写下划线**命名
- 带 `_service` 后缀：`cache_service.py`
- 特殊功能使用描述性后缀：`_client`, `_generator`, `_validator`

### 文档文件
- 使用**小写下划线**命名：`development_plan.md`
- 英文命名优先

---

## 🔄 版本说明

### API 版本
- **根级别 API**: 旧版本，保留用于向后兼容
- **v1 API**: 新版本，推荐使用

### Service 版本
- **v2 后缀**: 最新版本（如 `quark_api_client_v2.py`）
- **无后缀**: 旧版本或稳定版本

---

## 📌 注意事项

1. **配置文件**: 修改 `config.yaml` 后需重启服务
2. **数据库**: 位于 `quark_strm.db`，使用 SQLite
3. **日志**: 默认输出到 `logs/` 目录
4. **环境变量**: 可通过 `.env` 文件配置（参考 `.env.example`）

---

**维护者**: DevOps Agent  
**最后更新**: 2026-02-04
