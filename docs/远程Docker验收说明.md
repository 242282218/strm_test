# 远程 Docker 验收说明

本文档说明如何配置和使用 GitHub Actions 进行远程 Docker 部署验收。

## 概述

通过 `docker-remote-verify.yml` workflow，可以在推送代码到 GitHub 后，自动将代码部署到远程服务器并执行验收测试。

```
GitHub Push → Actions触发 → SSH到服务器 → 部署Docker → 运行验收 → 报告结果
```

## GitHub Secrets 配置

在 GitHub 仓库的 **Settings → Secrets and variables → Actions** 中配置以下 Secrets：

### 必需配置

| Secret | 说明 | 示例 |
|--------|------|------|
| `SERVER_HOST` | 远程服务器IP或域名 | `192.168.1.100` 或 `server.example.com` |
| `SERVER_USER` | SSH用户名 | `root` 或 `ubuntu` |
| `SERVER_SSH_KEY` | SSH私钥（完整内容） | `-----BEGIN OPENSSH PRIVATE KEY-----...` |

### 可选配置

| Secret | 说明 | 默认值 |
|--------|------|--------|
| `SERVER_SSH_PORT` | SSH端口 | `22` |
| `DEPLOY_DIR` | 服务器上的部署目录 | `~/quark_strm` |
| `SERVICE_PORT` | 服务端口 | `18000` |

### SSH密钥配置步骤

1. **生成SSH密钥对**（在本地执行）：
   ```bash
   ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github_actions
   ```

2. **将公钥添加到服务器**：
   ```bash
   ssh-copy-id -i ~/.ssh/github_actions.pub user@server
   ```

3. **将私钥添加到GitHub Secrets**：
   ```bash
   cat ~/.ssh/github_actions
   ```
   复制完整内容（包括 `-----BEGIN OPENSSH PRIVATE KEY-----` 和 `-----END OPENSSH PRIVATE KEY-----`）

## 验收流程

```
┌─────────────────┐
│  1. Checkout    │
│     代码检出    │
└────────┬────────┘
         ▼
┌─────────────────┐
│  2. 验证Secrets │
│  检查必需配置   │
└────────┬────────┘
         ▼
┌─────────────────┐
│  3. 配置SSH     │
│  设置密钥连接   │
└────────┬────────┘
         ▼
┌─────────────────┐
│  4. 同步代码    │
│  rsync到服务器  │
└────────┬────────┘
         ▼
┌─────────────────┐
│  5. 部署Docker  │
│  build & up -d  │
└────────┬────────┘
         ▼
┌─────────────────┐
│  6. 健康检查    │
│  等待服务就绪   │
└────────┬────────┘
         ▼
┌─────────────────┐
│  7. 运行验收    │
│  verify_docker  │
└────────┬────────┘
         ▼
┌─────────────────┐
│  8. 报告结果    │
│  Success/Failed │
└─────────────────┘
```

## 触发方式

### 自动触发

- **Push 到 main 分支**：自动触发验收
- **Push 到 develop 分支**：自动触发验收
- **PR 到 main 分支**：自动触发验收

### 手动触发

在 GitHub 仓库页面：
1. 进入 **Actions** 标签
2. 选择 **Docker Remote Verify**
3. 点击 **Run workflow**
4. 选择分支，点击 **Run workflow**

## 验收判定规则

### 验收等级定义

`scripts/verify_docker.sh` 采用三级验收机制：

| 等级 | 标记 | 说明 | 默认行为 |
|------|------|------|----------|
| **CRITICAL_FAIL** | `[CRITICAL_FAIL]` | 关键失败，必须阻断 | 无论STRICT_MODE如何，都exit 1 |
| **SOFT_FAIL** | `[SOFT_FAIL]` | 软性失败，可配置 | STRICT_MODE=true时exit 1，false时通过 |
| **INFO** | `[INFO]` | 信息性通过 | 不影响验收结果 |
| **WARN** | `[WARN]` | 警告 | 不影响验收结果 |

### 判定矩阵

```
有CRITICAL_FAIL → 无论STRICT_MODE → REJECTED (exit 1)
无CRITICAL_FAIL + 有SOFT_FAIL + STRICT_MODE=true → REJECTED (exit 1)
无CRITICAL_FAIL + 有SOFT_FAIL + STRICT_MODE=false → ACCEPTED WITH WARNINGS (exit 0)
无CRITICAL_FAIL + 无SOFT_FAIL → PASSED (exit 0)
```

### 环境变量控制

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `STRICT_MODE` | `true` | CI中建议保持true，本地调试可设为false |
| `LOG_ERROR_THRESHOLD` | `5` | 日志错误数≥此值触发CRITICAL_FAIL |
| `DISK_WARNING_THRESHOLD` | `80` | 磁盘使用率≥此值触发SOFT_FAIL |
| `DISK_CRITICAL_THRESHOLD` | `90` | 磁盘使用率≥此值触发SOFT_FAIL（更高阈值） |
| `MEM_WARNING_THRESHOLD` | `80` | 内存使用率≥此值触发SOFT_FAIL |
| `MEM_CRITICAL_THRESHOLD` | `90` | 内存使用率≥此值触发SOFT_FAIL（更高阈值） |

### 各检查项的判定规则

