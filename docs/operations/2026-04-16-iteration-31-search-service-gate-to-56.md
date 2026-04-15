# 2026-04-16 Iteration 31: Search Service Coverage & Gate to 56

## 当前状态判断
- 门槛 `55` 已可稳定通过，但 `app/services/search_service.py` 仅 `8.08%` 覆盖，搜索链路缺少有效回归保护。
- 本轮新增 `tests/test_search_service.py` 后，`search_service.py` 覆盖率提升到 `94.95%`。
- 全量覆盖率提升到 `56.29%`，满足将 CI 门槛从 `55` 上调到 `56` 的条件。

## 对标项目可借鉴点
- 成熟搜索模块通常优先覆盖“请求失败、结果转换、过滤排序、分页返回”四类路径。
- 外部依赖（HTTP、评分引擎、大小探测）用 fake/mocking 固定行为，确保单测稳定性和执行速度。
- 覆盖率门槛继续采用“补高价值低覆盖模块 + 小步上调 + 守护测试”闭环。

## 差距清单（按 P0/P1/P2/P3）
- P1: `search_service` 核心流程缺少分支测试。
  - 影响：搜索结果质量和错误反馈容易回归。
  - 根因：历史仅有 API 层少量验证，service 层决策分支未覆盖。
  - 建议：补齐类型映射、结果转换、大小过滤、排序分页、异常返回分支。
- P1: CI 门槛仍是 `55`，低于当前稳定可达覆盖率。
  - 影响：质量信号收敛滞后。
  - 建议：门槛上调到 `56` 并同步守护断言。

## 本轮要做的优化项
- 新增 `tests/test_search_service.py`，补齐 `search_service` 核心分支。
- 将 `.github/workflows/pytest.yml` 默认 `COVERAGE_FAIL_UNDER` 从 `55` 提升到 `56`。
- 同步 `tests/test_pytest_workflow_coverage_gate.py` 下限断言到 `>=56`。
- 执行门槛守护回归与全量 `--cov-fail-under=56` 强校验。

## 具体修改方案
- 新增 `quark_strm/tests/test_search_service.py`
  - 覆盖：
    - 云盘类型映射与结果转换打分逻辑
    - 大小过滤的 early-return、top20 过滤、无大小数据保留分支
    - `score/confidence/quality/time/size` 排序分支
    - `search` 的空关键词、业务错误、连接错误、通用异常、成功分页与参数映射
    - `search_with_filters` 的错误透传与阈值过滤
- 更新 `quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER: "56"`
- 更新 `quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - 测试名改为 `..._not_below_56`
  - 下限断言改为 `>=56`

## 验证方案
- 模块测试：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_search_service.py`
- 模块覆盖：
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.services.search_service --cov-report=term-missing' tests/test_search_service.py`
- 门槛守护回归：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_search_service.py tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py`
- 全量强校验：
  - `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=56'`
- 结果：
  - `tests/test_search_service.py`：`13 passed`
  - `app/services/search_service.py`：`94.95%`
  - 全量：`856 passed, 2 skipped`
  - 总覆盖率：`56.29%`

## 本轮风险
- 门槛 `56` 当前缓冲约 `0.29%`，可用但偏窄。
- 下一轮要上调到 `57` 需继续补低覆盖高权重模块，避免零缓冲抬升。

## 下一轮建议
1. 优先补 `app/services/ai_connectivity_service.py` 的网络异常与配置分支，扩大短平快缓冲。
2. 视覆盖率提升幅度再评估 `57` 门槛，不满足缓冲则继续补 service 层盲区。
3. 保持“模块补测 -> 全量强校验 -> 门槛上调”节奏。
