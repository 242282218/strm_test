# config/db/exception 真相源边界

**最后校验**: 2026-04-20  
**适用范围**: `app/config/`、`app/core/`、`app/services/config_service.py`  
**进入时机**: 在进入 Phase 3 的 `config/db/exception` 收敛前先读

## 1. 数据库入口怎么判断

### `app/core/db.py`

- 当前 SQLAlchemy engine/session 的主入口。
- `get_engine()`、`SessionLocal`、`get_db()`、`get_db_session()`、`init_db()` 都在这里。
- 连接池类型切换、SQLite PRAGMA、连接池健康检查也集中在这里。
- `resolve_db_path()` 当前对相对路径按当前工作目录解析，不会自动把数据库文件放进 `data/`。

当前建议：

1. 新的 ORM 会话生命周期优先走 `app.core.db`。
2. 新的 engine/session 能力不要绕过这里直接平铺到其他 `db_*` 文件。

### `app/core/database.py`

- 当前是 `Database` 兼容层，不是新的主入口。
- 内部已经通过 `app.core.db.get_db_session()` 和 ORM 模型工作。
- 主要价值是兼容旧的 `save_strm/get_strm/save_record/...` 调用面。

当前建议：

1. 不在这里继续堆新的数据库能力。
2. 只在确有历史调用兼容需求时保留或缩减它。

### `app/core/db_utils.py`

- 当前定位是查询优化/批处理辅助工具。
- 不拥有 engine、session 或配置真相源。
- 适合承载 `BatchQueryHelper`、`QueryOptimizer` 这类 helper，不适合作为数据库入口。

## 2. 异常入口怎么判断

### `app/core/error_codes.py`

- 当前唯一错误码枚举、HTTP 状态码映射和前端消息映射所在地。
- `ErrorCode`、`ERROR_HTTP_STATUS`、`ERROR_MESSAGES` 是当前 canonical contract。

### `app/core/exceptions.py`

- 当前领域异常层。
- `AppException` 基类和 `AuthException`、`ExternalServiceException`、`BusinessException` 等层级都在这里。
- 异常对象如何表达 `code/message/detail/retry_after` 也在这里定义。

### `app/core/exception_handler.py`

- 当前 FastAPI 异常处理层。
- 负责把 `AppException`、`HTTPException`、`RequestValidationError` 和兜底异常转换成统一响应。
- `ErrorResponse`、request id、5xx/502/503/504 的响应边界在这里收口。

当前建议：

1. 新错误码只加到 `error_codes.py`。
2. 新领域异常只加到 `exceptions.py`。
3. HTTP 响应表现和脱敏策略只改 `exception_handler.py`，不要把 API 响应逻辑塞回异常类。

## 3. 配置入口怎么判断

### `app/config/settings.py`

- 当前仍是配置 schema 和环境变量归一化的主文件。
- `AppConfig`、Pydantic 子配置模型、环境变量覆盖、占位符替换都集中在这里。
- 这是进入 Phase 3 前必须承认的现实真相源，但它仍然过大。

### `app/services/config_service.py`

- 当前是运行时配置 facade。
- `get_config_service()` 提供单例入口，内部还承载了加载、保存、watcher、回滚、回调通知等多职责。
- `app/api/tmdb.py`、`app/api/stable_stream.py`、`app/api/emby_gateway.py`、`app/api/proxy.py`、`app/api/emby.py` 与 `app/core/dependencies.py` 的运行态配置 caller 都已收口到这里；TMDB key 读取顺序固定为 `tmdb.api_key` 优先、`api_keys.tmdb_api_key` 回退，稳定播放入口、专用 Emby 网关、代理入口、本地 Emby 入口与依赖注入层的 Quark cookie / only_video / root_id 也都改为运行时从 `AppConfig` 读取。
- 这意味着它是运行时入口，但还不是理想的单一职责设计。

当前建议：

1. 运行时读写配置优先通过 `get_config_service()`，不要新写一套旁路。
2. API 层如果只是读取运行态配置，直接取 `AppConfig` 字段，不要在 route 里实例化 `ConfigManager`。
3. schema、环境变量归一化问题优先回到 `settings.py` 解决。
4. watcher/rollback/notification 的进一步拆分应在后续收敛里做，不要先用 workaround 再叠一层。

## 4. 当前不要误判的点

- `app/core/database.py` 不是新的数据库主入口，它已经退化为兼容层。
- `app/core/db_utils.py` 不是 engine/session 入口，它只是工具层。
- `app/core/exceptions.py` 和 `app/core/exception_handler.py` 不是重复模块：前者定义异常语义，后者定义 HTTP 响应表现。
- `app/config/settings.py` 虽然过大，但当前确实还是配置 schema 真相源；如果不先明确这一点，后续很容易把新字段散落到别处。
- `app/api/tmdb.py`、`app/api/stable_stream.py`、`app/api/emby_gateway.py`、`app/api/proxy.py`、`app/api/emby.py` 与 `app/core/dependencies.py` 已不再走 `config_manager` compatibility path，但 `app/api/quark.py` 仍保留 `get_config()` 兼容读取，不能误判为 API 层已经彻底退掉 `config_manager`。

## 5. 推荐验证锚点

- 数据库/连接池相关：`tests/test_db.py`、`tests/test_db_pool.py`
- 配置/API 相关：`tests/test_system_config_api.py`、`tests/test_tmdb_api.py`、`tests/test_stable_stream_route.py`、`tests/test_emby_gateway.py`、`tests/test_dependencies.py`、`tests/test_db_path_contract.py`
- 异常/安全相关：`tests/test_encryption.py`

进入真正的 Phase 3 代码收敛前，应先以这份边界文档为入口，再决定哪些模块是“继续保留的 facade”，哪些才是应该下沉或删除的兼容层。
