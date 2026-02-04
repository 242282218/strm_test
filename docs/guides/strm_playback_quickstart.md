# STRM 播放链路快速跑通（302 / WebDAV 两种模式）

目标：把夸克网盘里的视频批量生成 `.strm`，让 Emby（或 VLC/mpv/ffplay）可播放。

## 0. 前置条件

- 已在 `quark_strm/config.yaml` 配好 `quark.cookie`
- 生成 STRM 时的 `base_url` 必须是 **Emby 能访问到** 的地址（不要用 `localhost`）
  - 同机：`http://127.0.0.1:8000`
  - 局域网：`http://<你的局域网IP>:8000`

## 1. 启动后端

在 `smart_media/quark_strm` 目录：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

自检：

```bash
curl.exe -sS http://127.0.0.1:8000/health
```

## 2. 生成 STRM（两种模式）

两种模式仅影响 `.strm` 文件里写入的播放 URL：

- `redirect`：写入 `.../api/proxy/redirect/<file_id>`（后端 302 跳转到实时直链）
- `webdav`：写入 `.../dav/<path>`（走 WebDAV 入口；默认会把 WebDAV 用户名密码嵌入 URL）

### 2.1 用 API 生成（推荐先跑通）

示例：把 `/video` 下的内容生成到本地 `./strm`（会镜像目录结构）

**302 模式：**

```bash
curl.exe -sS -X POST "http://127.0.0.1:8000/api/strm/scan?remote_path=/video&local_path=./strm&recursive=true&concurrent_limit=5&base_url=http://127.0.0.1:8000&strm_url_mode=redirect"
```

**WebDAV 模式：**

```bash
curl.exe -sS -X POST "http://127.0.0.1:8000/api/strm/scan?remote_path=/video&local_path=./strm&recursive=true&concurrent_limit=5&base_url=http://127.0.0.1:8000&strm_url_mode=webdav"
```

返回示例：

```json
{"strms":["video/a.mp4.strm"],"count":1}
```

### 2.2 验证单个 STRM 是否可用

随便找一个生成的 `.strm`，读出其中 URL 进行测试：

```powershell
$u = Get-Content .\strm\video\a.mp4.strm -Raw
curl.exe -I "$u"
```

预期：

- `redirect` 模式：返回 `302`，并带 `Location: https://...` 的直链
- `webdav` 模式：通常返回 `307`（WebDAV 资源会跳转到直链）；如果看到 `401`，说明鉴权没带上（检查 `webdav.username/password`）

## 3. Emby 播放

1. 在 Emby 添加媒体库，媒体路径指向你生成 `.strm` 的目录（例如 `...\quark_strm\strm`）
2. 刷新媒体库
3. 点开条目播放

常见坑：

- Emby 不在同一台机器：`.strm` 里的 `base_url` 不能是 `localhost`
- Windows 防火墙：确保 Emby 能访问到运行后端的 `8000` 端口

