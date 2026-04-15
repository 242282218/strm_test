# 2026-04-16 Iteration 24: Core Utility Coverage Expansion & Gate to 49

## 当前状态判断
- 门槛 `48` 轮次后全量覆盖率约 `48.16%`，缓冲不足以直接抬升到 `49`。
- `db_loader`、`token_monitor`、`nfo_generator` 仍存在可快速补齐的低耦合覆盖盲区。
- 项目当前大量改动未提交，优先做“外科式”补测以降低冲突风险。

## 对标项目可借鉴点
- 成熟项目抬升 coverage gate 前，会优先清理 0%/低覆盖基础模块（工具层、兼容层、定时任务层），以最小改动获得最大覆盖收益。
- 对配置/监控类后台任务，常见做法是用 mock 驱动的契约测试覆盖“成功、失败、告警、清理”路径，避免依赖真实外部服务。
- 对输出序列化组件（如 NFO/XML 生成器）通常用结构断言（解析 XML）而非字符串整段比对，减少测试脆弱性。

## 差距清单（按 P0/P1/P2/P3）
- P1: `app/core/db_loader.py` 历史覆盖为 0%，模型映射与 unknown 类型分支无保护。
  - 影响：查询优化策略可能被静默改坏，导致 N+1 或加载策略偏差。
  - 改法：补齐选项映射、路由、异常分支测试。
- P1: `app/services/token_monitor.py` 缺少失败告警与循环分支回归。
  - 影响：生产 token 失效告警链路可能失效但无检测。
  - 改法：补充 token 检查成功/失败、通知失败、循环路径测试。
- P2: `app/services/nfo_generator.py` 输出结构无契约测试。
  - 影响：媒体库元数据格式回归难以及时发现。
  - 改法：对 movie/tv/episode NFO 做 XML 结构断言。

## 本轮要做的优化项
- 新增 `tests/test_db_loader.py` 补齐查询优化器核心分支。
- 新增 `tests/test_token_monitor.py` 补齐 token 监控核心分支。
- 新增 `tests/test_nfo_generator.py` 补齐 NFO 结构输出分支。
- 覆盖率门槛由 `48` 上调到 `49`，同步守护测试下限。

## 具体修改方案
- `quark_strm/tests/test_db_loader.py`
  - 覆盖 load strategy wrapper、`apply_options` 分支、`create_optimized_select` 路由与 ValueError。
- `quark_strm/tests/test_token_monitor.py`
  - 覆盖无 cookie、有效 cookie、token 检测失败触发高优告警、告警发送失败日志、循环执行分支。
- `quark_strm/tests/test_nfo_generator.py`
  - 覆盖电影/剧集/分集 NFO 的必填字段与可选字段省略行为（XML 解析断言）。
- `quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER` 从 `48` 提升到 `49`。
- `quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - workflow 断言下限提升到 `>=49`。

## 验证方案
- 目标测试：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_db_loader.py`
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_token_monitor.py`
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_nfo_generator.py`
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py tests/test_token_monitor.py tests/test_nfo_generator.py tests/test_db_loader.py`
- 模块覆盖：
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.core.db_loader --cov-report=term-missing' tests/test_db_loader.py`
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.services.token_monitor --cov-report=term-missing' tests/test_token_monitor.py`
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.services.nfo_generator --cov-report=term-missing' tests/test_nfo_generator.py`
- 全量强校验：
  - `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=49'`
- 结果：
  - 全量 `778 passed, 2 skipped`；
  - 总覆盖率 `49.01%`，满足门槛 `49`。

## 本轮风险
- 门槛 `49` 当前缓冲较小（约 `0.01%`），若引入新大模块或低覆盖改动，CI 可能抖动。
- 高体量低覆盖模块仍集中在 `services/media/*`、`services/integrations/*`、`core/*_queue/*_monitor`。

## 下一轮建议
1. 优先补 `app/services/integrations/quark.py` 的核心交互分支，提升大体量模块覆盖。
2. 次优先补 `app/core/db_pool_monitor.py` 或 `app/core/db_write_queue.py` 的关键异常/统计路径。
3. 在总覆盖率稳定 `49.5%+` 前，不建议上调至 `50`，先扩缓冲再抬门槛。
