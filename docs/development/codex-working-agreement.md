# Codex 工作约定

**最后校验**: 2026-04-20  
**适用范围**: `quark_strm/` 当前审查与收敛阶段  
**配套基线**: [`../architecture/current-state.md`](../architecture/current-state.md)、[`./compatibility-inventory.md`](./compatibility-inventory.md)、[`../plans/2026-04-20-codex-project-audit-optimization-plan.md`](../plans/2026-04-20-codex-project-audit-optimization-plan.md)

## 1. 开始前先看什么

1. 先看 [`current-state.md`](../architecture/current-state.md)，确认当前唯一入口、CI 真相源和高风险热点。
2. 如果改前端根级路径或迁移 feature，再看 [`compatibility-inventory.md`](./compatibility-inventory.md)。
3. 如果改 API 路由或对外路径，再看 `docs/api/README.md`。
4. 如果改部署、运行目录或命令，再看 `docs/operations/README.md`。
5. 如果改 `config/db/exception` 相关入口，再看 [`../architecture/core-truth-source-boundaries.md`](../architecture/core-truth-source-boundaries.md)。

## 2. 默认执行原则

1. 先改 canonical path，不先堆 wrapper。
2. 新后端公共接口默认落在 `app/api/v1/*`；legacy 根级 `app/api/*.py` 只继续承担兼容或 support 责任。
3. 新前端业务代码默认落在 `web/src/features/<domain>/`；根级 `web/src/views/*`、`web/src/api/*`、`web/src/components/*`、`web/src/stores/*` 只保留薄包装。
4. 删除任何 legacy/wrapper 前，先补映射、清单或 contract test。
5. 只做单主题提交，不把 API、前端、CI、docs 混在一起。

## 3. 当前已确认的不要碰区域

- `web/src/features/config/*` 当前已有大量未提交改动；除非是明确低 blast radius 的修复，否则先不要继续深入。
- `docs/architecture/README.md` 已有独立脏改动；需要补信息时，优先写入新的基线文档或干净索引文件。
- 工作树中存在大量与本轮目标无关的用户改动；提交时只包含本轮明确修改的文件。

## 4. 最小验证基线

按主题执行最小充分验证，不跳过：

- 文档/索引/清单改动：
  - `.venv\\Scripts\\python.exe -m pytest tests/test_baseline_docs_contract.py tests/test_file_index_contract.py -q`
- CI/workflow 或部署契约改动：
  - `.venv\\Scripts\\python.exe -m pytest tests/test_ci_workflow.py tests/test_pytest_workflow_coverage_gate.py tests/test_deployment_contract.py -q`
- API 路径或 API 文档改动：
  - `.venv\\Scripts\\python.exe -m pytest tests/test_api_docs_contract.py tests/test_api_v1_routes.py tests/test_main_entrypoint.py -q`
- 前端 canonical import、feature API 或 wrapper 改动：
  - `pnpm run lint --fix`
  - `pnpm run type-check`
  - `pnpm exec vitest run src/features/file-manager/api/fileManager.spec.ts src/features/file-manager/module-aliases.spec.ts src/features/proxy/views/ProxyServiceView.spec.ts`

## 5. 提交前自检

1. 这次修改是否让“唯一入口、唯一契约、唯一门禁”更清楚，而不是更模糊。
2. 是否只动了必要文件，且没有把用户已有脏改动捎带进提交。
3. 是否留下了清单、映射、测试或文档，而不是只改实现不补真相源。

## 6. 当前推荐顺序

1. 先收敛 docs 与 contract test。
2. 再处理低风险的 API/compatibility truth-source gap。
3. 最后再进入大页面拆分或基础设施重构。
