# 智能重命名功能完善 - 实施清单

## 📋 项目信息
- **项目名称**: 智能重命名 - 夸克云盘集成
- **开始日期**: 2026-02-04
- **预计工期**: 5-8 天
- **负责人**: 开发团队

---

## ✅ 任务清单

### 🎯 阶段 1: 后端 API 开发（2-3天）

#### 1.1 QuarkService 扩展
- [ ] **任务**: 实现 `list_files` 方法
  - **文件**: `app/services/quark_service.py`
  - **功能**: 获取指定目录下的文件列表
  - **依赖**: QuarkAPIClient
  - **测试**: 单元测试 + 手动测试
  - **预计时间**: 2小时

- [ ] **任务**: 实现 `rename_file` 方法
  - **文件**: `app/services/quark_service.py`
  - **功能**: 重命名单个文件
  - **依赖**: QuarkAPIClient
  - **测试**: 单元测试 + 手动测试
  - **预计时间**: 1小时

- [ ] **任务**: 实现 `move_file` 方法
  - **文件**: `app/services/quark_service.py`
  - **功能**: 移动文件到指定目录
  - **依赖**: QuarkAPIClient
  - **测试**: 单元测试 + 手动测试
  - **预计时间**: 1小时

- [ ] **任务**: 添加错误处理和重试机制
  - **文件**: `app/services/quark_service.py`
  - **功能**: 处理 API 错误，添加重试逻辑
  - **依赖**: 无
  - **测试**: 异常场景测试
  - **预计时间**: 2小时

#### 1.2 API 端点开发
- [ ] **任务**: 实现 `/api/quark/browse` 端点
  - **文件**: `app/api/quark.py`
  - **功能**: 浏览云盘目录
  - **依赖**: QuarkService
  - **测试**: Postman 测试
  - **预计时间**: 3小时
  - **关键代码**:
    ```python
    @router.get("/browse")
    async def browse_quark_directory(
        pdir_fid: str = Query("0"),
        page: int = Query(1, ge=1),
        size: int = Query(100, ge=1, le=500),
        file_type: Optional[str] = Query(None),
        service: QuarkService = Depends(get_quark_service)
    ):
        # 实现代码
        pass
    ```

- [ ] **任务**: 实现 `/api/quark/smart-rename-cloud` 端点
  - **文件**: `app/api/quark.py`
  - **功能**: 预览云盘文件重命名
  - **依赖**: QuarkService, SmartRenameService
  - **测试**: Postman 测试
  - **预计时间**: 4小时
  - **关键代码**:
    ```python
    @router.post("/smart-rename-cloud")
    async def smart_rename_cloud_files(
        request: QuarkSmartRenameRequest,
        quark_service: QuarkService = Depends(get_quark_service),
        rename_service: SmartRenameService = Depends(get_smart_rename_service)
    ):
        # 实现代码
        pass
    ```

- [ ] **任务**: 实现 `/api/quark/execute-cloud-rename` 端点
  - **文件**: `app/api/quark.py`
  - **功能**: 执行云盘文件重命名
  - **依赖**: QuarkService
  - **测试**: Postman 测试
  - **预计时间**: 3小时
  - **关键代码**:
    ```python
    @router.post("/execute-cloud-rename")
    async def execute_cloud_rename(
        request: QuarkRenameExecuteRequest,
        quark_service: QuarkService = Depends(get_quark_service)
    ):
        # 实现代码
        pass
    ```

- [ ] **任务**: 实现 `/api/quark/cloud-rename-status/{batch_id}` 端点
  - **文件**: `app/api/quark.py`
  - **功能**: 查询重命名状态
  - **依赖**: 数据库
  - **测试**: Postman 测试
  - **预计时间**: 2小时

#### 1.3 数据模型定义
- [ ] **任务**: 定义请求/响应模型
  - **文件**: `app/api/quark.py`
  - **功能**: Pydantic 模型定义
  - **依赖**: 无
  - **测试**: 类型检查
  - **预计时间**: 1小时
  - **模型列表**:
    - `QuarkSmartRenameRequest`
    - `QuarkRenameExecuteRequest`
    - `QuarkRenameOperation`
    - `QuarkBrowseResponse`

#### 1.4 后端测试
- [ ] **任务**: 编写单元测试
  - **文件**: `tests/test_quark_service.py`
  - **覆盖**: QuarkService 所有方法
  - **预计时间**: 3小时

