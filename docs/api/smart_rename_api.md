# 智能重命名 API 接口文档

## 📋 文档信息
- **版本**: v1.1
- **创建时间**: 2026-02-04
- **更新时间**: 2026-02-04
- **适用范围**: 智能重命名功能 - 夸克云盘集成

---

## 🌐 API 端点总览

### 现有端点（本地文件）

| 端点 | 方法 | 描述 | 状态 |
|------|------|------|------|
| `/api/smart-rename/preview` | POST | 预览本地文件重命名 | ✅ 已实现 |
| `/api/smart-rename/execute` | POST | 执行本地文件重命名 | ✅ 已实现 |
| `/api/smart-rename/rollback/{batch_id}` | POST | 回滚重命名操作 | ✅ 已实现 |
| `/api/smart-rename/algorithms` | GET | 获取算法列表 | ✅ 已实现 |
| `/api/smart-rename/naming-standards` | GET | 获取命名标准列表 | ✅ 已实现 |
| `/api/smart-rename/status` | GET | 获取服务状态 | ✅ 已实现 |

### 新增端点（夸克云盘）

| 端点 | 方法 | 描述 | 状态 |
|------|------|------|------|
| `/api/quark/browse` | GET | 浏览云盘目录 | ❌ 待实现 |
| `/api/quark/smart-rename-cloud` | POST | 预览云盘文件重命名 | ❌ 待实现 |
| `/api/quark/execute-cloud-rename` | POST | 执行云盘文件重命名 | ❌ 待实现 |
| `/api/quark/cloud-rename-status/{batch_id}` | GET | 查询云盘重命名状态 | ❌ 待实现 |

---

## 📖 详细接口说明

### 1. 浏览云盘目录

#### 基本信息
- **端点**: `/api/quark/browse`
- **方法**: `GET`
- **描述**: 获取夸克云盘指定目录下的文件和文件夹列表

#### 请求参数

| 参数名 | 类型 | 必填 | 默认值 | 描述 |
|--------|------|------|--------|------|
| pdir_fid | string | 否 | "0" | 父目录ID，"0"表示根目录 |
| page | integer | 否 | 1 | 页码，从1开始 |
| size | integer | 否 | 100 | 每页数量，范围1-500 |
| file_type | string | 否 | "all" | 文件类型过滤：video/folder/all |

#### 请求示例

```bash
GET /api/quark/browse?pdir_fid=0&page=1&size=50&file_type=folder
```

#### 响应示例

```json
{
  "status": 200,
  "data": {
    "items": [
      {
        "fid": "abc123",
        "file_name": "电影",
        "pdir_fid": "0",
        "file_type": 0,
        "size": 0,
        "created_at": 1706889600,
        "updated_at": 1706889600,
        "category": "folder"
      },
      {
        "fid": "def456",
        "file_name": "电视剧",
        "pdir_fid": "0",
        "file_type": 0,
        "size": 0,
        "created_at": 1706889600,
        "updated_at": 1706889600,
        "category": "folder"
      }
    ],
    "total": 2,
    "page": 1,
    "size": 50
  }
}
```

#### 响应字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| fid | string | 文件/文件夹唯一ID |
| file_name | string | 文件/文件夹名称 |
| pdir_fid | string | 父目录ID |
| file_type | integer | 类型：0=文件夹, 1=文件 |
| size | integer | 文件大小（字节），文件夹为0 |
| created_at | integer | 创建时间（Unix时间戳） |
| updated_at | integer | 更新时间（Unix时间戳） |
| category | string | 分类：folder/video/document等 |

#### 错误响应

```json
{
  "status": 401,
  "message": "未登录或登录已过期",
  "detail": "请重新登录夸克账号"
}
```

```json
{
  "status": 404,
  "message": "目录不存在",
  "detail": "指定的目录ID不存在或已被删除"
}
```

---

### 2. 预览云盘文件重命名

#### 基本信息
- **端点**: `/api/quark/smart-rename-cloud`
- **方法**: `POST`
- **描述**: 对夸克云盘中的文件进行智能重命名预览

#### 请求体

```json
{
  "pdir_fid": "abc123",
  "algorithm": "ai_enhanced",
  "naming_standard": "emby",
  "force_ai_parse": false,
  "options": {
    "recursive": true,
    "create_folders": true,
    "auto_confirm_high_confidence": true,
    "high_confidence_threshold": 0.9,
    "ai_confidence_threshold": 0.7
  }
}
```

#### 请求字段说明

