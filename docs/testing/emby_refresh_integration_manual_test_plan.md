# Emby 刷新集成测试方案（手工实测版）

项目：`smart_media/quark_strm`  
适用实现版本：以仓库当前代码为准  
文档用途：你在真实环境中按步骤实际测试，并形成可验收的记录

---

## 1. 测试目标与范围

验证 Emby 集成的「配置 → 连接 → 手动刷新 → 自动触发 → 定时刷新 → 刷新历史」闭环可用，并满足：

- Emby 刷新失败 **不应影响** STRM 生成/重命名等主流程（仅记录告警/失败）
- 同时只允许一个刷新任务运行，避免重复刷新（并发控制）

### 优先级与验收点

**P0（必须通过）**
1. 配置可保存到 `quark_strm/config.yaml`，重启后仍生效  
2. 连接测试可用：返回 `success/message/server_info`  
3. 手动刷新可用：触发刷新任务（后台执行），接口返回成功

**P1（应通过）**
4. STRM 生成后自动触发刷新（不阻塞 STRM 主流程）  
5. 智能重命名执行后自动触发刷新（不阻塞重命名主流程）  
6. Cron 定时刷新可用：按表达式触发刷新任务

**P2（可选）**
7. 刷新历史可查看（接口返回历史记录）；通知（若你已配置通知规则/渠道）

---

## 2. 前置条件 / 环境准备

### 2.1 基础环境

- 可访问的 Emby Server（建议同局域网，减少不稳定因素）
- 已生成 Emby API Key
- `quark_strm` 后端服务可启动（本文示例端口为 `8000`，按你实际替换）

### 2.2 配置文件位置

- 后端配置文件：`smart_media/quark_strm/config.yaml`
- 本次实现的 Emby 配置段（新增/扩展）：
  - `emby.enabled`
  - `emby.url`
  - `emby.api_key`
  - `emby.timeout`
  - `emby.notify_on_complete`
  - `emby.refresh.on_strm_generate`
  - `emby.refresh.on_rename`
  - `emby.refresh.cron`
  - `emby.refresh.library_ids`

> 注意：前端为了安全不会回填 `api_key`；保存时若 `api_key` 留空，后端会“保持现有 api_key 不变”。首次启用请务必填写。

---

## 3. 测试工具与命令

### 3.1 启动后端（示例）

在 `smart_media/quark_strm` 目录执行（按你的启动方式为准）：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3.2 API Base

下文统一以：

- `API_BASE=http://localhost:8000`

### 3.3 Windows PowerShell 注意事项（重要）

在 PowerShell 中，`curl` 默认是 `Invoke-WebRequest` 的别名，`curl -X ...` 这类写法会报错。

推荐使用以下任一方式：

1) 使用 `curl.exe`（Windows 自带）

```powershell
curl.exe -sS http://127.0.0.1:8000/health
```

2) 使用 `Invoke-RestMethod`（更适合 JSON）

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health -Method GET -TimeoutSec 10
```

此外，如遇 `localhost` 超时，建议统一改用 `127.0.0.1` 进行测试，避免本机 DNS/IPv6 解析差异导致的干扰。

### 3.4 端口占用排查（若出现请求超时）

如果出现“端口监听但请求超时/无响应”，可能是残留进程或重复启动导致。

```powershell
netstat -ano | findstr :8000
tasklist /FI "PID eq <PID>"
taskkill /F /PID <PID>
```

---

## 4. 手工测试用例（按执行顺序）

### TC-01 配置写入与持久化（P0）

**目的**：验证 Emby 配置通过 API 写入 `config.yaml`，重启后仍生效

**步骤**
1. 更新配置（把 `url/api_key` 替换为你的实际值）：

```bash
curl -X POST "%API_BASE%/api/emby/config" ^
  -H "Content-Type: application/json" ^
  -d "{\"enabled\":true,\"url\":\"http://192.168.100.66:18096\",\"api_key\":\"YOUR_API_KEY\",\"timeout\":30,\"notify_on_complete\":true,\"on_strm_generate\":true,\"on_rename\":true,\"cron\":\"\",\"library_ids\":[]}"
```

2. 打开 `smart_media/quark_strm/config.yaml`，确认 `emby:` 段已更新
3. 重启后端服务
4. 查询状态：

```bash
curl "%API_BASE%/api/emby/status"
```

**期望结果**
- `POST /api/emby/config` 返回：`{"success": true}`
- `config.yaml` 中 `emby.enabled/url/api_key/...` 已写入
- 重启后 `GET /api/emby/status` 的 `configuration` 与写入一致（`api_key` 为脱敏显示）

---

### TC-02 连接测试（P0）

**目的**：验证可连通 Emby，且返回 `server_info`

**步骤**
```bash
curl -X POST "%API_BASE%/api/emby/test-connection" ^
  -H "Content-Type: application/json" ^
  -d "{\"url\":\"http://192.168.100.66:18096\",\"api_key\":\"YOUR_API_KEY\"}"
