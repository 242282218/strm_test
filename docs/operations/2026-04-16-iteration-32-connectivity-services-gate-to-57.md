# 2026-04-16 Iteration 32: Connectivity + Core Services Coverage & Gate to 57

## 当前状态判断
- 门槛 `56` 阶段已稳定，但距离 `57` 仍存在明显缺口。
- `ai_connectivity_service` 与 `cloud_drive/file_manager/proxy` 三类 service 模块覆盖偏低，且分支集中在真实业务调用链路。
- 本轮补测后总覆盖率提升到 `57.19%`，可稳定支撑门槛上调到 `57`。

## 对标项目可借鉴点
- 成熟后端项目会优先补“服务层编排逻辑 + 异常返回契约”，再收紧全局覆盖门槛。
- 对外部依赖（aiohttp、网盘 SDK、存储 provider）统一采用 fake 依赖隔离，保障测试稳定性。
- 门槛提升继续执行“补测核心 service -> 全量强校验 -> 门槛守护同步”。

## 差距清单（按 P0/P1/P2/P3）
- P1: `ai_connectivity_service` 对配置归一化、网络异常和并发探活缺少系统回归。
  - 影响：AI 连通性探测结果可能回归且不易发现。
  - 建议：补齐 helper 分支、test_provider 成功/失败/异常、test_providers 去重与默认分支。
- P1: `cloud_drive_service`、`file_manager_service`、`proxy_service` 服务层分支历史覆盖不足。
  - 影响：文件管理和代理链路异常路径缺乏保护。
  - 建议：补齐 CRUD、错误包装、缓存命中/回源、上下文关闭等路径。
- P1: CI 门槛仍在 `56`，低于当前稳定能力。
  - 建议：上调到 `57` 并同步守护测试断言。

## 本轮要做的优化项
- 扩展 `tests/test_ai_connectivity_service.py` 覆盖核心分支。
- 新增 `tests/test_cloud_drive_service.py`、`tests/test_file_manager_service.py`、`tests/test_proxy_service.py`。
- 将 `.github/workflows/pytest.yml` 默认门槛从 `56` 提升到 `57`。
- 同步 `tests/test_pytest_workflow_coverage_gate.py` 到 `>=57`。

## 具体修改方案
- 更新 `quark_strm/tests/test_ai_connectivity_service.py`
  - 覆盖 `_first_non_empty`、`_coerce_timeout`、`_format_exception_message`、provider config fallback。
  - 覆盖 `test_provider` 的未配置、HTTP 200、HTTP 非 200、超时异常分支。
  - 覆盖 `test_providers` 的默认 provider、输入去重与并发调度分支。
- 新增 `quark_strm/tests/test_cloud_drive_service.py`
  - 覆盖 drive CRUD、默认 drive 查询、cookie 检查成功/失败/非 quark/缺失分支。
- 新增 `quark_strm/tests/test_file_manager_service.py`
  - 覆盖 provider 初始化异常分支、browse 路径处理、move/delete/rename/mkdir/unknown action 分支。
- 新增 `quark_strm/tests/test_proxy_service.py`
  - 覆盖缓存命中/回源、异常抛出、context manager、clear/stats/close。
- 更新门槛文件
  - `quark_strm/.github/workflows/pytest.yml` -> `COVERAGE_FAIL_UNDER: "57"`
  - `quark_strm/tests/test_pytest_workflow_coverage_gate.py` -> `>=57`

## 验证方案
- 目标测试：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_ai_connectivity_service.py tests/test_cloud_drive_service.py tests/test_file_manager_service.py tests/test_proxy_service.py`
- 模块覆盖：
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.services.ai_connectivity_service --cov-report=term-missing' tests/test_ai_connectivity_service.py`
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.services.cloud_drive_service --cov=app.services.file_manager_service --cov=app.services.proxy_service --cov-report=term-missing' tests/test_cloud_drive_service.py tests/test_file_manager_service.py tests/test_proxy_service.py`
- 门槛守护回归：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_ai_connectivity_service.py tests/test_cloud_drive_service.py tests/test_file_manager_service.py tests/test_proxy_service.py tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py`
- 全量强校验：
  - `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=57'`
- 结果：
  - 全量：`896 passed, 2 skipped`
  - 总覆盖率：`57.19%`
  - `ai_connectivity_service.py`：`98.69%`
  - `file_manager_service.py`：`93.90%`
  - `proxy_service.py`：`97.83%`

## 本轮风险
- 门槛 `57` 当前缓冲约 `0.19%`，仍偏窄。
- 后续继续上调前，需要继续补高体量低覆盖 service 模块，避免门槛震荡。

## 下一轮建议
1. 优先补 `app/services/notification_service.py` 核心分支。
2. 结合 `notification/*` 子模块与接口层验证，扩大 `58` 门槛缓冲。
3. 保持“模块补测 + 全量强校验 + 渐进门槛”策略。