| 字段 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| pdir_fid | string | 是 | - | 目标目录ID |
| algorithm | string | 否 | "ai_enhanced" | 算法：standard/ai_enhanced/ai_only |
| naming_standard | string | 否 | "emby" | 命名标准：emby/plex/kodi |
| force_ai_parse | boolean | 否 | false | 是否强制使用AI解析 |
| options | object | 否 | - | 高级选项 |

**options 字段说明**:

| 字段 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| recursive | boolean | true | 是否递归处理子目录 |
| create_folders | boolean | true | 是否创建文件夹结构 |
| auto_confirm_high_confidence | boolean | true | 自动确认高置信度匹配 |
| high_confidence_threshold | float | 0.9 | 高置信度阈值 |
| ai_confidence_threshold | float | 0.7 | AI解析置信度阈值 |

#### 响应示例

```json
{
  "status": 200,
  "data": {
    "batch_id": "batch_20260204_123456",
    "pdir_fid": "abc123",
    "total_items": 10,
    "matched_items": 8,
    "needs_confirmation": 2,
    "average_confidence": 0.85,
    "analysis_time": 3.5,
    "items": [
      {
        "fid": "file001",
        "original_name": "复仇者联盟4.终局之战.2019.1080p.mkv",
        "new_name": "Avengers Endgame (2019).mkv",
        "tmdb_id": 299534,
        "tmdb_title": "Avengers: Endgame",
        "tmdb_year": 2019,
        "media_type": "movie",
        "overall_confidence": 0.95,
        "used_algorithm": "ai_enhanced",
        "needs_confirmation": false,
        "status": "matched"
      },
      {
        "fid": "file002",
        "original_name": "权力的游戏.S08E06.mkv",
        "new_name": "Game of Thrones - S08E06.mkv",
        "tmdb_id": 1399,
        "tmdb_title": "Game of Thrones",
        "tmdb_year": 2011,
        "media_type": "tv",
        "season": 8,
        "episode": 6,
        "overall_confidence": 0.92,
        "used_algorithm": "standard",
        "needs_confirmation": false,
        "status": "matched"
      }
    ]
  }
}
```

#### 响应字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| batch_id | string | 批次ID，用于后续执行 |
| pdir_fid | string | 目标目录ID |
| total_items | integer | 总文件数 |
| matched_items | integer | 成功匹配的文件数 |
| needs_confirmation | integer | 需要确认的文件数 |
| average_confidence | float | 平均置信度 |
| analysis_time | float | 分析耗时（秒） |
| items | array | 文件列表 |

**items 中每项的字段**:

| 字段 | 类型 | 描述 |
|------|------|------|
| fid | string | 文件ID |
| original_name | string | 原文件名 |
| new_name | string | 新文件名 |
| tmdb_id | integer | TMDB ID（如果匹配到） |
| tmdb_title | string | TMDB标题 |
| tmdb_year | integer | 年份 |
| media_type | string | 媒体类型：movie/tv/anime |
| season | integer | 季数（仅剧集） |
| episode | integer | 集数（仅剧集） |
| overall_confidence | float | 总体置信度 |
| used_algorithm | string | 使用的算法 |
| needs_confirmation | boolean | 是否需要确认 |
| status | string | 状态：matched/parsed/skipped |

---

### 3. 执行云盘文件重命名

#### 基本信息
- **端点**: `/api/quark/execute-cloud-rename`
- **方法**: `POST`
- **描述**: 批量执行夸克云盘文件重命名

#### 请求体

```json
{
  "batch_id": "batch_20260204_123456",
  "operations": [
    {
      "fid": "file001",
      "new_name": "Avengers Endgame (2019).mkv"
    },
    {
      "fid": "file002",
      "new_name": "Game of Thrones - S08E06.mkv"
    }
  ]
}
```

#### 请求字段说明

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| batch_id | string | 是 | 预览时返回的批次ID |
| operations | array | 是 | 重命名操作列表 |

**operations 中每项的字段**:

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| fid | string | 是 | 文件ID |
| new_name | string | 是 | 新文件名 |

#### 响应示例

```json
{
  "status": 200,
  "data": {
    "batch_id": "batch_20260204_123456",
    "total": 10,
    "success": 8,
    "failed": 2,
    "results": [
      {
        "fid": "file001",
        "status": "success",
        "new_name": "Avengers Endgame (2019).mkv"
      },
      {
        "fid": "file002",
        "status": "failed",
        "error": "文件名已存在"
      }
    ]
  }
}
```

#### 响应字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| batch_id | string | 批次ID |
| total | integer | 总操作数 |
| success | integer | 成功数量 |
| failed | integer | 失败数量 |
| results | array | 每个操作的结果 |

