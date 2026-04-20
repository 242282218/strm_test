# 监控文档

**最后同步**: 2026-04-20  
**对应代码目录**: `app/api/prometheus.py`、`app/core/prometheus_metrics.py`、`prometheus.yml`、`docs/monitoring/grafana-dashboard.json`

## 当前已落地资产

- [`../../prometheus.yml`](../../prometheus.yml) - 仓库当前 Prometheus 抓取配置示例。
- [`./grafana-dashboard.json`](./grafana-dashboard.json) - 当前 Grafana 仪表盘资产。
- `app/api/prometheus.py` - `/metrics` 与 `/metrics/health` 的 HTTP 暴露入口。
- `app/core/prometheus_metrics.py` - Prometheus registry 与应用指标定义入口。

当前 `docs/monitoring/` 目录只落地了 `README.md` 与 `grafana-dashboard.json`。  
当前仓库尚未落地 `prometheus-rules.yml` 或 `alerting/alertmanager.yml`；在真实文件进入仓库前，不要把它们写成现有资产。

## 指标入口

| 端点 | 说明 |
| --- | --- |
| `/metrics` | Prometheus 指标抓取端点 |
| `/metrics/health` | 指标服务健康检查 |

## 当前接入方式

1. 按 [`../../prometheus.yml`](../../prometheus.yml) 把 `quark_strm` job 指向目标实例。
2. 启动应用后确认 `/metrics` 与 `/metrics/health` 可访问。
3. 在 Grafana 导入 [`./grafana-dashboard.json`](./grafana-dashboard.json)。

## 与其它执行入口的关系

- 部署、运行目录与 Docker profile：[`../operations/README.md`](../operations/README.md)
- API 路径与公开探针：[`../api/README.md`](../api/README.md)
- 当前入口/热点基线：[`../architecture/current-state.md`](../architecture/current-state.md)

## 后续补齐项

- [ ] 若新增告警规则文件，先补真实仓库文件，再更新本索引与 contract test。
- [ ] 若引入 Alertmanager 或 Loki 资产目录，补相对链接并同步运维入口文档。
