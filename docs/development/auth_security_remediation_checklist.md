# 认证与安全整改清单

- 日期：2026-03-17
- 范围：`quark_strm`
- 目标：按照代码审查问题顺序，先完成高风险认证与异常处理整改，并在每一项整改前后保留可验证记录。
- 执行方式：严格采用 TDD，小步推进；每项先补测试并确认失败，再做最小改动修复。

---

## 1. 背景

本清单用于落实当前审查中已确认的高优先级问题，优先处理：

1. API Key 被直接作为 Cookie / access token / refresh token 返回。
2. 管理员初始化默认密码为 `admin` 且回传客户端。
3. `ALLOW_PUBLIC_INIT_ADMIN` 存在部署误用风险。
4. 若干接口把内部异常细节直接回传给客户端。

本轮仅先启动问题 1，并为问题 2-4 建立后续实施位。

---

## 2. 整改原则

1. 不改变功能范围，只修正高风险安全行为。
2. 不回滚与当前任务无关的改动。
3. 统一走最小改动策略，优先收敛现有逻辑而不是重写。
4. 每项整改都必须包含：
   - 目标行为
   - 影响文件
   - 测试策略
   - 实施状态
5. 所有生产代码改动前，必须先有失败测试。

---

## 3. 按问题顺序的整改项

### 3.1 问题 1：API Key 直接作为登录态凭证回传

- 风险等级：P0
- 当前问题：
  - API Key 登录后，原始 API Key 被写入 `auth_token` Cookie。
  - 响应体中的 `access_token` / `refresh_token` 直接返回原始 API Key。
- 涉及文件：
  - `app/api/auth.py`
  - `app/services/auth_service.py`
  - `app/core/auth_middleware.py`
  - `app/core/dependencies.py`
  - `tests/test_auth_api_endpoints.py`
  - `tests/test_auth_middleware.py`
- 目标行为：
  1. API Key 仅用于完成一次认证交换。
  2. Cookie 中不再存储原始 API Key。
  3. 响应体中不再返回原始 API Key。
  4. 交换后签发受控的短期会话令牌，并保持受保护接口可继续访问。
- 测试策略：
  1. 新增 API Key 登录用例，断言响应体不回传原始 API Key。
  2. 断言 `Set-Cookie` 不包含原始 API Key。
  3. 断言签发的新会话令牌可通过受保护接口校验。
- 实施状态：当前轮次已完成（API Key 登录不再回传原始 API Key，已补测试并完成最小验证）

### 3.2 问题 2：管理员初始化默认密码为 `admin` 且回传客户端

- 风险等级：P0
- 涉及文件：
  - `app/api/auth.py`
  - `app/services/auth_service.py`
  - `tests/test_auth_api_endpoints.py`
  - `tests/test_auth.py`
- 目标行为：
  1. 不允许隐式降级到固定默认密码。
  2. 未显式提供初始化密码时，应返回明确错误或受控一次性密码策略。
  3. 不向客户端回传明文管理员密码。
- 测试策略：
  - 补充 init-admin 行为测试与默认密码回归测试。
- 实施状态：当前轮次已完成（禁止隐式默认密码，且初始化接口不再回传明文管理员密码）

### 3.3 问题 3：`ALLOW_PUBLIC_INIT_ADMIN` 部署误用风险

- 风险等级：P0
- 涉及文件：
  - `app/api/auth.py`
  - `app/core/auth_middleware.py`
  - `tests/test_auth_api_endpoints.py`
  - `tests/test_auth_middleware.py`
- 目标行为：
  1. 仅允许受控引导场景使用初始化入口。
  2. 避免生产误配置导致公开初始化。
- 测试策略：
  - 覆盖默认、本地受信、显式开放三类行为。
- 实施状态：当前轮次已完成（移除公开放行效果，即使设置开关也仍只允许本地受信请求）

### 3.4 问题 4：内部异常细节直接暴露给客户端

- 风险等级：P0
- 涉及文件：
  - `app/api/auth.py`
  - `app/api/file_manager.py`
  - `app/api/security.py`
  - `app/core/exception_handler.py`
- 目标行为：
  1. 5xx 仅返回通用错误消息。
  2. 详细异常只保留在日志中。
  3. 与统一异常处理器的对外行为保持一致。
- 测试策略：
  - 补充 500 场景断言，验证响应不包含内部异常字符串。
- 实施状态：当前轮次已完成（认证、文件管理、安全审计接口的 5xx 响应已完成异常脱敏，详细异常仅保留日志）

---

## 4. 实施批次

### 批次 A（当前）

- [x] 建立整改清单文档
- [x] 为问题 1 先补失败测试
- [x] 修复 API Key 登录凭证回传问题
- [x] 运行最小验证
- [x] 更新清单状态

### 批次 B（后续）

- [x] 处理问题 2：管理员初始化密码策略
- [x] 处理问题 3：初始化入口受控策略
- [x] 处理问题 4：异常细节脱敏

### 批次 C（本轮追加）

- [x] 处理监控接口未统一鉴权问题
- [x] 处理 Cloud Drive 读取接口未鉴权问题
- [x] 处理 Quark SDK / system_config 异常细节透传问题
- [x] 修复 CI 质量闸门失效问题
- [x] 统一前端认证请求客户端