**results 中每项的字段**:

| 字段 | 类型 | 描述 |
|------|------|------|
| fid | string | 文件ID |
| status | string | 状态：success/failed |
| new_name | string | 新文件名（成功时） |
| error | string | 错误信息（失败时） |

---

### 4. 查询云盘重命名状态

#### 基本信息
- **端点**: `/api/quark/cloud-rename-status/{batch_id}`
- **方法**: `GET`
- **描述**: 查询云盘重命名批次的执行状态

#### 请求参数

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| batch_id | string | 是 | 批次ID（路径参数） |

#### 请求示例

```bash
GET /api/quark/cloud-rename-status/batch_20260204_123456
```

#### 响应示例

```json
{
  "status": 200,
  "data": {
    "batch_id": "batch_20260204_123456",
    "status": "completed",
    "total_items": 10,
    "success_items": 8,
    "failed_items": 2,
    "created_at": "2026-02-04T12:34:56Z",
    "completed_at": "2026-02-04T12:35:10Z"
  }
}
```

#### 响应字段说明

| 字段 | 类型 | 描述 |
|------|------|------|
| batch_id | string | 批次ID |
| status | string | 状态：previewing/executing/completed/failed |
| total_items | integer | 总文件数 |
| success_items | integer | 成功数量 |
| failed_items | integer | 失败数量 |
| created_at | string | 创建时间（ISO 8601格式） |
| completed_at | string | 完成时间（ISO 8601格式） |

---

## 🔐 认证与授权

### 认证方式
所有 API 端点都需要有效的夸克登录凭证。系统使用 Cookie 进行认证。

### Cookie 字段
- `__puus`: 夸克用户认证令牌
- 其他夸克相关 Cookie

### 认证失败响应
```json
{
  "status": 401,
  "message": "未授权",
  "detail": "请先登录夸克账号"
}
```

---

## ⚠️ 错误码说明

| 错误码 | 描述 | 解决方案 |
|--------|------|----------|
| 400 | 请求参数错误 | 检查请求参数格式和内容 |
| 401 | 未授权 | 重新登录夸克账号 |
| 403 | 禁止访问 | 检查文件权限 |
| 404 | 资源不存在 | 检查文件/目录ID是否正确 |
| 429 | 请求过于频繁 | 降低请求频率，添加延迟 |
| 500 | 服务器内部错误 | 查看服务器日志，联系管理员 |
| 503 | 服务不可用 | 稍后重试 |

---

## 📊 限流规则

### 请求频率限制
- 浏览目录：每秒最多 10 次
- 智能重命名预览：每分钟最多 5 次
- 执行重命名：每分钟最多 3 次

### 批量操作限制
- 单次预览最多 1000 个文件
- 单次执行最多 500 个文件
- 建议分批处理大量文件

---

## 🧪 测试用例

### 测试用例 1: 浏览根目录

**请求**:
```bash
curl -X GET "http://localhost:8000/api/quark/browse?pdir_fid=0&page=1&size=20" \
  -H "Cookie: __puus=your_cookie_here"
```

**预期响应**: 200 OK，返回根目录文件列表

---

### 测试用例 2: 预览电影重命名

**请求**:
```bash
curl -X POST "http://localhost:8000/api/quark/smart-rename-cloud" \
  -H "Content-Type: application/json" \
  -H "Cookie: __puus=your_cookie_here" \
  -d '{
    "pdir_fid": "movie_folder_id",
    "algorithm": "ai_enhanced",
    "naming_standard": "emby"
  }'
```

**预期响应**: 200 OK，返回重命名预览结果

---

### 测试用例 3: 执行重命名

**请求**:
```bash
curl -X POST "http://localhost:8000/api/quark/execute-cloud-rename" \
  -H "Content-Type: application/json" \
  -H "Cookie: __puus=your_cookie_here" \
  -d '{
    "batch_id": "batch_20260204_123456",
    "operations": [
      {
        "fid": "file001",
        "new_name": "Movie Name (2023).mkv"
      }
    ]
  }'
```

**预期响应**: 200 OK，返回执行结果

---

## 📝 更新日志

### v1.1 (2026-02-04)
- 更新媒体类型支持，添加 "anime" 类型
- 完善智能重命名解析服务
- 扩展正则解析模式，支持多集格式
- 增强后处理逻辑，添加更多后缀清理

### v1.0 (2026-02-04)
- 初始版本
- 定义夸克云盘集成 API 接口
- 添加浏览、预览、执行端点

---

**文档维护者**: Architect Agent  
**最后更新**: 2026-02-04