| 检查项 | 规则 | 等级 | 说明 |
|--------|------|------|------|
| Docker环境 | Docker/Compose/Daemon任一不可用 | CRITICAL_FAIL | 基础环境必须可用 |
| 容器状态 | 无运行容器 或 有unhealthy容器 | CRITICAL_FAIL | 服务必须正常运行 |
| 端口监听 | 服务端口未监听 | CRITICAL_FAIL | 端口必须开放 |
| 健康端点 | `/health` 不可达 | CRITICAL_FAIL | 健康检查必须响应 |
| 根端点 | `/` 不可达 | CRITICAL_FAIL | 根路径必须可访问 |
| API端点 | 任一API返回500 | CRITICAL_FAIL | 服务器错误不可接受 |
| API端点 | API返回401/403 | INFO | 预期行为（需要认证） |
| 静态文件 | 全部静态资源不可达 | SOFT_FAIL | 前端可能未构建 |
| 日志检查 | 错误数≥LOG_ERROR_THRESHOLD | CRITICAL_FAIL | 过多错误日志 |
| 资源使用 | 磁盘/内存超阈值 | SOFT_FAIL | 资源紧张但不阻断 |

### CI日志解读

**成功示例：**
```
========================================
Verification Summary
========================================
INFO:        12
WARN:        2
SOFT_FAIL:   0
CRITICAL_FAIL: 0
========================================
STRICT_MODE: true
========================================
JUDGMENT: PASSED (All checks passed)
```

**关键失败示例：**
```
[CRITICAL_FAIL] API /api/quark/files/0 returns server error (HTTP 500)
...
========================================
CRITICAL_FAIL: 1
========================================
JUDGMENT: REJECTED (Critical failures detected)
Reason: 1 critical check(s) failed
```

**严格模式拒绝示例：**
```
[SOFT_FAIL] Disk usage: 85% (high, threshold: 80%)
...
========================================
SOFT_FAIL:   1
STRICT_MODE: true
========================================
JUDGMENT: REJECTED (Strict mode, soft failures not allowed)
```

**非严格模式通过示例：**
```
[SOFT_FAIL] All static files are inaccessible
...
========================================
SOFT_FAIL:   1
STRICT_MODE: false
========================================
JUDGMENT: ACCEPTED WITH WARNINGS (Non-strict mode)
```

## 验收检查项

## 常见失败原因

### 1. SSH连接失败

**症状**：`SSH connection failed`

**原因**：
- 服务器IP/端口错误
- SSH密钥未正确配置
- 服务器防火墙阻止

**解决**：
```bash
# 本地测试SSH连接
ssh -p PORT user@SERVER_HOST

# 检查服务器SSH服务
systemctl status sshd
```

### 2. Docker构建失败

**症状**：`docker compose build` 报错

**原因**：
- 服务器磁盘空间不足
- Docker daemon未运行
- 网络问题导致镜像拉取失败

**解决**：
```bash
# 检查磁盘空间
df -h

# 检查Docker状态
systemctl status docker

# 手动构建测试
docker compose build --no-cache
```

### 3. 健康检查超时

**症状**：`Health check failed after 30 attempts`

**原因**：
- 服务启动时间过长
- 端口冲突
- 配置错误导致服务无法启动

**解决**：
```bash
# 查看容器日志
docker compose logs --tail=100

# 检查端口占用
ss -tlnp | grep 18000

# 手动测试健康端点
curl http://127.0.0.1:18000/health
```

### 4. 验收脚本失败

**症状**：`verify_docker.sh` 返回非0

**原因**：
- API端点返回500错误
- 资源使用超过阈值
- 容器日志中有错误

**解决**：
```bash
# 在服务器上手动运行验收脚本
cd ~/quark_strm
./scripts/verify_docker.sh

# 查看详细日志
docker compose logs -f
```

## 故障排查

### 查看工作流日志

1. 进入 GitHub 仓库 **Actions** 标签
2. 点击失败的 workflow 运行
3. 展开失败的步骤查看详细日志

### 手动在服务器上调试

```bash
# 登录到服务器
ssh user@SERVER_HOST

# 进入部署目录
cd ~/quark_strm

# 查看容器状态
docker compose ps

# 查看日志
docker compose logs --tail=200

# 手动运行验收
./scripts/verify_docker.sh
```

### 清理和重置

```bash
# 停止并删除容器
docker compose down -v

# 删除镜像（强制重新构建）
docker rmi quark-strm:latest

# 清理构建缓存
docker builder prune -f
```

## 安全注意事项

1. **SSH密钥**：使用专用密钥，不要复用个人密钥
2. **服务器访问**：限制服务器仅允许GitHub Actions IP访问（如可能）
3. **Secrets保护**：不要在日志中打印Secrets
4. **部署目录**：使用非root用户运行容器（推荐）

## 扩展配置

### 多服务器部署

修改 workflow 添加矩阵策略：

```yaml
strategy:
  matrix:
    server:
      - { host: 'server1.example.com', port: '18000' }
      - { host: 'server2.example.com', port: '18001' }
```

### 添加通知

在 workflow 末尾添加通知步骤：

```yaml
- name: Notify on success
  if: success()
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {"text": "Deployment successful!"}
```

## 参考

- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [SSH 密钥管理](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