```

**期望结果**
- `success: true`
- `server_info.server_name/version/operating_system` 存在（内容依 Emby 实际）

**异常验证（可选）**
- API Key 填错：`success: false`，`message` 包含失败原因（不应导致 500 崩溃）

---

### TC-03 获取媒体库列表（P0）

**目的**：验证能获取媒体库列表用于选择刷新范围

**步骤**
```bash
curl "%API_BASE%/api/emby/libraries"
```

**期望结果**
- `success: true`
- `libraries` 为数组；每项包含 `id/name`（`collection_type` 可能为空）

---

### TC-04 手动触发刷新（全库）（P0）

**目的**：验证手动刷新接口可触发后台刷新

**步骤**
1. 触发刷新：

```bash
curl -X POST "%API_BASE%/api/emby/refresh" -H "Content-Type: application/json" -d "{}"
```

2. 观察 Emby 侧是否开始扫描（或查看媒体库最近扫描时间）
3. 查看刷新历史（可选）：

```bash
curl "%API_BASE%/api/emby/refresh/history?limit=20"
```

**期望结果**
- `POST /refresh` 返回：`{"success": true, "message": "刷新任务已触发"}`
- Emby 侧能看到刷新/扫描行为（可能有延迟）
- `/refresh/history` 能看到记录（含时间戳、成功/失败）

---

### TC-05 手动触发刷新（指定库）（P1）

**目的**：验证按 `library_ids` 刷新指定库（行为依赖 Emby 版本与实现细节）

**前置**：先通过 TC-03 拿到某个 `library id`

**步骤**
```bash
curl -X POST "%API_BASE%/api/emby/refresh" ^
  -H "Content-Type: application/json" ^
  -d "{\"library_ids\":[\"LIB_ID_1\",\"LIB_ID_2\"]}"
```

**期望结果**
- 接口返回成功
- Emby 侧对对应库出现刷新迹象（若 UI 不明显，请以 Emby 日志/扫描时间判断）

---

### TC-06 STRM 生成后自动触发刷新（P1）

**目的**：验证 STRM 生成完成后触发 Emby 刷新，且失败不影响 STRM 主流程

**前置**
- `emby.enabled=true`
- `emby.refresh.on_strm_generate=true`
- 你已有可跑通的 STRM 生成流程（UI 或接口）

**步骤（示例：直接调用 STRM 扫描接口）**
```bash
curl -X POST "%API_BASE%/api/strm/scan?remote_path=/video&local_path=./strm&recursive=true&concurrent_limit=5&base_url=http://localhost:8000&strm_url_mode=redirect"
```

**观察点**
- STRM 扫描/生成接口返回是否正常（不应被 Emby 刷新阻塞）
- Emby 是否出现扫描动作
- `GET /api/emby/refresh/history` 是否新增记录

**期望结果**
- STRM 主流程不受 Emby 刷新失败影响
- Emby 可用时能观察到刷新触发

---

### TC-07 智能重命名完成后自动触发刷新（P1）

**目的**：验证 smart rename 执行完成后触发刷新

**前置**
- `emby.enabled=true`
- `emby.refresh.on_rename=true`
- 你能跑通智能重命名 execute 流程（按项目现有入口）

**步骤**
1. 执行一次智能重命名（建议仅少量文件）
2. 完成后观察 Emby 刷新动作
3. 查看刷新历史是否有新增记录

**期望结果**
- 重命名结果正常返回
- 刷新在后台触发；失败不影响重命名主结果

---

### TC-08 Cron 定时刷新（P1）

**目的**：验证按 cron 表达式定时触发刷新

**建议**：先用“每分钟一次”便于观察：`*/1 * * * *`

**步骤**
1. 更新配置，设置 cron：
```bash
curl -X POST "%API_BASE%/api/emby/config" ^
  -H "Content-Type: application/json" ^
  -d "{\"enabled\":true,\"url\":\"http://192.168.100.66:18096\",\"api_key\":\"YOUR_API_KEY\",\"timeout\":30,\"notify_on_complete\":true,\"on_strm_generate\":true,\"on_rename\":true,\"cron\":\"*/1 * * * *\",\"library_ids\":[]}"
```

2. 等待 1–2 分钟
3. 观察：
   - Emby 扫描动作
   - `GET /api/emby/refresh/history` 是否出现周期性记录

4. 停止定时刷新（将 cron 置空后保存）：
```bash
curl -X POST "%API_BASE%/api/emby/config" ^
  -H "Content-Type: application/json" ^
  -d "{\"enabled\":true,\"url\":\"http://192.168.100.66:18096\",\"api_key\":\"\",\"timeout\":30,\"notify_on_complete\":true,\"on_strm_generate\":true,\"on_rename\":true,\"cron\":\"\",\"library_ids\":[]}"
```

**期望结果**
- 到点触发刷新
- 不会并发触发多次（重复触发会跳过）
- 置空 cron 后不再触发

---

## 5. 回归测试清单（建议快速过一遍）

- `GET %API_BASE%/health` 返回 `status=ok`
- 已有 Emby Playback Hook 路由仍可访问（如你有使用）：`/api/emby/items/{id}/PlaybackInfo` 等
- STRM 生成与智能重命名不因 Emby 不可用而报错（只记录 warning）

---

## 6. 测试记录模板（最终交付可用）

**测试报告：Emby 刷新集成（手工）**

- 测试时间：  
- 测试人：  
- 后端地址（API_BASE）：  
- Emby 地址：  
- 关键配置：`emby.enabled / on_strm_generate / on_rename / cron / library_ids`  

| 用例 | 结果(通过/失败) | 证据（响应/截图/日志） | 备注 |
|---|---|---|---|
| TC-01 配置持久化 |  |  |  |
| TC-02 连接测试 |  |  |  |
| TC-03 获取媒体库 |  |  |  |
| TC-04 手动刷新全库 |  |  |  |
| TC-05 手动刷新指定库 |  |  |  |
| TC-06 STRM 触发刷新 |  |  |  |
| TC-07 重命名触发刷新 |  |  |  |
| TC-08 Cron 定时刷新 |  |  |  |

---

## 7. 已知依赖与注意事项

- “指定库刷新”的可观测行为依赖 Emby 版本与 UI 表现；如 UI 不明显，建议以 Emby 日志或扫描时间为准。
- 刷新历史为进程内内存记录：服务重启后会清空（当前实现如此）。
- 首次启用必须提供 `url/api_key`；后续更新配置时 `api_key` 为空代表“保持原值不变”。
