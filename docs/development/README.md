# 开发文档

**最后同步**: 2026-04-20

## 当前执行入口

- [`codex-working-agreement.md`](./codex-working-agreement.md) - 给 Codex/维护者的固定执行入口与最小验证基线
- [`compatibility-inventory.md`](./compatibility-inventory.md) - 前端根级 wrapper 清单、状态与删除条件
- [`../architecture/current-state.md`](../architecture/current-state.md) - 当前后端/前端/CI 基线与热点分布

## 开发环境搭建

### 前置要求

- Python 3.11+
- Node.js 22+
- Docker + Docker Compose (可选)
- Git

### 后端开发环境

```bash
# 1. 克隆仓库
git clone <repository-url>
cd quark_strm

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp config.example.yaml config.yaml
# 编辑 config.yaml 填入必要配置

# 5. 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端开发环境

```bash
# 1. 进入前端目录
cd web

# 2. 安装依赖（二选一）
npm ci
# 或：pnpm install

# 3. 启动开发服务器
pnpm run dev

# 4. 最小验证基线
pnpm run lint --fix
pnpm run type-check
pnpm run test:run
pnpm run build-only
```

说明：

- `npm ci` 与 `web/package-lock.json` 一起构成当前 CI/干净安装的真相源。
- `pnpm run ...` 是当前本地开发与人工回归的默认脚本入口。
- 这不代表仓库已经完成 `pnpm-lock.yaml` 迁移；如需完全复现 CI，优先使用 `npm ci`。

## 代码规范

### Python

- 使用 `ruff` 进行代码 linting
- 使用 `pyright` 进行类型检查
- 遵循 PEP 8 风格指南
- 所有公共 API 必须有类型注解
- 网络重试统一走 `app.core.retry`，禁止在业务服务中直接引入 `tenacity` 装饰器

```bash
# 代码检查
ruff check app/
pyright app/

# 自动格式化
ruff format app/
```

### 重试策略约定

- 默认网络瞬时错误重试：`from app.core.retry import retry_on_transient`
- 命名策略重试：`from app.core.retry import retry_with_policy`
  - 当前内置策略：`default`、`tmdb`
- 新增重试场景时，先在 `app/core/retry.py` 注册策略，再在服务层引用，避免分散实现。

### TypeScript/Vue

- 使用 ESLint v9 进行代码 linting
- 使用 TypeScript strict 模式
- Vue 组件使用 `<script setup>` 语法
- 所有组件和函数必须有类型定义

```bash
# 代码检查
pnpm run lint --fix
```

## 测试

### 运行测试

当前 CI coverage 门槛真相源在 `.github/workflows/pytest.yml` 与 `.github/workflows/docker-deploy-test.yml`，统一来自 `vars.QUARK_STRM_COVERAGE_FAIL_UNDER`，未配置时回退 `66`。

```bash
# 后端全量测试（模拟当前 workflow 默认门槛）
python -m pytest tests/ -v --tb=short --cov=app --cov-report=term-missing --cov-fail-under=66

# 前端单元/组件测试
cd web
pnpm run test:run

# 前端启动 smoke
pnpm run test:smoke

# 端到端测试
pnpm run test:e2e

# 需要隔离端口时
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3001 VITE_API_PROXY_TARGET=http://127.0.0.1:18000 pnpm run test:e2e
```

### 编写测试

- 单元测试放在 `tests/unit/`
- 集成测试放在 `tests/integration/`
- 测试文件命名：`test_*.py`
- 使用 `pytest` fixtures 进行依赖注入

## 项目结构

### 后端模块

| 模块 | 说明 |
|------|------|
| `app/api/` | API 端点定义 |
| `app/config/` | 配置管理 |
| `app/core/` | 核心工具类、中间件、异常处理 |
| `app/models/` | SQLAlchemy ORM 模型 |
| `app/services/` | 业务逻辑服务 |

### 前端模块

采用特性模块化结构：

```
web/src/features/
├── auth/           # 认证相关
├── dashboard/      # 仪表板
├── tasks/          # 任务管理
├── scrape/         # 刮削服务
├── emby/           # Emby 集成
├── quark/          # 夸克网盘
├── rename/         # 重命名
└── ...
```

每个特性模块包含：
- `views/` - 视图组件
- `components/` - 可复用组件
- `stores/` - Pinia 状态管理
- `api/` - API 调用
- `types/` - TypeScript 类型定义

## Git 工作流

### 分支策略

- `main` - 主分支，可部署状态
- `develop` - 开发分支
- `feature/*` - 功能分支
- `fix/*` - 修复分支
- `release/*` - 发布分支

### 提交规范

遵循 Conventional Commits：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type 类型**:
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档变更
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试相关
- `ci`: CI/CD 相关
- `chore`: 构建/工具链

**示例**:
```
feat(emby): 添加媒体库自动刷新功能

- 实现 Emby 库刷新 API
- 添加定时刷新配置
- 新增刷新历史记录

Closes #123
```

## 调试技巧

### 后端调试

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("调试信息")
```

### 前端调试

```typescript
// 使用 Vue DevTools
// 在浏览器安装 Vue.js devtools 插件

// 控制台日志
console.log('组件状态:', state)
```

## 待办事项

- [ ] 添加更多代码示例
- [ ] 补充调试指南
- [ ] 添加常见问题 FAQ
- [ ] 补充性能优化指南

## 参考链接

- [架构文档](../architecture/README.md)
- [API 文档](../api/README.md)
- [运维文档](../operations/README.md)