---

## 5. 最小验证要求

问题 1 完成后至少执行：

1. `pytest tests/test_auth_api_endpoints.py -q`
2. `pytest tests/test_auth_middleware.py -q`

如认证链路改动影响依赖注入，再补：

3. `pytest tests/test_auth.py -q`

---

## 6. 更新记录

### 2026-03-17

- 创建整改清单。
- 确认采用方案 A：按问题顺序推进。
- 开始执行问题 1：API Key 登录凭证整改。
- 为问题 1 新增失败测试：验证 API Key 登录不再回传原始 API Key，也不写入原始 API Key 到 Cookie。
- 完成问题 1 的最小修复：API Key 登录改为签发短期访问令牌，并以该令牌写入 Cookie 与响应体。
- 已完成最小验证：
  - `pytest tests/test_auth_api_endpoints.py -q`
  - `pytest tests/test_auth_middleware.py -q`
  - `pytest tests/test_auth.py -q`
- 开始执行问题 2：管理员初始化密码策略整改。
- 为问题 2 新增失败测试：未配置 `ADMIN_PASSWORD` 时拒绝初始化；已配置时不回传明文管理员密码。
- 完成问题 2 的最小修复：
  - `AuthService.init_default_admin` 不再回退到固定默认密码；
  - `/api/auth/init-admin` 在未配置 `ADMIN_PASSWORD` 时返回明确错误；
  - 初始化成功时不再返回明文管理员密码。
- 已完成问题 2 的最小验证：
  - `pytest tests/test_auth_api_endpoints.py -q`
  - `pytest tests/test_auth.py -q`
- 开始执行问题 3：初始化入口受控策略整改。
- 为问题 3 新增失败测试：即使设置 `ALLOW_PUBLIC_INIT_ADMIN=true`，未受信请求也不能绕过本地限制。
- 完成问题 3 的最小修复：移除 `ALLOW_PUBLIC_INIT_ADMIN` 的公开放行效果，在 API 层和认证中间件中统一要求本地受信请求。
- 已完成问题 3 的最小验证：
  - `pytest tests/test_auth_middleware.py -q`
  - `pytest tests/test_auth_api_endpoints.py -q`
- 开始执行问题 4：内部异常细节脱敏。
- 为问题 4 新增失败测试：验证认证初始化、文件浏览/操作、安全事件/摘要接口在 5xx 场景下不回传内部异常文本。
- 完成问题 4 的最小修复：
  - `app/api/auth.py` 中 `/api/auth/init-admin` 的 500 响应改为通用错误消息；
  - `app/api/file_manager.py` 中 `/files/browse` 与 `/files/operation` 的 500 响应改为通用错误消息；
  - `app/api/security.py` 中安全事件与摘要接口的 500 响应改为通用错误消息。
- 已完成问题 4 的最小验证：
  - `pytest tests/test_auth_api_endpoints.py -q`
  - `pytest tests/test_security_api.py -q`
  - `pytest tests/test_file_manager_api.py -q`
- 开始执行批次 C：补齐首轮审查中剩余的高优先级接口鉴权、异常脱敏、CI 与前端客户端一致性问题。
- 为监控接口新增失败测试：验证 `/monitor/metrics`、`/monitor/db-pool/status` 未认证访问必须失败，并保留 `/monitor/health` 为公开健康检查。
- 完成监控接口最小修复：`app/api/monitoring.py` 中本轮覆盖的敏感只读端点统一增加 `require_api_key`。
- 为 Cloud Drive 读取接口新增失败测试：验证 `GET /api/cloud_drive/` 与 `GET /api/cloud_drive/{id}` 未认证访问失败。
- 完成 Cloud Drive 最小修复：`app/api/cloud_drive.py` 中列表与详情读取接口增加 `require_api_key`。
- 为 Quark SDK 与 system config 新增失败测试：验证内部异常不会经 `detail=str(e)` 直接透传到客户端。
- 完成异常脱敏最小修复：
  - `app/api/quark_sdk.py` 中文件列表、搜索接口 500 响应改为通用错误消息；
  - `app/api/system_config.py` 中 metadata / get / update / ai-providers 相关 500 响应改为通用错误消息。
- 为 CI workflow 新增静态回归测试：验证单元测试步骤不再 `|| true`，且汇总阶段会把 `pre-build-tests` 失败视为整体失败。
- 完成 CI 最小修复：`.github/workflows/docker-deploy-test.yml` 已移除单测步骤的忽略失败行为，并把 `pre-build-tests` 纳入最终失败条件。
- 为前端 auth store 新增回归测试：约束登录、登出、鉴权检查必须复用共享 `@/api/index` 客户端。
- 完成前端最小修复：`web/src/stores/auth.ts` 已移除本地重复 axios 客户端，统一改为使用共享 `api`，并适配共享客户端的返回结构。
- 已完成批次 C 的最小验证：
  - `pytest tests/test_monitoring_api.py tests/test_cloud_drive_api.py tests/test_system_config_api.py tests/test_quark_sdk_api.py tests/test_ci_workflow.py -q`
  - `npm --prefix web run test:run -- src/stores/auth.spec.ts src/router/index.spec.ts src/features/auth/views/LoginView.spec.ts`
