# Scrape + Emby 发布运行手册（5 点范围）

## 1. 目标范围

本手册对应以下 5 个上线范围：

1. 刮削与整理主流程
2. 刮削目录管理
3. 刮削记录治理
4. 二级分类（动漫文件夹/电影/电视剧）
5. Emby 对接（配置/刷新/webhook/事件日志/删除计划）

## 2. 发布前检查

1. 后端测试通过：
   - `pytest -q quark_strm/tests/test_scope5_e2e.py`
   - `pytest -q quark_strm/tests/test_emby_refresh_api.py quark_strm/tests/test_emby_events_and_delete_api.py`
2. 前端类型检查通过：
   - `npm --prefix quark_strm/web run type-check`
3. 配置检查：
   - `emby.enabled`/`emby.url`/`emby.api_key` 可用
   - `emby.refresh.episode_aggregate_window_seconds` 为 `1~300`
   - `emby.delete_execute_enabled` 默认 `false`

## 3. 配置基线（生产推荐）

```yaml
emby:
  enabled: true
  url: "http://emby:8096"
  api_key: "******"
  timeout: 30
  notify_on_complete: true
  delete_execute_enabled: false
  refresh:
    on_strm_generate: true
    on_rename: true
    cron: "0 */6 * * *"
    library_ids: []
    episode_aggregate_window_seconds: 10
```

## 4. 上线步骤

1. 升级服务并完成数据库表创建（应用启动会自动创建）。
2. 访问“系统配置”页面，完成 Emby 配置并执行连接测试。
3. 访问“Emby 监控”页面，确认：
   - 状态为“已连接”
   - 可见刷新历史
   - webhook 事件可查询
4. 通过“刮削目录”启动一个样本任务，确认“刮削记录”可回看。

## 5. 删除联动安全策略

1. 默认只允许 `POST /api/emby/delete-plan`（dry-run）。
2. 只有在灰度窗口内才开启：
   - `emby.delete_execute_enabled=true`
3. 执行动作前必须确认：
   - 计划项 `can_execute=true`
   - 计划来源、备注和执行人已记录

## 6. 监控与告警

默认监控阈值：

1. `scrape.job.failure_rate > 0.3` 持续 120 秒触发
2. `emby.webhook.event_latency_seconds > 60` 持续 120 秒触发
3. `emby.delete.execute.warning > 0` 持续 1 秒触发（执行告警）

## 7. 回滚预案

1. 立即关闭高风险开关：
   - `emby.delete_execute_enabled=false`
2. 停止新任务入口：
   - 暂停刮削目录（`enabled=false` 或停用 cron）
3. 回退代码版本并重启服务。
4. 对已执行计划进行审计：
   - 检查 `emby_delete_plans` 中 `executed=true` 记录
   - 导出 `plan_items` 与 `executed_by/executed_at`

## 8. 验收报告模板

建议每次发布至少附以下证据：

1. 功能截图：
   - 刮削目录页
   - 刮削记录页
   - 分类策略页
   - Emby 监控页
2. 关键接口响应：
   - `/api/scrape/pathes`
   - `/api/scrape/records`
   - `/api/scrape/category-strategy/preview`
   - `/api/emby/events`
   - `/api/emby/delete-plan`
3. 测试结果：
   - pytest 汇总
   - 前端 type-check 结果
