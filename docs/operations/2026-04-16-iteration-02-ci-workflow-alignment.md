# 2026-04-16 Iteration 02: CI Workflow Alignment

## 当前状态判断
- `tests/test_ci_workflow.py` 之前失败，根因是测试硬编码依赖仓库外层 `.github/workflows/pytest.yml`。
- 当前仓库可提交边界在 `quark_strm/`，直接修外层文件不可版本化，导致 CI 校验不可复现。

## 对标项目可借鉴点
- 成熟项目会让测试在仓库边界内自洽，不依赖外层目录结构偶然存在。
- CI 工作流文件应与测试校验同仓库管理，避免跨仓库路径耦合。

## 差距清单（按 P0/P1/P2/P3）
- P0: CI 测试对外层路径有硬依赖，导致本仓库内回归失败。
- P1: 缺少仓库内独立 `pytest.yml`，测试意图与实际文件布局不一致。
- P2: CI/测试路径策略文档化不足，后续改动易回归。
- P3: 工作流复用程度可继续提升。

## 本轮要做的优化项
- 在仓库内补齐 `pytest.yml`。
- 修正测试路径解析策略，优先外层存在则使用，否则回退仓库内工作流。
- 跑 CI 相关回归组合测试，确认无副作用。

## 具体修改方案
- 新增 `quark_strm/.github/workflows/pytest.yml`，包含 `Run Tests` 步骤并保持失败即失败语义。
- 更新 `quark_strm/tests/test_ci_workflow.py`:
  - 增加 `resolve_workflow_path(...)`。
  - 对 `pytest.yml` 和 `ci.yml` 使用 `root -> project` 回退路径。

## 验证方案
- 定点验证: `python -m pytest -q -o addopts='--tb=short -v' tests/test_ci_workflow.py`
- 组合回归: `python -m pytest -q -o addopts='--tb=short -v' tests/test_ci_workflow.py tests/test_lifecycle.py tests/test_main_entrypoint.py tests/test_api_v1_routes.py tests/test_dependencies.py`
- 结果: `42 passed, 2 skipped`。

## 本轮风险
- 新增 `pytest.yml` 仍沿用 `--cov-fail-under=70`，在当前覆盖率基线下可能导致 CI 失败，需后续策略化处理。

## 下一轮建议
1. 将覆盖率门槛策略分层: 本地默认不阻断，CI 严格门槛保持。
2. 为 `pytest.ini` 增加注释和执行约定，减少误用。
3. 在 CI 文档中补“仓库内工作流优先级”说明。
