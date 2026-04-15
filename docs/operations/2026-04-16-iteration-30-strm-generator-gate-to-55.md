# 2026-04-16 Iteration 30: STRM Generator Coverage & Gate to 55

## 当前状态判断
- 门槛 `54` 阶段已稳定通过，但 `app/services/media/strm_generator.py` 作为 STRM 生成主链路仍存在分支盲区。
- 本轮新增 `tests/test_media_strm_generator_extra.py` 后，`strm_generator.py` 覆盖率提升到 `96.89%`，并且全量总覆盖率稳定在 `55.56%`。
- 基于当前缓冲（`+0.56%`），可将 CI 覆盖率门槛从 `54` 上调到 `55`。

## 对标项目可借鉴点
- 成熟媒体工具项目会优先补“核心生成链路 + 异常退化 + 批量并发”分支，再做覆盖率门槛上调。
- 门槛提升必须包含双守护：workflow 参数化阈值 + 本地断言测试，避免后续回退。
- 对外部依赖（网盘 API、配置、映射服务）通过 stub/mocking 保持单测确定性，避免脆弱 E2E 依赖。

## 差距清单（按 P0/P1/P2/P3）
- P1: `strm_generator` 关键分支（URL 模式切换、递归扫描异常、批量统计）历史覆盖不足。
  - 影响：STRM 产出异常时缺少快速回归信号。
  - 根因：此前仅覆盖基础路径，异常和边界组合未系统补测。
  - 建议：补齐模式分支、异常分支、并发/限流统计分支。
- P1: CI 门槛仍是 `54`，低于当前稳定覆盖率。
  - 影响：质量信号收敛速度慢于项目当前测试能力。
  - 建议：门槛上调到 `55` 并同步守护测试。

## 本轮要做的优化项
- 新增 `tests/test_media_strm_generator_extra.py`，补齐 `strm_generator` 核心分支与异常路径。
- 将 `.github/workflows/pytest.yml` 默认 `COVERAGE_FAIL_UNDER` 从 `54` 提升到 `55`。
- 同步 `tests/test_pytest_workflow_coverage_gate.py` 下限断言到 `>=55`。
- 执行门槛守护回归与全量 `--cov-fail-under=55` 强校验。

## 具体修改方案
- 新增 `quark_strm/tests/test_media_strm_generator_extra.py`
  - 覆盖：
    - base_url 修复与非法 `strm_url_mode` 分支
    - `_get_all_files` 递归/非递归、视频过滤与 service 异常分支
    - `_generate_video_url` 四种模式（redirect/stream/direct/webdav）
    - `_generate_single_strm` 的创建、跳过、覆盖与 URL 异常抛出
    - `generate_strm_files` 的 `max_files` 限制、并发下统计与异常聚合
    - `generate_strm_from_quark` 的配置回落、cookie 必填和 close 释放
- 更新 `quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER: "55"`
- 更新 `quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - 阈值守护测试名改为 `..._not_below_55`
  - 下限断言改为 `>=55`

## 验证方案
- 门槛守护回归：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_media_strm_generator_extra.py tests/test_strm_generator.py tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py`
- 全量强校验：
  - `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=55'`
- 结果：
  - 子集回归：`19 passed`
  - 全量：`843 passed, 2 skipped`
  - 总覆盖率：`55.56%`
  - `app/services/media/strm_generator.py`：`96.89%`

## 本轮风险
- 门槛 `55` 当前缓冲约 `0.56%`，可用但不算宽裕。
- 高体量低覆盖模块（如 `search_service`、`notification_service`、`media/scrape`）仍是下一轮门槛上调主要阻力。

## 下一轮建议
1. 优先补 `app/services/search_service.py` 的请求错误路径、大小过滤与排序分支，扩大门槛缓冲。
2. 次优先补 `app/services/notification_service.py` 初始化/规则匹配/日志落库异常分支。
3. 覆盖率稳定 `56%+` 后再评估将门槛上调到 `56`。
