# AI 开发指导 - 智能重命名夸克云盘集成

## 🎯 开发任务概述

你需要完成智能重命名功能的夸克云盘集成，当前用户点击"浏览文件夹"按钮时显示"功能开发中"，你的任务是实现完整的夸克云盘文件浏览器，使用户能够选择云盘文件夹并对其中的媒体文件进行智能重命名。

## 📋 核心开发任务

### 后端开发（优先级：高）

**第一步：扩展 QuarkService** (`app/services/quark_service.py`)
- 添加 `list_files(pdir_fid, page, size)` 方法，调用夸克 API 获取文件列表
- 添加 `rename_file(fid, new_name)` 方法，重命名单个文件
- 添加 `move_file(fid, to_pdir_fid, new_name)` 方法，移动文件到指定目录
- 所有方法需添加函数级注释说明用途、输入、输出与副作用，并实现错误处理和重试机制

**第二步：新增 API 端点** (`app/api/quark.py`)
- 实现 `GET /api/quark/browse` 端点，支持参数 pdir_fid（默认"0"）、page、size、file_type（video/folder/all），返回文件列表，需过滤文件类型（视频文件扩展名：.mp4/.mkv/.avi/.mov/.wmv/.flv）
- 实现 `POST /api/quark/smart-rename-cloud` 端点，接收 QuarkSmartRenameRequest（包含 pdir_fid、algorithm、naming_standard、options），调用 SmartRenameService 对云盘文件进行解析和 TMDB 匹配，返回预览结果（包含 batch_id、items 列表）
- 实现 `POST /api/quark/execute-cloud-rename` 端点，接收 QuarkRenameExecuteRequest（包含 operations 数组），批量调用 quark_service.rename_file，返回执行结果统计
- 定义 Pydantic 模型：QuarkSmartRenameRequest、QuarkRenameExecuteRequest、QuarkRenameOperation

### 前端开发（优先级：高）

**第一步：创建文件浏览器组件** (`web/src/components/QuarkFileBrowser.vue`)
- 创建对话框组件，接收 modelValue（boolean）props，emit update:modelValue 和 select(fid, path) 事件
- 实现面包屑导航（breadcrumbs 数组，初始为 [{fid: '0', name: '根目录'}]），点击可返回上级目录
- 实现文件列表展示（表格布局：名称、类型、大小、修改时间），文件夹显示 Folder 图标，文件显示 Document 图标
- 实现文件选择逻辑（单选文件夹，selectedFid 和 selectedItem 状态），双击文件夹进入子目录
- 实现分页功能（currentPage、pageSize、total），调用 browseQuarkDirectory API
- 添加 Loading 状态和错误处理，使用 ElMessage 显示错误信息

**第二步：实现 API 客户端** (`web/src/api/quark.ts`)
- 定义 TypeScript 接口：QuarkBrowseRequest、QuarkFileItem、QuarkSmartRenameRequest、QuarkRenameExecuteRequest
- 实现 API 函数：browseQuarkDirectory、smartRenameCloudFiles、executeCloudRename，使用 api.get/post 调用后端接口

**第三步：集成到智能重命名页面** (`web/src/views/SmartRenameView.vue`)
- 导入 QuarkFileBrowser 组件，添加 showQuarkBrowser、isCloudMode、selectedCloudFid 状态
- 修改 openPathSelector 函数，使用 ElMessageBox.confirm 让用户选择"夸克云盘"或"本地文件"，选择云盘时设置 isCloudMode=true 并显示 showQuarkBrowser=true
- 添加 handleCloudFolderSelect(fid, path) 函数，保存 selectedCloudFid 和显示路径为"夸克云盘: {path}"
- 修改 startAnalysis 函数，根据 isCloudMode 调用不同 API（云盘模式调用 smartRenameCloudFiles，本地模式调用 previewSmartRename）
- 修改 executeRename 函数，云盘模式调用 executeCloudRename API，传入 operations 数组（从 selectedItems 构建）

## 🔑 关键技术要点

**夸克 API 集成**：所有夸克 API 调用需要 Cookie 认证（__puus），使用现有的 QuarkAPIClient（app/services/quark_api_client_v2.py），调用 list、rename、move 方法，注意添加请求间隔（100-200ms）避免限流

**智能重命名流程**：复用现有 SmartRenameService 的 _parse_with_algorithm 和 _match_tmdb 方法，对云盘文件名进行解析，使用 _generate_new_name 生成符合 Emby 规范的新文件名，云盘模式使用 fid 作为文件标识而非本地路径

**错误处理**：后端捕获异常返回 HTTPException（401 未授权、404 资源不存在、429 限流、500 服务器错误），前端使用 try-catch 捕获错误并用 ElMessage.error 显示友好提示，网络错误建议重试

**性能优化**：文件列表分页加载（默认 50 条/页），批量重命名分批执行（建议每批 50 个文件），添加 Loading 状态提升用户体验

## ⚠️ 必须遵守的规则

1. **函数注释**：所有新增函数必须添加函数级注释，说明用途、输入参数、输出结果、副作用
2. **错误处理**：所有 API 调用必须包含 try-catch，失败时明确标记 FAIL 并等待人工决策，不得自动重试超过 3 次
3. **代码规范**：遵循项目现有代码风格，Python 使用 async/await，TypeScript 使用 async/await 和类型注解
4. **测试验证**：每完成一个模块立即进行手动测试，使用 Postman 测试后端 API，使用浏览器测试前端功能
5. **渐进式开发**：按照后端 → 前端 → 集成的顺序开发，每个阶段完成后验证再进入下一阶段

## 📊 验收标准

功能完整性：用户点击"浏览文件夹"可选择"夸克云盘"，显示云盘目录树，可浏览文件夹并选择，点击"扫描媒体文件"能分析云盘文件并显示预览结果，确认后能批量重命名云盘文件

性能要求：文件列表加载 < 2秒，智能分析 100 个文件 < 5秒，批量重命名执行时间合理

用户体验：界面友好、操作直观、加载状态明确、错误提示清晰

稳定性：无崩溃、错误处理完善、边界情况处理正确

## 📚 参考文档

详细技术方案见 `docs/development/smart_rename_quark_integration.md`，API 接口定义见 `docs/api/smart_rename_api.md`，任务清单见 `docs/development/smart_rename_implementation_checklist.md`，现有代码参考 `app/api/smart_rename.py`、`app/services/smart_rename_service.py`、`web/src/views/SmartRenameView.vue`

---

**开始开发前请先阅读上述三个参考文档，理解整体架构后再动手编码，遇到问题及时标记 FAIL 并说明原因，不要盲目尝试！**
