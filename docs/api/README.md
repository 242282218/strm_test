# API 文档

## 概述

quark_strm 提供 RESTful API 接口，所有接口返回统一的 JSON 响应格式。

**基础 URL**: `http://localhost:8000`

**API 版本**: v1

**v1 路径规范**:
- Canonical: `/api/v1/<module>/*`（例如 `/api/v1/quark/files/0`）
- Legacy alias: `/api/v1/api/<module>/*`（兼容旧客户端，建议尽快迁移）

## 认证

### 认证方式

当前系统支持两类认证凭证：

1. JWT / Session Token

```http
Authorization: Bearer <jwt-token>
```

浏览器登录后，服务端也会通过 HttpOnly Cookie 自动携带 `auth_token`。

2. API Key

```http
X-API-Key: <api-key>
```

兼容只支持 `Authorization` 头的客户端时，也可使用：

```http
Authorization: Bearer <api-key>
```

API key 的推荐配置入口为：

- `config.yaml` -> `security.api_key`
- 环境变量 `SMART_MEDIA_SECURITY_API_KEY`

### 获取 Token / 登录

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password123"
}
```

也支持直接提交 API key 换取 JWT/HttpOnly Cookie：

```http
POST /api/auth/login
Content-Type: application/json

{
  "api_key": "your-api-key"
}
```

**响应示例**:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

## 统一响应格式

### 成功响应

```json
{
  "code": 0,
  "data": { ... },
  "message": "success"
}
```

### 错误响应

```json
{
  "code": 1001,
  "error_code": "AUTH_UNAUTHORIZED",
  "title": "未授权",
  "message": "请先登录",
  "action": "请携带有效的 JWT Token",
  "category": 1000
}
```

### 错误码分类

| 分类 | 范围 | 说明 |
|------|------|------|
| 系统错误 | 1000-1999 | 系统级错误 |
| 认证错误 | 2000-2999 | 认证授权相关 |
| 业务错误 | 3000-3999 | 业务逻辑错误 |
| 外部服务 | 4000-4999 | 外部 API 调用错误 |

## API 端点

### 公共探针与指标

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | `/health` | 综合健康状态（含启动告警与 readiness 摘要） | ❌ |
| GET | `/health/live` | 存活探针 | ❌ |
| GET | `/ready` | 就绪探针别名 | ❌ |
| GET | `/health/ready` | 就绪探针 | ❌ |
| GET | `/metrics` | Prometheus 指标抓取端点 | ❌ |
| GET | `/metrics/health` | Prometheus 指标服务健康状态 | ❌ |

### 认证模块 (`/api/auth`)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| POST | `/login` | 用户登录 | ❌ |
| GET | `/verify` | 校验 Cookie / JWT / API Key 是否有效 | ❌ |
| GET | `/status` | 返回当前是否启用认证及是否已初始化管理员 | ❌ |
| POST | `/init-admin` | 本地首次引导创建管理员账户 | ❌ |
| POST | `/refresh` | 使用 refresh token 刷新访问令牌 | ❌ |
| POST | `/logout` | 清理登录 Cookie | ❌ |
| POST | `/change-password` | 修改当前用户密码 | ✅ |
| GET | `/me` | 获取当前用户 | ✅ |

### 夸克网盘 (`/api/quark`)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | `/files` | 获取文件列表 | ✅ |
| GET | `/files/:id` | 获取文件详情 | ✅ |
| POST | `/files/:id/strm` | 生成 STRM 文件 | ✅ |
| DELETE | `/files/:id` | 删除文件 | ✅ |

### STRM 管理 (`/api/strm`)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | `/list` | 获取 STRM 列表 | ✅ |
| POST | `/generate` | 批量生成 STRM | ✅ |
| DELETE | `/batch` | 批量删除 STRM | ✅ |
| GET | `/status` | 获取生成状态 | ✅ |

### Emby 集成 (`/api/emby`)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | `/status` | 获取 Emby 状态 | ✅ |
| POST | `/refresh` | 刷新媒体库 | ✅ |
| GET | `/libraries` | 获取媒体库列表 | ✅ |
| GET | `/sessions` | 获取播放会话 | ✅ |

### 刮削服务 (`/api/scrape`)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | `/paths` | 获取刮削路径配置 | ✅ |
| POST | `/paths` | 添加刮削路径 | ✅ |
| DELETE | `/paths/:id` | 删除刮削路径 | ✅ |
| POST | `/execute` | 执行刮削任务 | ✅ |
| GET | `/records` | 获取刮削记录 | ✅ |

### 任务管理 (`/api/tasks`)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | `/list` | 获取任务列表 | ✅ |
| GET | `/status/:id` | 获取任务状态 | ✅ |
| POST | `/cancel/:id` | 取消任务 | ✅ |
| DELETE | `/history` | 清空历史记录 | ✅ |

### 重命名服务 (`/api/rename`)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| POST | `/basic` | 基础重命名 | ✅ |
| POST | `/smart` | 智能重命名 | ✅ |
| GET | `/history` | 获取重命名历史 | ✅ |

### 系统监控 (`/api/monitor`)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/monitor/health` | 监控子系统健康摘要 | ❌ |
| GET | `/api/monitor/system/status` | 系统状态摘要 | ❌ |
| GET | `/api/monitor/metrics` | 聚合业务指标快照 | ✅ |
| GET | `/api/monitor/http-pool/health` | HTTP 连接池健康状态 | ❌ |
| GET | `/api/monitor/db-pool/health` | 数据库连接池健康状态 | ❌ |

### 通知服务 (`/api/notification`)

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|------|
| GET | `/config` | 获取通知配置 | ✅ |
| PUT | `/config` | 更新通知配置 | ✅ |
| POST | `/test` | 发送测试通知 | ✅ |
| GET | `/history` | 获取通知历史 | ✅ |

## WebSocket 接口

### 任务进度推送

```
WS /ws/tasks
```

**消息格式**:

```json
{
  "type": "progress",
  "task_id": "xxx",
  "progress": 50,
  "message": "处理中..."
}
```

## 速率限制

| 端点类型 | 限制 |
|----------|------|
| 认证接口 | 10 次/分钟 |
| 普通 API | 100 次/分钟 |
| 文件操作 | 50 次/分钟 |

## 分页参数

支持分页的接口使用以下参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | int | 1 | 页码 |
| `page_size` | int | 20 | 每页数量 |
| `total` | bool | false | 是否返回总数 |

## 排序参数

支持排序的接口使用以下参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| `sort_by` | string | 排序字段 |
| `sort_order` | string | asc/desc |

## 待办事项

- [ ] 补充完整的请求/响应示例
- [ ] 添加 Swagger UI 截图
- [ ] 补充错误码完整列表
- [ ] 添加速率限制配置指南

## 参考链接

- [架构文档](../architecture/README.md)
- [开发文档](../development/README.md)
- [运维文档](../operations/README.md)
