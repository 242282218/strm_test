# Emby redirect 播放卡住修复设计

## 背景

当前新生成的 redirect STRM 样本在 Emby 中会出现播放卡住。排查表明：

- `item 57` 的 `PlaybackInfo` 通过 Smart Media 调用 Emby 原生 `Items/57/PlaybackInfo` 时超时，最终返回 500。
- 旧样本 `item 6` 可以正常返回 `PlaybackInfo`。
- 两者主要差异在于 STRM 内容与 Emby 条目元数据：`item 57` 使用裸 fid 语义，`item 6` 带完整路径/文件名语义。
- redirect 路由在不可直接外跳时会按设计退化到本地 stream fallback，因此观测到 200/206 并不等于纯外部 302 成功。

## 目标

修复新生成 redirect STRM 在 Emby 中卡住的问题，并满足验收标准：

- Emby 起播后连续播放，不出现卡顿/缓冲。

## 参考

- go-emby2openlist：PlaybackInfo 改写、302 redirect、STRM 外链播放
- qmediasync：STRM 生成与 Emby 外链播放
- SmartStrm：STRM 生成与 302 播放

## 推荐方案

### 方案

优先修正 redirect STRM 生成内容，使其优先写入完整远端路径，而不是裸 fid 语义的 `path` 参数。

### 具体改动

1. 在单文件生成路径中，优先通过 Quark 服务获取完整远端路径。
2. 当调用 `generate_single_file_strm()` 时，传入完整远端路径（如 `/目录/文件名.mkv`），而不是只传 `fid` 或文件名。
3. 保持 redirect / stream / PlaybackInfo Hook 现有总体架构不变。
4. 不先改代理 fallback 行为，避免扩大变更面。

## 原因

- 该方案是最小改动。
- 与已知可工作的旧样本形态对齐。
- 更符合同类开源项目对稳定 STRM 条目语义的依赖方式。
- 若该方案无效，再考虑在 Hook 层增加更强的兼容兜底。

## 测试策略

### 测试优先级

先写失败测试，再修复实现。

### 测试点

1. 单文件扫描时，如果能解析完整远端路径，则应把完整路径传给 `generate_single_file_strm()`。
2. redirect URL 生成时，若给定完整远端路径，应保留完整 `path` 参数。
3. 真实验证：
   - 重新生成 redirect 样本
   - Emby 入库
   - `PlaybackInfo` 不再超时
   - Emby 实际起播
   - 连续播放无缓冲

## 风险与回退

### 风险

- Emby 卡住可能不仅由路径语义引起，还可能和条目命名、媒体识别、服务器探测策略有关。

### 回退策略

- 若最小修复后仍然卡住，则进入第二阶段：在 PlaybackInfo Hook / 代理层增加对特殊 STRM 条目的兼容兜底。

## 实施范围

- 代码：仅限 STRM 生成和对应测试。
- 不主动修改整体播放代理架构。
- 验证会使用现有 Emby 与 `test_strm`。
