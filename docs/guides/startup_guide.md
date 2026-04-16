# Quark STRM 开发环境启动指南

本文档介绍如何在本地启动 Quark STRM 项目的前后端开发环境。

## 环境要求

- Python 3.11+
- Node.js 18+
- pnpm 或 npm

## 快速启动

### 1. 启动后端服务

```bash
cd quark_strm

# 激活虚拟环境（如果已创建）
.venv\Scripts\activate

# 启动后端服务（端口 8000）
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端服务启动后，可以访问：
- API 文档：http://localhost:8000/docs
- 存活探针：http://localhost:8000/health/live
- 就绪探针：http://localhost:8000/ready

### 2. 启动前端服务

```bash
cd quark_strm\web

# 安装依赖（首次运行）
npm install

# 启动开发服务器（推荐端口 18099，避免与本机 3000 冲突）
npm run dev -- --port 18099
```

前端服务启动后，访问：http://localhost:18099

## 端口配置

| 服务 | 默认端口 | 说明 |
|------|---------|------|
| 前端 | 3000/18099 | Vite 开发服务器（推荐 18099） |
| 后端 | 8000 | FastAPI 后端服务 |
| Emby 专用代理 | 18097 | 透明反向代理入口（页面+登录+播放链路） |

> **注意**：如果端口 3000 被其他服务占用（如本机博客项目），请使用 18099。前端代理配置在 `web/vite.config.ts` 中。

## 前端代理配置

前端通过 Vite 代理转发 API 请求到后端。配置文件：`web/vite.config.ts`

```typescript
server: {
  port: 3000, // 可通过命令行参数覆盖，例如 --port 18099
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true
    }
  }
}
```

如需修改后端端口，请同步更新此配置。

## 默认登录账号

- 用户名：`admin`
- 密码：`admin`

## 常见问题

### 端口被占用

如果启动时提示端口被占用，可以：

1. 检查占用进程：
   ```bash
   netstat -ano | findstr :8000
   ```

2. 更换端口：
   - 后端：修改启动命令中的 `--port` 参数
   - 前端：修改 `vite.config.ts` 中的代理目标

### 前端请求 404

确保：
1. 后端服务已正常启动
2. 前端代理配置中的端口与后端实际端口一致
3. 重启前端开发服务器使配置生效

### Emby 18097 登录报错

如果 `http://127.0.0.1:18097` 登录提示“处理请求时出错”：
1. 先确认运行版本包含 `v2026.03.14-emby-proxy-hotfix1`。
2. 使用无痕窗口重试，避免旧缓存与 Service Worker 干扰。
3. 查看日志：
   - `quark_strm/logs/runtime/proxy_18097.out.log`
   - `quark_strm/logs/runtime/proxy_18097.err.log`
4. 检查登录请求 `POST /emby/Users/authenticatebyname` 是否返回上游状态（200/401）。

## Emby 专用代理验证

启动后可验证：

```bash
# Emby 专用代理入口
curl -I http://127.0.0.1:18097/

# Emby 公共接口
curl -I http://127.0.0.1:18097/emby/system/info/public
```

预期行为：
- 18097 可直接打开 Emby 页面
- 播放时优先 302，失败自动回退转发代理
- 页面和登录链路保持透明代理，不注入额外安全头

### 依赖问题

如果遇到依赖问题，尝试：

```bash
# 后端
cd quark_strm
pip install -r requirements.txt

# 前端
cd quark_strm\web
rm -rf node_modules
npm install
```

## 开发调试

### 查看后端日志

后端日志输出在控制台，包含请求路径、响应状态、耗时等信息。

### 查看前端控制台

打开浏览器开发者工具（F12），查看 Console 和 Network 面板。

### API 调试

访问 http://localhost:8000/docs 使用 Swagger UI 进行 API 测试。

## 生产部署

生产环境部署请参考 `docs/operations/` 目录下的部署文档。