- [ ] **任务**: 编写集成测试
  - **文件**: `tests/test_quark_api.py`
  - **覆盖**: 所有 API 端点
  - **预计时间**: 3小时

- [ ] **任务**: 手动测试
  - **工具**: Postman/curl
  - **场景**: 正常流程 + 异常场景
  - **预计时间**: 2小时

---

### 🎨 阶段 2: 前端组件开发（2-3天）

#### 2.1 QuarkFileBrowser 组件
- [ ] **任务**: 创建组件基础结构
  - **文件**: `web/src/components/QuarkFileBrowser.vue`
  - **功能**: 组件框架、props、emits
  - **预计时间**: 1小时

- [ ] **任务**: 实现目录树展示
  - **文件**: `web/src/components/QuarkFileBrowser.vue`
  - **功能**: 显示文件夹层级结构
  - **预计时间**: 3小时
  - **关键功能**:
    - 面包屑导航
    - 文件夹点击进入
    - 返回上级目录

- [ ] **任务**: 实现文件列表展示
  - **文件**: `web/src/components/QuarkFileBrowser.vue`
  - **功能**: 表格形式展示文件
  - **预计时间**: 2小时
  - **显示字段**:
    - 文件名
    - 类型
    - 大小
    - 修改时间

- [ ] **任务**: 实现文件选择逻辑
  - **文件**: `web/src/components/QuarkFileBrowser.vue`
  - **功能**: 单选/多选文件夹
  - **预计时间**: 2小时

- [ ] **任务**: 实现分页功能
  - **文件**: `web/src/components/QuarkFileBrowser.vue`
  - **功能**: 分页加载文件列表
  - **预计时间**: 1小时

- [ ] **任务**: 添加加载状态和错误处理
  - **文件**: `web/src/components/QuarkFileBrowser.vue`
  - **功能**: Loading、错误提示
  - **预计时间**: 1小时

#### 2.2 API 客户端
- [ ] **任务**: 定义 TypeScript 类型
  - **文件**: `web/src/api/quark.ts`
  - **功能**: 接口类型定义
  - **预计时间**: 1小时
  - **类型列表**:
    - `QuarkBrowseRequest`
    - `QuarkFileItem`
    - `QuarkSmartRenameRequest`
    - `QuarkRenameExecuteRequest`

- [ ] **任务**: 实现 API 调用函数
  - **文件**: `web/src/api/quark.ts`
  - **功能**: 封装 API 调用
  - **预计时间**: 2小时
  - **函数列表**:
    - `browseQuarkDirectory`
    - `smartRenameCloudFiles`
    - `executeCloudRename`
    - `getCloudRenameStatus`

#### 2.3 集成到智能重命名页面
- [ ] **任务**: 添加模式选择
  - **文件**: `web/src/views/SmartRenameView.vue`
  - **功能**: 本地/云盘模式切换
  - **预计时间**: 2小时
  - **UI 设计**:
    - 模式选择对话框
    - 当前模式指示器

- [ ] **任务**: 集成文件浏览器组件
  - **文件**: `web/src/views/SmartRenameView.vue`
  - **功能**: 显示/隐藏浏览器
  - **预计时间**: 1小时

- [ ] **任务**: 修改分析流程
  - **文件**: `web/src/views/SmartRenameView.vue`
  - **功能**: 支持云盘模式分析
  - **预计时间**: 3小时
  - **修改点**:
    - `startAnalysis` 函数
    - 根据模式调用不同 API

- [ ] **任务**: 修改执行流程
  - **文件**: `web/src/views/SmartRenameView.vue`
  - **功能**: 支持云盘模式执行
  - **预计时间**: 2小时
  - **修改点**:
    - `executeRename` 函数
    - 云盘重命名逻辑

#### 2.4 UI/UX 优化
- [ ] **任务**: 添加加载动画
  - **文件**: `web/src/components/QuarkFileBrowser.vue`
  - **功能**: 骨架屏、Loading
  - **预计时间**: 1小时

- [ ] **任务**: 优化错误提示
  - **文件**: `web/src/views/SmartRenameView.vue`
  - **功能**: 友好的错误信息
  - **预计时间**: 1小时

- [ ] **任务**: 响应式布局适配
  - **文件**: `web/src/components/QuarkFileBrowser.vue`
  - **功能**: 移动端适配
  - **预计时间**: 2小时

