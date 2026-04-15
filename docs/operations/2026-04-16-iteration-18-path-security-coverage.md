# 2026-04-16 Iteration 18: Path Security Coverage

## 当前状态判断
- `app/core/path_security.py` 之前覆盖率仅 `7.97%`，文件操作安全边界缺乏回归保护。
- 本轮补测后，模块覆盖率提升到 `92.75%`，核心路径校验与安全文件操作均有测试保护。
- 全量覆盖率由 `45.25%` 提升到 `45.75%`（`671 passed, 2 skipped`）。

## 对标项目可借鉴点
- 生产级项目会对文件系统安全工具层做高覆盖单测，因为路径越权是高风险根因问题。
- 重点不是“功能可用”，而是“异常与边界可预测”：越权、符号链接、跨设备硬链接降级都必须可验证。

## 差距清单（按 P0/P1/P2/P3）
- P1: `security_audit_service` 告警发送分支仍有覆盖盲区，安全告警链路可观测性不足。
- P2: 仍有若干 0% 或低覆盖基础模块，后续门槛上调需要继续补测支撑。

## 本轮要做的优化项
- 新增 `path_security` 工具层分支测试，覆盖：
  - 允许目录加载（配置成功/异常回退）；
  - 路径校验（空路径、越权、符号链接、realpath 异常、存在性检查）；
  - `safe_open/safe_makedirs/safe_rename/safe_symlink/safe_hardlink` 的关键行为与异常分支。

## 具体修改方案
- 文件：`quark_strm/tests/test_path_security.py`
  - 新增 13 个测试，使用 `tmp_path` + `monkeypatch` 覆盖文件系统安全关键路径；
  - 覆盖跨设备硬链接降级复制与非跨设备错误抛出分支。

## 验证方案
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_path_security.py`
- `python -m pytest -q -o addopts='-v --tb=short --cov=app.core.path_security --cov-report=term-missing' tests/test_path_security.py`
- `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=44'`
- 结果：全部通过；`path_security.py` 覆盖 `92.75%`，全量覆盖 `45.75%`。

## 本轮风险
- 文件安全层风险已显著下降，但安全审计通知链路仍存在残余分支未覆盖。
- 覆盖率虽已提升，但后续大体量低覆盖改动仍可能压缩门槛缓冲。

## 下一轮建议
1. 将 `pytest` 覆盖率门槛从 `44` 提升到 `45` 并同步守护测试。
2. 补齐 `security_audit_service` 的告警发送路径分支，进一步增强安全事件链路回归信号。
3. 优先持续补“安全与边界工具层”而非低价值表层分支。