- [ ] **任务**: 添加快捷键支持
  - **文件**: `web/src/components/QuarkFileBrowser.vue`
  - **功能**: 键盘导航
  - **预计时间**: 1小时
  - **快捷键**:
    - `Enter`: 进入文件夹
    - `Backspace`: 返回上级
    - `Ctrl+A`: 全选

---

### 🧪 阶段 3: 联调测试（1-2天）

#### 3.1 功能测试
- [ ] **任务**: 测试文件浏览功能
  - **场景**: 
    - 浏览根目录
    - 进入子目录
    - 返回上级
    - 面包屑导航
  - **预计时间**: 1小时

- [ ] **任务**: 测试智能重命名预览
  - **场景**:
    - 选择文件夹
    - 开始分析
    - 查看预览结果
    - 编辑重命名项
  - **预计时间**: 2小时

- [ ] **任务**: 测试批量重命名执行
  - **场景**:
    - 选择文件
    - 执行重命名
    - 查看结果
    - 错误处理
  - **预计时间**: 2小时

- [ ] **任务**: 测试错误处理
  - **场景**:
    - 网络错误
    - 权限错误
    - 文件名冲突
    - API 限流
  - **预计时间**: 2小时

#### 3.2 性能测试
- [ ] **任务**: 测试大量文件加载
  - **场景**: 1000+ 文件的文件夹
  - **指标**: 加载时间 < 2秒
  - **预计时间**: 1小时

- [ ] **任务**: 测试批量重命名性能
  - **场景**: 100+ 文件批量重命名
  - **指标**: 执行时间合理
  - **预计时间**: 1小时

- [ ] **任务**: 优化 API 调用频率
  - **方法**: 添加节流/防抖
  - **预计时间**: 1小时

#### 3.3 用户测试
- [ ] **任务**: 邀请用户试用
  - **人数**: 3-5 人
  - **预计时间**: 2小时

- [ ] **任务**: 收集反馈
  - **方法**: 问卷/访谈
  - **预计时间**: 1小时

- [ ] **任务**: 修复问题
  - **根据**: 用户反馈
  - **预计时间**: 4小时

---

## 📊 进度跟踪

### 总体进度
- [ ] 阶段 1: 后端 API 开发 (0/14)
- [ ] 阶段 2: 前端组件开发 (0/19)
- [ ] 阶段 3: 联调测试 (0/11)

**总进度**: 0/44 (0%)

---

## 🎯 里程碑

| 里程碑 | 目标日期 | 状态 | 备注 |
|--------|----------|------|------|
| 后端 API 完成 | Day 3 | ⏳ 待开始 | - |
| 前端组件完成 | Day 6 | ⏳ 待开始 | - |
| 联调测试完成 | Day 8 | ⏳ 待开始 | - |
| 功能上线 | Day 8 | ⏳ 待开始 | - |

---

## ⚠️ 风险与应对

### 风险 1: 夸克 API 限流
- **影响**: 高频调用可能被限流
- **应对**: 添加请求间隔，实现请求队列
- **责任人**: 后端开发

### 风险 2: 大量文件性能问题
- **影响**: 加载/处理慢
- **应对**: 分页加载，虚拟滚动
- **责任人**: 前端开发

### 风险 3: 文件名冲突
- **影响**: 重命名失败
- **应对**: 自动添加序号，提示用户
- **责任人**: 后端开发

### 风险 4: 用户体验问题
- **影响**: 用户不会使用
- **应对**: 添加引导，优化交互
- **责任人**: 前端开发

---

## 📝 每日站会记录

### Day 1 (2026-02-04)
- **完成**: 
  - 需求分析
  - 技术方案设计
  - 文档编写
- **计划**: 
  - 开始后端开发
- **阻塞**: 无

---

## 📚 参考文档

1. [智能重命名功能完善开发文档](./smart_rename_quark_integration.md)
2. [智能重命名 API 接口文档](../api/smart_rename_api.md)
3. [夸克 API 文档](https://pan.quark.cn/docs)
4. [Emby 命名规范](https://support.emby.media/support/solutions/articles/44001159110)

---

## 🎉 完成标准

### 功能完整性
- [x] 所有任务完成
- [ ] 所有测试通过
- [ ] 文档完善

### 质量标准
- [ ] 代码审查通过
- [ ] 无严重 Bug
- [ ] 性能达标

### 用户验收
- [ ] 用户试用满意
- [ ] 反馈问题已修复

---

**清单维护者**: 开发团队  
**最后更新**: 2026-02-04
