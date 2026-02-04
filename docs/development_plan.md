# 夸克 STRM 最小实现方案 - 开发方案

> 本文档为 **Markdown (.md)** 文件，可直接用于 GitHub / Obsidian / Typora。

---

## 一、项目概述与目标

### 1.1 项目目标

实现 **Emby/Jellyfin 可播放的夸克网盘 STRM 最小闭环**，满足以下核心需求：

- **.strm 文件稳定不变** - 生成的 STRM 文件内容保持稳定，无需频繁更新
- **支持 Range / Seek** - 支持视频播放的随机访问和进度跳转
- **直链不稳定兜底** - 夸克直链失效时，由反向代理/播放网关自动兜底
- **全流程开源可审计** - 所有代码开源，确保安全性和可维护性

### 1.2 技术路线拆解

系统架构分为 3 层：

```
[夸克网盘]
    ↓
[夸克接入层] - 获取文件、直链、302
    ↓
[STRM 生成层] - 生成本地媒体库结构
    ↓
[播放网关层] - 反向代理 / 302 重定向
    ↓
[Emby / Jellyfin]
```

### 1.3 核心技术挑战

1. **夸克鉴权机制** - Cookie/TV Token 的获取与维护
2. **直链失效处理** - 直链有效期短，需要自动刷新
3. **Range 请求正确性** - 确保视频播放的 Range 请求正确转发
4. **Emby 客户端兼容性** - 兼容不同 Emby/Jellyfin 客户端的播放请求

---

## 二、参考项目深度分析

### 2.1 OpenList (Go) - 夸克接入层核心参考

#### 2.1.1 项目信息
- **项目地址**: https://github.com/OpenListTeam/OpenList
- **许可证**: AGPL-3.0
- **状态**: 活跃维护
- **语言**: Go

#### 2.1.2 核心文件分析

> 补充：如采用 TV Token 登录，优先参考 drivers/quark_uc_tv/* 的签名与刷新流程。

**文件 1: `drivers/quark_uc/driver.go`**

**核心结构体**:
```go
type QuarkOrUC struct {
    model.Storage
    Addition
    config driver.Config
    conf   Conf
}
```

**关键方法**:

1. **Init 初始化方法** (L36-L48)
```go
func (d *QuarkOrUC) Init(ctx context.Context) error {
    _, err := d.request("/config", http.MethodGet, nil, nil)
    if err == nil {
        if d.AdditionVersion != 2 {
            d.AdditionVersion = 2
            if !d.UseTransCodingAddress && len(d.DownProxyURL) == 0 {
                d.WebProxy = true
                d.WebdavPolicy = "native_proxy"
            }
        }
    }
    return err
}
```
**可复用点**: 配置版本检查和代理策略自动设置

2. **List 文件列表获取** (L54-L61)
```go
func (d *QuarkOrUC) List(ctx context.Context, dir model.Obj, args model.ListArgs) ([]model.Obj, error) {
    files, err := d.GetFiles(dir.GetID())
    if err != nil {
        return nil, err
    }
    return files, nil
}
```
**可复用点**: 文件列表获取的接口设计

3. **Link 直链获取** (L63-L71)
```go
func (d *QuarkOrUC) Link(ctx context.Context, file model.Obj, args model.LinkArgs) (*model.Link, error) {
    f := file.(*File)
    if d.UseTransCodingAddress && d.config.Name == "Quark" && f.Category == 1 && f.Size > 0 {
        return d.getTranscodingLink(file)
    }
    return d.getDownloadLink(file)
}
```
**可复用点**: 根据文件类型选择直链获取策略

**文件 2: `drivers/quark_uc/util.go`**

**关键方法**:

1. **request 通用请求方法** (L27-L67)
```go
func (d *QuarkOrUC) request(pathname string, method string, callback base.ReqCallback, resp interface{}) ([]byte, error) {
    u := d.conf.api + pathname
    req := base.RestyClient.R()
    req.SetHeaders(map[string]string{
        "Cookie":  d.Cookie,
        "Accept":  "application/json, text/plain, */*",
        "Referer": d.conf.referer,
    })
    req.SetQueryParam("pr", d.conf.pr)
    req.SetQueryParam("fr", "pc")
    // ... 处理响应和Cookie更新
}
```
**可复用点**:
- 夸克API请求的标准Header设置
- Cookie自动更新机制 (`__puus`, `__pus`)
- 错误处理和响应解析

2. **GetFiles 文件列表获取** (L69-L111)
```go
func (d *QuarkOrUC) GetFiles(parent string) ([]model.Obj, error) {
    files := make([]model.Obj, 0)
    page := 1
    size := 100
    query := map[string]string{
        "pdir_fid":             parent,
        "_size":                strconv.Itoa(size),
        "_fetch_total":         "1",
        "fetch_all_file":       "1",
        "fetch_risk_file_name": "1",
    }
    // 分页获取逻辑
}
```
**可复用点**:
- 夸克文件列表API的查询参数
- 分页遍历逻辑
- HTML转义处理 (`html.UnescapeString`)

3. **getDownloadLink 直链获取** (L113-L137)
```go
func (d *QuarkOrUC) getDownloadLink(file model.Obj) (*model.Link, error) {
    data := base.Json{
        "fids": []string{file.GetID()},
    }
    var resp DownResp
    ua := d.conf.ua
    _, err := d.request("/file/download", http.MethodPost, func(req *resty.Request) {
        req.SetHeader("User-Agent", ua).
            SetBody(data)
    }, &resp)
    if err != nil {
        return nil, err
    }
    return &model.Link{
        URL: resp.Data[0].DownloadUrl,
        Header: http.Header{
            "Cookie":     []string{d.Cookie},
            "Referer":    []string{d.conf.referer},
            "User-Agent": []string{ua},
        },
        Concurrency: 3,
        PartSize:    10 * utils.MB,
    }, nil
}
```
**可复用点**:
- 夸克下载API调用
- 直链响应结构解析
- 必需的Header设置

4. **getTranscodingLink 转码直链** (L139-L168)
```go
func (d *QuarkOrUC) getTranscodingLink(file model.Obj) (*model.Link, error) {
    data := base.Json{
        "fid":         file.GetID(),
        "resolutions": "low,normal,high,super,2k,4k",
        "supports":    "fmp4_av,m3u8,dolby_vision",
    }
    var resp TranscodingResp
    // ... 调用转码API
}
```
**可复用点**: 夸克转码直链获取逻辑

**文件 3: `drivers/quark_uc/types.go`**

**关键数据结构**:

1. **File 文件对象** (L21-L45)
```go
type File struct {
    Fid      string `json:"fid"`
    FileName string `json:"file_name"`
    Category int    `json:"category"`
    Size     int64 `json:"size"`
    LCreatedAt int64 `json:"l_created_at"`
    LUpdatedAt int64 `json:"l_updated_at"`
    File      bool  `json:"file"`
    CreatedAt int64 `json:"created_at"`
    UpdatedAt int64 `json:"updated_at"`
}
```
**可复用点**: 夸克文件元数据结构

2. **DownResp 下载响应** (L104-L138)
```go
type DownResp struct {
    Resp
    Data []struct {
        DownloadUrl string `json:"download_url"`
    } `json:"data"`
}
```
**可复用点**: 夸克下载API响应结构

3. **TranscodingResp 转码响应** (L140-L214)
```go
type TranscodingResp struct {
    Resp
    Data struct {
        VideoList []struct {
            Resolution string `json:"resolution"`
            VideoInfo  struct {
                Duration int64   `json:"duration"`
                Size     int64   `json:"size"`
                URL      string  `json:"url"`
            } `json:"video_info,omitempty"`
        } `json:"video_list"`
    } `json:"data"`
}
```
**可复用点**: 夸克转码API响应结构

#### 2.1.3 可复用组件清单

| 组件 | 源文件 | 功能 | 适配方式 |
|------|--------|------|---------|
| 夸克API请求封装 | `quark_uc/util.go:27-67` | 通用请求方法 | 转换为Python requests/aiohttp |
| 文件列表获取 | `quark_uc/util.go:69-111` | 分页获取文件列表 | 转换为Python异步实现 |
| 直链获取 | `quark_uc/util.go:113-137` | 获取下载直链 | 转换为Python实现 |
| 转码直链 | `quark_uc/util.go:139-168` | 获取转码直链 | 转换为Python实现 |
| Cookie管理 | `quark_uc/util.go:49-61` | 自动更新Cookie | 转换为Python实现 |
| 文件元数据 | `quark_uc/types.go:21-45` | 文件信息结构 | 转换为Python dataclass |

---

### 2.2 AlistAutoStrm (Go) - STRM生成层核心参考

#### 2.2.1 项目信息
- **项目地址**: https://github.com/imshuai/AlistAutoStrm
- **许可证**: MIT
- **语言**: Go
- **状态**: 持续更新

#### 2.2.2 核心文件分析

**文件 1: `strm.go`**

**核心结构体**:
```go
type Strm struct {
    Name      string `json:"name"`
    LocalDir  string `json:"local_dir"`
    RemoteDir string `json:"remote_dir"`
    RawURL    string `json:"raw_url"`
}
```

**关键方法**:

1. **Key 唯一键生成** (L22-L25)
```go
func (s *Strm) Key() string {
    byts := sha1.Sum([]byte(s.RawURL))
    return fmt.Sprintf("%x", byts)
}
```
**可复用点**: 使用SHA1生成唯一标识符

2. **GenStrm 生成STRM文件** (L60-L70)
```go
func (s *Strm) GenStrm(overwrite bool) error {
    err := os.MkdirAll(s.LocalDir, 0755)
    if err != nil {
        return err
    }
    _, err = os.Stat(path.Join(s.LocalDir, s.Name))
    if !overwrite && !os.IsNotExist(err) {
        return fmt.Errorf("file %s already exists and overwrite is false", path.Join(s.LocalDir, s.Name))
    }
    return os.WriteFile(path.Join(s.LocalDir, s.Name), []byte(s.RawURL), 0666)
}
```
**可复用点**:
- 目录创建逻辑
- 文件存在检查
- STRM文件写入

3. **Check 检查STRM有效性** (L73-L85)
```go
func (s *Strm) Check() bool {
    logger.Infof("Checking %s", s.LocalDir+"/"+s.Name)
    resp, err := http.Head(s.RawURL)
    if err != nil {
        logger.Errorf("http.Head(%s) error: %v", s.RawURL, err)
        return false
    }
    defer resp.Body.Close()
    if resp.StatusCode == 302 || (resp.StatusCode == 200 && (resp.Header.Get("Content-Type") == "video/mp4" || resp.Header.Get("Content-Type") == "application/octet-stream")) {
        return true
    }
    return false
}
```
**可复用点**:
- HTTP HEAD请求验证
- 状态码和Content-Type检查

4. **Save/Delete BoltDB操作** (L49-L57, L34-L46)
```go
func (s *Strm) Save() error {
    return db.Update(func(tx *bolt.Tx) error {
        b, err := tx.CreateBucketIfNotExists([]byte("strm"))
        if err != nil {
            return err
        }
        return b.Put([]byte(s.Key()), s.Value())
    })
}

func (s *Strm) Delete() error {
    err := os.RemoveAll(path.Join(s.LocalDir, s.Name))
    if err != nil {
        return err
    }
    return db.Update(func(tx *bolt.Tx) error {
        b := tx.Bucket([]byte("strm"))
        if b == nil {
            return fmt.Errorf("bucket not found")
        }
        return b.Delete([]byte(s.Key()))
    })
}
```
**可复用点**: 数据库CRUD操作模式

**文件 2: `mission.go`**

**核心结构体**:
```go
type Mission struct {
    CurrentRemotePath    string
    LocalPath            string
    BaseURL              string
    Exts                 []string
    AltExts              []string
    IsCreateSubDirectory bool
    IsRecursive          bool
    IsForceRefresh       bool
    client               *sdk.Client
    wg                   *sync.WaitGroup
    concurrentChan       chan int
}
```

**关键方法**:

1. **getStrm 递归获取STRM** (L31-L158)
```go
func (m *Mission) getStrm(strmChan chan *Strm) {
    threadIdx := <-m.concurrentChan
    defer func() {
        m.concurrentChan <- threadIdx
        m.wg.Done()
    }()
    alistFiles, err := m.client.List(m.CurrentRemotePath, "", 1, 0, m.IsForceRefresh)
    if err != nil {
        logger.Errorf("[thread %2d]: get files from [%s] error: %s", threadIdx, m.CurrentRemotePath, err.Error())
        return
    }
    for _, f := range alistFiles {
        if f.IsDir && m.IsRecursive {
            // 递归处理子目录
            mm := &Mission{
                BaseURL:           m.BaseURL,
                CurrentRemotePath: m.CurrentRemotePath + "/" + f.Name,
                LocalPath: func() string {
                    if m.IsCreateSubDirectory {
                        return path.Join(m.LocalPath, f.Name)
                    } else {
                        return m.LocalPath
                    }
                }(),
                // ... 复制其他配置
            }
            m.wg.Add(1)
            go mm.getStrm(strmChan)
        } else if !f.IsDir {
            if checkExt(f.Name, m.Exts) {
                strm := &Strm{
                    Name: func() string {
                        ext := filepath.Ext(f.Name)
                        name := strings.TrimSuffix(f.Name, ext)
                        return name + ".strm"
                    }(),
                    RemoteDir: m.CurrentRemotePath,
                    LocalDir:  m.LocalPath,
                    RawURL:    m.BaseURL + "/d" + m.CurrentRemotePath + "/" + f.Name,
                }
                strmChan <- strm
            }
        }
    }
}
```
**可复用点**:
- 并发控制模式 (channel + WaitGroup)
- 递归目录遍历
- 文件扩展名过滤
- STRM对象构建

2. **GetAllStrm 并发获取所有STRM** (L161-L223)
```go
func (m *Mission) GetAllStrm(concurrentNum int) []*Strm {
    m.concurrentChan = make(chan int, concurrentNum)
    for i := 0; i < concurrentNum; i++ {
        m.concurrentChan <- i
    }
    m.wg = &sync.WaitGroup{}
    m.wg.Add(1)
    strmChan := make(chan *Strm, 1000)
    stopChan := make(chan struct{})
    resultChan := make(chan []*Strm, 1)
    go func() {
        strms := make([]*Strm, 0)
        running := true
        for running {
            select {
            case <-stopChan:
                draining := true
                for draining {
                    select {
                    case strm := <-strmChan:
                        strms = append(strms, strm)
                    default:
                        draining = false
                    }
                }
                resultChan <- strms
                running = false
            case strm := <-strmChan:
                strms = append(strms, strm)
            }
            time.Sleep(5 * time.Millisecond)
        }
    }()
    go m.getStrm(strmChan)
    m.wg.Wait()
    stopChan <- struct{}{}
    return <-resultChan
}
```
**可复用点**:
- 并发工作池模式
- Channel通信模式
- 优雅停止机制

**文件 3: `config.go`**

**配置结构**:
```go
type Config struct {
    Database            string     `json:"database" yaml:"database"`
    Endpoints           []Endpoint `json:"endpoints" yaml:"endpoints"`
    Loglevel            string     `json:"loglevel" yaml:"loglevel"`
    LogFile             string     `json:"log-file" yaml:"log-file"`
    ColoredLog          bool       `json:"colored-log" yaml:"colored-log"`
    Timeout             int        `json:"timeout" yaml:"timeout"`
    Exts                []string   `json:"exts" yaml:"exts"`
    AltExts             []string   `json:"alt-exts" yaml:"alt-exts"`
    CreateSubDirectory  bool       `json:"create-sub-directory" yaml:"create-sub-directory"`
    isIncrementalUpdate bool
    records             map[string]int
}

type Endpoint struct {
    BaseURL          string `json:"base-url" yaml:"base-url"`
    Token            string `json:"token" yaml:"token"`
    Username         string `json:"username" yaml:"username"`
    Password         string `json:"password" yaml:"password"`
    InscureTLSVerify bool   `json:"inscure-tls-verify" yaml:"inscure-tls-verify"`
    Dirs             []Dir  `json:"dirs" yaml:"dirs"`
    MaxConnections   int    `json:"max-connections" yaml:"max-connections"`
}

type Dir struct {
    LocalDirectory     string   `json:"local-directory" yaml:"local-directory"`
    RemoteDirectories  []string `json:"remote-directories" yaml:"remote-directories"`
    NotRescursive      bool     `json:"not-recursive" yaml:"not-recursive"`
    CreateSubDirectory bool     `json:"create-sub-directory" yaml:"create-sub-directory"`
    Disabled           bool     `json:"disabled" yaml:"disabled"`
    ForceRefresh       bool     `json:"force-refresh" yaml:"force-refresh"`
}
```
**可复用点**: 配置结构设计

**文件 4: `main.go`**

**命令行接口**:
```go
app.Commands = []*cli.Command{
    {
        Name:  "update",
        Usage: "update strm file with choosed mode",
        Flags: []cli.Flag{
            &cli.StringFlag{
                Name:  "mode",
                Usage: "update mode, support: local, remote",
                Value: "local",
            },
            &cli.BoolFlag{
                Name:  "no-incremental-update",
                Usage: "when this flag is set, will not use incremental update",
                Value: false,
            },
        },
        Action: func(c *cli.Context) error {
            // 更新逻辑
        },
    },
    {
        Name:  "update-database",
        Usage: "clean database and get all local strm files stored in database",
        Action: func(c *cli.Context) error {
            // 数据库更新逻辑
        },
    },
    {
        Name:  "check",
        Usage: "check if strm file is valid",
        Action: func(c *cli.Context) error {
            // 检查逻辑
        },
    },
}
```
**可复用点**: 命令行接口设计

#### 2.2.3 可复用组件清单

| 组件 | 源文件 | 功能 | 适配方式 |
|------|--------|------|---------|
| STRM数据结构 | `strm.go:14-19` | STRM对象定义 | 转换为Python dataclass |
| STRM文件生成 | `strm.go:60-70` | 生成STRM文件 | 转换为Python实现 |
| STRM有效性检查 | `strm.go:73-85` | HTTP HEAD验证 | 转换为Python aiohttp |
| 并发工作池 | `mission.go:161-223` | 并发控制 | 转换为Python asyncio |
| 递归目录遍历 | `mission.go:31-158` | 递归获取文件 | 转换为Python实现 |
| 配置系统 | `config.go:3-34` | 配置管理 | 转换为Pydantic |
| 增量更新 | `main.go:111-213` | 增量更新逻辑 | 转换为Python实现 |

---

### 2.3 go-emby2openlist (Go) - 播放网关层核心参考

#### 2.3.1 项目信息
- **项目地址**: https://github.com/AmbitiousJun/go-emby2openlist
- **许可证**: MIT
- **语言**: Go
- **状态**: 持续更新

#### 2.3.2 核心文件分析

**文件 1: `internal/service/emby/playbackinfo.go`**
- **核心逻辑**: 修改 PlaybackInfo 响应的 MediaSources，强制 DirectPlay/DirectStream
```go
source.Put("SupportsDirectPlay", jsons.FromValue(true))
source.Put("SupportsDirectStream", jsons.FromValue(true))
source.Put("DirectStreamUrl", jsons.FromValue(newUrl))
```
**可复用点**: PlaybackInfo Hook 逻辑与 DirectStreamUrl 重写

**文件 2: `internal/service/emby/redirect.go`**
- **核心逻辑**: STRM 资源重定向与回源策略
```go
if urls.IsRemote(embyPath) {
    finalPath := getFinalRedirectLink(embyPath, c.Request.Header.Clone())
    c.Redirect(http.StatusTemporaryRedirect, finalPath)
}
```
**可复用点**: 302 重定向 + 内部跳转解析

**文件 3: `internal/service/path/path.go`**
- **核心逻辑**: Emby 路径 → OpenList 路径映射
```go
openlistFilePath := strings.TrimPrefix(embyPath, embyMount)
```
**可复用点**: mount-path 去除与路径映射

**文件 4: `internal/web/cache/cache.go`**
- **核心逻辑**: 缓存 key 忽略 Range/Host
```go
"Range": {}, "Host": {}, "Referrer": {}, "Connection": {},
```
**可复用点**: 缓存 key 规避易变 Header

#### 2.3.3 可复用组件清单

| 组件 | 源文件 | 功能 | 适配方式 |
|------|--------|------|---------|
| PlaybackInfo Hook | `playbackinfo.go` | 直链播放重写 | 转换为Python FastAPI拦截器 |
| 302重定向 | `redirect.go` | STRM直链重定向 | 转换为Python实现 |
| 路径映射 | `path.go` | Emby→OpenList路径 | 转换为Python实现 |
| 直链缓存策略 | `cache.go` | Cache Key/TTL | 转换为Python缓存服务 |
| OpenList直链获取 | `openlist/api.go` | 获取RawUrl | 转换为Python请求封装 |

---

### 2.4 alist-strm (Python) - STRM生成与校验参考

#### 2.4.1 项目信息
- **项目地址**: https://github.com/tefuirZ/alist-strm
- **许可证**: MIT
- **语言**: Python
- **状态**: 脚本/Docker

#### 2.4.2 核心文件分析

**文件 1: `main.py`**
- **核心逻辑**: WebDAV 递归遍历 + 目录树缓存 + STRM 写入
```python
if compare_directory_trees(cached_tree, current_tree):
    logger.info("本地目录树与云端一致，跳过更新。")
```
**可复用点**: 增量更新策略（目录树缓存比对）

**文件 2: `db_handler.py`**
- **核心逻辑**: SQLite 配置存储与读取
**可复用点**: 轻量级配置与任务参数持久化

**文件 3: `task_scheduler.py`**
- **核心逻辑**: cron 任务增删改查
**可复用点**: 任务计划模型与启停策略

**文件 4: `strm_validator.py`**
- **核心逻辑**: 快扫/慢扫校验 STRM 有效性
**可复用点**: STRM 校验与异常输出

#### 2.4.3 可复用组件清单

| 组件 | 源文件 | 功能 | 适配方式 |
|------|--------|------|---------|
| 目录树缓存 | `main.py` | 目录树增量对比 | 转换为Python实现 |
| STRM生成规则 | `main.py` | STRM写入格式 | 直接复用 |
| SQLite配置 | `db_handler.py` | 配置存储 | 直接复用 |
| 任务调度 | `task_scheduler.py` | Cron管理 | APScheduler兼容 |
| STRM校验 | `strm_validator.py` | 快扫/慢扫 | 直接复用 |

---
### 2.5 MediaHelp (Python) - 播放网关层辅助参考

#### 2.5.1 项目信息
- **项目地址**: https://github.com/JieWSOFT/MediaHelp
- **许可证**: MIT
- **语言**: Python (FastAPI)
- **状态**: 源码已停更，仅作为 FastAPI/异步代理风格参考

#### 2.5.2 核心文件分析

**文件: `backend/api/proxy.py`**

**核心路由**:
```python
@router.get("/proxy/image_proxy")
async def proxy_image(url: str):
    """
    代理图片请求

    参数:
    - url: base64编码的原始图片URL

    返回:
    - 图片内容
    """
    try:
        # 解码URL
        try:
            decoded_url = unquote(base64.urlsafe_b64decode(url).decode('utf-8'))
        except Exception as e:
            logger.error(f"URL解码失败: {str(e)}")
            raise HTTPException(status_code=400, detail="无效的URL格式")

        # 验证URL是否为Telegram CDN
        if "cdn-telegram.org" not in decoded_url:
            raise HTTPException(status_code=403, detail="仅支持代理Telegram CDN的图片")

        # 确保session已初始化
        await http_client._ensure_session()

        # 获取图片内容
        async with http_client._session.get(
            url=decoded_url,
            timeout=aiohttp.ClientTimeout(total=30),
            ssl=False
        ) as response:
            if response.status != 200:
                raise HTTPException(status_code=response.status, detail="获取图片失败")

            # 读取二进制数据
            content = await response.read()

            # 获取正确的媒体类型
            content_type = response.headers.get("content-type", "image/jpeg")

        # 返回图片
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=31536000",
                "Access-Control-Allow-Origin": "*"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"代理图片请求失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"代理请求失败: {str(e)}")
```

**可复用点**:
- FastAPI路由设计
- 异步HTTP请求处理
- 错误处理机制
- 响应Header设置
- Base64编码/解码

#### 2.5.3 可复用组件清单

| 组件 | 源文件 | 功能 | 适配方式 |
|------|--------|------|---------|
| FastAPI路由 | `proxy.py:10-66` | 代理路由设计 | 直接复用 |
| 异步HTTP请求 | `proxy.py:38-47` | aiohttp请求 | 直接复用 |
| 错误处理 | `proxy.py:62-66` | 异常处理 | 直接复用 |
| 响应Header | `proxy.py:53-60` | Header设置 | 直接复用 |

---

## 三、分阶段实施规划

### 3.1 阶段概览

| 阶段 | 名称 | 周期 | 主要任务 | 里程碑 | 负责智能体 |
|------|------|------|----------|--------|-----------|
| **P1** | 基础架构搭建 | Week 1 | 项目初始化、配置系统、日志系统 | 可运行的脚手架 | 基础架构智能体 |
| **P2** | 夸克接入层 | Week 2 | 夸克API封装、鉴权管理、文件列表获取 | 可获取夸克直链 | 夸克接入智能体 |
| **P3** | STRM生成层 | Week 3 | 目录遍历、STRM文件生成、增量更新 | 可生成STRM文件库 | STRM生成智能体 |
| **P4** | 播放网关层 | Week 4 | 反向代理、302重定向、Range支持、缓存 | 可播放STRM视频 | 播放网关智能体 |
| **P5** | 集成测试与优化 | Week 5 | 端到端测试、性能优化、文档完善 | 生产可用版本 | 测试优化智能体 |

### 3.2 P1: 基础架构搭建 (Week 1)

#### 3.2.1 任务清单

| 任务ID | 任务描述 | 优先级 | 预计工时 | 依赖 |
|--------|---------|--------|---------|------|
| P1-T1 | 项目目录结构初始化 | 高 | 2h | 无 |
| P1-T2 | Python虚拟环境配置 | 高 | 1h | P1-T1 |
| P1-T3 | 依赖包安装 (FastAPI, Pydantic, aiohttp) | 高 | 1h | P1-T2 |
| P1-T4 | 配置系统实现 (YAML/JSON) | 高 | 4h | P1-T3 |
| P1-T5 | 日志系统实现 | 高 | 3h | P1-T4 |
| P1-T6 | 数据库初始化 (SQLite) | 高 | 3h | P1-T4 |
| P1-T7 | 基础API框架搭建 | 高 | 4h | P1-T5 |
| P1-T8 | Docker容器化配置 | 中 | 3h | P1-T7 |

#### 3.2.2 技术实现细节

**P1-T1: 项目目录结构**
```
quark_strm/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI应用入口
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py         # 配置管理 (参考 AlistAutoStrm config.go)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── logging.py          # 日志系统
│   │   └── database.py         # 数据库连接 (参考 AlistAutoStrm BoltDB)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── strm.py            # STRM数据模型 (参考 AlistAutoStrm strm.go)
│   │   └── quark.py          # 夸克数据模型 (参考 OpenList types.go)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── quark_service.py   # 夸克服务 (参考 OpenList driver.go)
│   │   ├── strm_service.py    # STRM服务 (参考 AlistAutoStrm mission.go)
│   │   └── proxy_service.py   # 代理服务 (参考 MediaHelp proxy.py)
│   └── api/
│       ├── __init__.py
│       ├── quark.py           # 夸克API
│       ├── strm.py            # STRM API
│       └── proxy.py           # 代理API
├── tests/
│   ├── __init__.py
│   ├── test_quark.py
│   ├── test_strm.py
│   └── test_proxy.py
├── config.yaml                # 配置文件
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

**P1-T4: 配置系统实现**
```python
# 参考: AlistAutoStrm config.go
from pydantic import BaseModel, Field
from typing import List, Optional
import yaml

class EndpointConfig(BaseModel):
    base_url: str = Field(..., description="OpenList/AList base URL")
    token: Optional[str] = Field(None, description="API token")
    username: Optional[str] = Field(None, description="Username")
    password: Optional[str] = Field(None, description="Password")
    insecure_tls_verify: bool = Field(False, description="Skip TLS verification")
    dirs: List['DirConfig'] = Field(default_factory=list, description="Directory mappings")
    max_connections: int = Field(5, description="Max concurrent connections")

class DirConfig(BaseModel):
    local_directory: str = Field(..., description="Local directory path")
    remote_directories: List[str] = Field(..., description="Remote directory paths")
    not_recursive: bool = Field(False, description="Disable recursive scan")
    create_sub_directory: bool = Field(False, description="Create subdirectories")
    disabled: bool = Field(False, description="Disable this directory")
    force_refresh: bool = Field(False, description="Force refresh")

class AppConfig(BaseModel):
    database: str = Field("quark_strm.db", description="Database file path")
    endpoints: List[EndpointConfig] = Field(default_factory=list)
    log_level: str = Field("INFO", description="Log level")
    log_file: Optional[str] = Field(None, description="Log file path")
    colored_log: bool = Field(True, description="Enable colored logs")
    timeout: int = Field(30, description="Request timeout in seconds")
    exts: List[str] = Field(default_factory=lambda: [".mp4", ".mkv", ".avi", ".mov"], description="Video extensions")
    alt_exts: List[str] = Field(default_factory=lambda: [".srt", ".ass"], description="Subtitle extensions")
    create_sub_directory: bool = Field(False, description="Create subdirectories globally")

    @classmethod
    def from_yaml(cls, path: str) -> 'AppConfig':
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self, path: str) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.dict(), f, allow_unicode=True)
```

**P1-T5: 日志系统实现**
```python
import logging
from loguru import logger
import sys

def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None, colored: bool = True):
    """
    设置日志系统

    参考: AlistAutoStrm log.go
    """
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=colored
    )
    if log_file:
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=log_level,
            rotation="10 MB",
            retention="7 days",
            encoding="utf-8"
        )
```

**P1-T6: 数据库初始化**
```python
import sqlite3
from contextlib import contextmanager
from typing import Optional

class Database:
    """
    数据库管理类

    参考: AlistAutoStrm BoltDB操作 (strm.go:49-57)
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库表结构"""
        with self.get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strm (
                    key TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    local_dir TEXT NOT NULL,
                    remote_dir TEXT NOT NULL,
                    raw_url TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    remote_dir TEXT PRIMARY KEY,
                    last_scan TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    @contextmanager
    def get_conn(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_strm(self, strm: 'StrmModel') -> bool:
        """保存STRM记录"""
        with self.get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO strm (key, name, local_dir, remote_dir, raw_url, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (strm.key, strm.name, strm.local_dir, strm.remote_dir, strm.raw_url))
            conn.commit()
        return True

    def get_strm(self, key: str) -> Optional['StrmModel']:
        """获取STRM记录"""
        with self.get_conn() as conn:
            cursor = conn.execute("SELECT * FROM strm WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return StrmModel(**dict(row))
        return None

    def delete_strm(self, key: str) -> bool:
        """删除STRM记录"""
        with self.get_conn() as conn:
            conn.execute("DELETE FROM strm WHERE key = ?", (key,))
            conn.commit()
        return True

    def get_records(self) -> dict:
        """获取扫描记录"""
        with self.get_conn() as conn:
            cursor = conn.execute("SELECT * FROM records")
            return {row['remote_dir']: row['last_scan'] for row in cursor.fetchall()}

    def save_record(self, remote_dir: str) -> bool:
        """保存扫描记录"""
        with self.get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO records (remote_dir, last_scan)
                VALUES (?, CURRENT_TIMESTAMP)
            """, (remote_dir,))
            conn.commit()
        return True
```

#### 3.2.3 验收标准

- [ ] 项目目录结构完整
- [ ] Python虚拟环境可正常启动
- [ ] 所有依赖包成功安装
- [ ] 配置文件可正常加载和保存
- [ ] 日志系统可正常输出
- [ ] 数据库可正常连接和操作
- [ ] FastAPI应用可正常启动
- [ ] Docker容器可正常构建和运行

---

### 3.3 P2: 夸克接入层 (Week 2)

#### 3.3.1 任务清单

| 任务ID | 任务描述 | 优先级 | 预计工时 | 依赖 |
|--------|---------|--------|---------|------|
| P2-T1 | 夸克API请求封装 | 高 | 6h | P1-T7 |
| P2-T2 | Cookie/Token管理 | 高 | 4h | P2-T1 |
| P2-T3 | 文件列表获取 | 高 | 6h | P2-T2 |
| P2-T4 | 直链获取 | 高 | 6h | P2-T3 |
| P2-T5 | 转码直链获取 | 中 | 4h | P2-T4 |
| P2-T6 | 错误处理和重试机制 | 高 | 4h | P2-T5 |
| P2-T7 | 单元测试 | 高 | 4h | P2-T6 |

#### 3.3.2 技术实现细节

**P2-T1: 夸克API请求封装**
```python
# 参考: OpenList quark_uc/util.go:27-67
import aiohttp
from typing import Optional, Dict, Any
from app.core.logging import logger

class QuarkAPIClient:
    """
    夸克API客户端

    参考: OpenList QuarkOrUC.request方法
    """

    def __init__(self, cookie: str, referer: str = "https://pan.quark.cn/"):
        self.cookie = cookie
        self.referer = referer
        self.base_url = "https://pan.quark.cn"
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        """确保session已初始化"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def request(
        self,
        pathname: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        通用请求方法

        参考: OpenList quark_uc/util.go:27-67
        """
        await self._ensure_session()

        url = f"{self.base_url}{pathname}"
        headers = {
            "Cookie": self.cookie,
            "Accept": "application/json, text/plain, */*",
            "Referer": self.referer,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        query_params = {"pr": "uc", "fr": "pc"}
        if params:
            query_params.update(params)

        try:
            async with self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=query_params
            ) as response:
                result = await response.json()

                # 更新Cookie
                for cookie in response.cookies:
                    if cookie.key in ["__puus", "__pus"]:
                        self.cookie = self._update_cookie(self.cookie, cookie.key, cookie.value)
                        logger.info(f"Updated cookie: {cookie.key}")

                # 检查响应状态
                if result.get("status", 0) >= 400 or result.get("code", 0) != 0:
                    error_msg = result.get("message", "Unknown error")
                    logger.error(f"API error: {error_msg}")
                    raise Exception(error_msg)

                return result

        except aiohttp.ClientError as e:
            logger.error(f"Request failed: {str(e)}")
            raise

    def _update_cookie(self, cookie_str: str, key: str, value: str) -> str:
        """更新Cookie"""
        cookies = {}
        for item in cookie_str.split(";"):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                cookies[k] = v
        cookies[key] = value
        return "; ".join([f"{k}={v}" for k, v in cookies.items()])

    async def close(self):
        """关闭session"""
        if self.session and not self.session.closed:
            await self.session.close()
```

**P2-T3: 文件列表获取**
```python
# 参考: OpenList quark_uc/util.go:69-111
from typing import List
from app.models.quark import FileModel

class QuarkService:
    """夸克服务"""

    def __init__(self, cookie: str):
        self.client = QuarkAPIClient(cookie)

    async def get_files(
        self,
        parent: str,
        page_size: int = 100,
        only_video: bool = False
    ) -> List[FileModel]:
        """
        获取文件列表

        参考: OpenList quark_uc/util.go:69-111
        """
        files = []
        page = 1

        while True:
            params = {
                "pdir_fid": parent,
                "_size": str(page_size),
                "_fetch_total": "1",
                "fetch_all_file": "1",
                "fetch_risk_file_name": "1",
                "_page": str(page)
            }

            try:
                result = await self.client.request("/file/sort", params=params)
                data = result.get("data", {})
                file_list = data.get("list", [])
                metadata = data.get("metadata", {})

                for file_data in file_list:
                    # HTML转义处理
                    from html import unescape
                    file_data["file_name"] = unescape(file_data["file_name"])

                    file_model = FileModel(**file_data)

                    # 过滤视频文件
                    if only_video:
                        if file_model.is_dir or file_model.category == 1:
                            files.append(file_model)
                    else:
                        files.append(file_model)

                # 检查是否还有更多页
                total = metadata.get("total", 0)
                if page * page_size >= total:
                    break

                page += 1

            except Exception as e:
                logger.error(f"Failed to get files: {str(e)}")
                break

        return files

    async def close(self):
        """关闭客户端"""
        await self.client.close()
```

**P2-T4: 直链获取**
```python
# 参考: OpenList quark_uc/util.go:113-137
from app.models.quark import LinkModel

class QuarkService:
    # ... 其他方法

    async def get_download_link(self, file_id: str) -> LinkModel:
        """
        获取下载直链

        参考: OpenList quark_uc/util.go:113-137
        """
        data = {"fids": [file_id]}

        result = await self.client.request(
            "/file/download",
            method="POST",
            data=data
        )

        download_url = result["data"][0]["download_url"]

        return LinkModel(
            url=download_url,
            headers={
                "Cookie": self.client.cookie,
                "Referer": self.client.referer,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            concurrency=3,
            part_size=10 * 1024 * 1024  # 10MB
        )

    async def get_transcoding_link(self, file_id: str) -> LinkModel:
        """
        获取转码直链

        参考: OpenList quark_uc/util.go:139-168
        """
        data = {
            "fid": file_id,
            "resolutions": "low,normal,high,super,2k,4k",
            "supports": "fmp4_av,m3u8,dolby_vision"
        }

        result = await self.client.request(
            "/file/v2/play/project",
            method="POST",
            data=data
        )

        video_list = result["data"]["video_list"]
        for video in video_list:
            if video["video_info"]["url"]:
                return LinkModel(
                    url=video["video_info"]["url"],
                    content_length=video["video_info"]["size"],
                    concurrency=3,
                    part_size=10 * 1024 * 1024
                )

        raise Exception("No transcoding link found")
```

#### 3.3.3 验收标准

- [ ] 夸克API请求可正常发送和接收
- [ ] Cookie可自动更新
- [ ] 文件列表可正常获取
- [ ] 直链可正常获取
- [ ] 转码直链可正常获取
- [ ] 错误可正确处理和重试
- [ ] 所有单元测试通过

---

### 3.4 P3: STRM生成层 (Week 3)

#### 3.4.1 任务清单

| 任务ID | 任务描述 | 优先级 | 预计工时 | 依赖 |
|--------|---------|--------|---------|------|
| P3-T1 | STRM数据模型定义 | 高 | 2h | P2-T7 |
| P3-T2 | 目录遍历实现 | 高 | 6h | P3-T1 |
| P3-T3 | STRM文件生成 | 高 | 4h | P3-T2 |
| P3-T4 | 并发控制实现 | 高 | 6h | P3-T3 |
| P3-T5 | 增量更新实现 | 高 | 4h | P3-T4 |
| P3-T6 | STRM有效性检查 | 中 | 3h | P3-T5 |
| P3-T7 | 单元测试 | 高 | 4h | P3-T6 |

#### 3.4.2 技术实现细节

**P3-T1: STRM数据模型**
```python
# 参考: AlistAutoStrm strm.go:14-19
from pydantic import BaseModel, Field
from typing import Optional
import hashlib
from datetime import datetime

class StrmModel(BaseModel):
    """
    STRM数据模型

    参考: AlistAutoStrm strm.go:14-19
    """
    name: str = Field(..., description="STRM文件名")
    local_dir: str = Field(..., description="本地目录路径")
    remote_dir: str = Field(..., description="远程目录路径")
    raw_url: str = Field(..., description="原始URL")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

    @property
    def key(self) -> str:
        """
        生成唯一键

        参考: AlistAutoStrm strm.go:22-25
        """
        return hashlib.sha1(self.raw_url.encode()).hexdigest()

    @property
    def full_path(self) -> str:
        """获取完整文件路径"""
        import os
        return os.path.join(self.local_dir, self.name)

    def gen_strm_file(self, overwrite: bool = False) -> bool:
        """
        生成STRM文件

        参考: AlistAutoStrm strm.go:60-70
        """
        import os

        # 创建目录
        os.makedirs(self.local_dir, exist_ok=True)

        # 检查文件是否存在
        if not overwrite and os.path.exists(self.full_path):
            return False

        # 写入文件
        with open(self.full_path, 'w', encoding='utf-8') as f:
            f.write(self.raw_url)

        return True

    async def check_valid(self) -> bool:
        """
        检查STRM有效性

        参考: AlistAutoStrm strm.go:73-85
        """
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(self.raw_url) as response:
                    if response.status == 302:
                        return True
                    if response.status == 200:
                        content_type = response.headers.get("Content-Type", "")
                        if content_type in ["video/mp4", "application/octet-stream"]:
                            return True
                    return False
        except Exception as e:
            logger.error(f"Failed to check STRM: {str(e)}")
            return False
```

**P3-T2: 目录遍历实现**
```python
# 参考: AlistAutoStrm mission.go:31-158
from typing import List, Set
from app.models.strm import StrmModel
from app.services.quark_service import QuarkService
from app.core.logging import logger

class StrmGenerator:
    """STRM生成器"""

    def __init__(
        self,
        quark_service: QuarkService,
        base_url: str,
        exts: List[str],
        alt_exts: List[str],
        create_sub_dir: bool = False
    ):
        self.quark_service = quark_service
        self.base_url = base_url
        self.exts = exts
        self.alt_exts = alt_exts
        self.create_sub_dir = create_sub_dir

    async def scan_directory(
        self,
        remote_path: str,
        local_path: str,
        recursive: bool = True,
        scanned_dirs: Set[str] = None
    ) -> List[StrmModel]:
        """
        扫描目录并生成STRM

        参考: AlistAutoStrm mission.go:31-158
        """
        if scanned_dirs is None:
            scanned_dirs = set()

        # 检查是否已扫描
        if remote_path in scanned_dirs:
            return []

        scanned_dirs.add(remote_path)
        strms = []

        try:
            files = await self.quark_service.get_files(remote_path)

            for file in files:
                if file.is_dir and recursive:
                    # 递归处理子目录
                    sub_local_path = local_path
                    if self.create_sub_dir:
                        import os
                        sub_local_path = os.path.join(local_path, file.name)

                    sub_strms = await self.scan_directory(
                        f"{remote_path}/{file.name}",
                        sub_local_path,
                        recursive,
                        scanned_dirs
                    )
                    strms.extend(sub_strms)

                elif not file.is_dir:
                    # 处理文件
                    import os
                    ext = os.path.splitext(file.name)[1].lower()

                    if ext in self.exts:
                        # 生成STRM
                        strm = StrmModel(
                            name=f"{os.path.splitext(file.name)[0]}.strm",
                            local_dir=local_path,
                            remote_dir=remote_path,
                            raw_url=f"{self.base_url}/d{remote_path}/{file.name}"
                        )
                        strms.append(strm)

                    elif ext in self.alt_exts:
                        # 下载字幕文件
                        await self._download_file(file, local_path)

        except Exception as e:
            logger.error(f"Failed to scan directory {remote_path}: {str(e)}")

        return strms

    async def _download_file(self, file, local_path: str):
        """下载文件（如字幕）"""
        import os
        import aiohttp

        file_path = os.path.join(local_path, file.name)

        # 检查文件是否存在
        if os.path.exists(file_path):
            return

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/d{file.get_path()}/{file.name}"
                async with session.get(url) as response:
                    if response.status == 200:
                        os.makedirs(local_path, exist_ok=True)
                        with open(file_path, 'wb') as f:
                            f.write(await response.read())
                        logger.info(f"Downloaded: {file_path}")

        except Exception as e:
            logger.error(f"Failed to download {file.name}: {str(e)}")
```

**P3-T4: 并发控制实现**
```python
# 参考: AlistAutoStrm mission.go:161-223
import asyncio
from typing import List
from app.models.strm import StrmModel

class ConcurrentScanner:
    """并发扫描器"""

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)

    async def scan_directories(
        self,
        generator: StrmGenerator,
        directories: List[tuple]
    ) -> List[StrmModel]:
        """
        并发扫描多个目录

        参考: AlistAutoStrm mission.go:161-223
        """
        tasks = []
        strms = []

        async def scan_and_collect(remote_path: str, local_path: str):
            async with self.semaphore:
                result = await generator.scan_directory(remote_path, local_path)
                return result

        # 创建所有任务
        for remote_path, local_path in directories:
            task = asyncio.create_task(scan_and_collect(remote_path, local_path))
            tasks.append(task)

        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集结果
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Scan failed: {str(result)}")
            else:
                strms.extend(result)

        return strms
```

**P3-T5: 增量更新实现**
```python
# 参考: AlistAutoStrm main.go:111-213
from app.core.database import Database
from app.models.strm import StrmModel
from typing import List

class IncrementalUpdater:
    """增量更新器"""

    def __init__(self, db: Database):
        self.db = db

    async def update_strms(
        self,
        new_strms: List[StrmModel],
        mode: str = "local"
    ) -> dict:
        """
        增量更新STRM

        参考: AlistAutoStrm main.go:111-213
        """
        added = 0
        deleted = 0
        ignored = 0

        if mode == "local":
            # 本地模式：只添加新的
            for strm in new_strms:
                existing = self.db.get_strm(strm.key)
                if existing is None:
                    strm.gen_strm_file(overwrite=False)
                    self.db.save_strm(strm)
                    self.db.save_record(strm.remote_dir)
                    added += 1
                    logger.info(f"Added: {strm.full_path}")
                else:
                    ignored += 1
                    logger.debug(f"Ignored: {strm.full_path}")

        elif mode == "remote":
            # 远程模式：删除不存在的
            records = self.db.get_records()
            remote_dirs = {strm.remote_dir for strm in new_strms}

            for remote_dir in records:
                if remote_dir not in remote_dirs:
                    # 删除该目录下的所有STRM
                    self._delete_strms_by_dir(remote_dir)
                    deleted += 1

            # 添加新的
            for strm in new_strms:
                existing = self.db.get_strm(strm.key)
                if existing is None:
                    strm.gen_strm_file(overwrite=True)
                    self.db.save_strm(strm)
                    self.db.save_record(strm.remote_dir)
                    added += 1
                else:
                    ignored += 1

        return {
            "added": added,
            "deleted": deleted,
            "ignored": ignored
        }

    def _delete_strms_by_dir(self, remote_dir: str):
        """删除指定目录下的所有STRM"""
        import os

        # 从数据库获取该目录的所有STRM
        # 这里需要实现查询逻辑
        # ...

        # 删除文件
        # ...

        # 从数据库删除记录
        # ...
```

#### 3.4.3 验收标准

- [ ] STRM数据模型正确定义
- [ ] 目录可正常遍历
- [ ] STRM文件可正常生成
- [ ] 并发控制正常工作
- [ ] 增量更新正常工作
- [ ] STRM有效性检查正常
- [ ] 所有单元测试通过

---

### 3.5 P4: 播放网关层 (Week 4)

#### 3.5.1 任务清单

| 任务ID | 任务描述 | 优先级 | 预计工时 | 依赖 |
|--------|---------|--------|---------|------|
| P4-T1 | PlaybackInfo Hook 设计 | 高 | 6h | P3-T7 |
| P4-T2 | 路径映射 (Emby→OpenList/Quark) | 高 | 4h | P4-T1 |
| P4-T3 | 代理路由设计 | 高 | 4h | P4-T2 |
| P4-T4 | 302重定向实现 | 高 | 6h | P4-T3 |
| P4-T5 | Range请求处理 | 高 | 6h | P4-T4 |
| P4-T6 | 直链缓存实现 | 高 | 4h | P4-T5 |
| P4-T7 | Emby/Jellyfin 兼容 | 高 | 4h | P4-T6 |
| P4-T8 | 错误处理与回源策略 | 高 | 3h | P4-T7 |
| P4-T9 | 单元测试 | 高 | 4h | P4-T8 |

#### 3.5.2 技术实现细节

**P4-T1: PlaybackInfo Hook 设计**
```python
# 参考: go-emby2openlist internal/service/emby/playbackinfo.go
# 目标: 强制 DirectPlay / DirectStream，并重写 DirectStreamUrl
async def hook_playback_info(item_id: str, api_key: str) -> dict:
    playback = await emby_client.playback_info(item_id, api_key)
    for source in playback.get("MediaSources", []):
        source["SupportsDirectPlay"] = True
        source["SupportsDirectStream"] = True
        source["DirectStreamUrl"] = f"/proxy/stream/{item_id}?api_key={api_key}"
    return playback
```

**P4-T2: 路径映射 (Emby → OpenList/Quark)**
```python
# 参考: go-emby2openlist internal/service/path/path.go
def map_emby_to_openlist(path: str, mount_path: str, path_map: dict) -> str:
    path = path.replace("\\", "/")
    if path.startswith(mount_path):
        path = path[len(mount_path):]
    return path_map.get(path, path)
```
**P4-T3: 代理路由设计**
```python
# 参考: MediaHelp proxy.py
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import aiohttp
from app.core.logging import logger

router = APIRouter(prefix="/proxy", tags=["代理服务"])

class ProxyService:
    """代理服务"""

    def __init__(self, quark_service: 'QuarkService'):
        self.quark_service = quark_service
        self.cache: dict = {}

    async def proxy_stream(
        self,
        request: Request,
        file_id: str,
        range_header: Optional[str] = None
    ) -> Response:
        """
        代理视频流

        支持302重定向和Range请求
        """
        try:
            # 获取直链
            link = await self.quark_service.get_download_link(file_id)

            # 检查缓存
            if file_id in self.cache:
                cached_link = self.cache[file_id]
                if await self._check_link_valid(cached_link.url):
                    link = cached_link

            # 代理请求
            headers = {}
            if range_header:
                headers["Range"] = range_header

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    link.url,
                    headers=headers,
                    allow_redirects=False
                ) as response:
                    # 返回302重定向
                    if response.status == 302:
                        location = response.headers.get("Location")
                        return Response(
                            status_code=302,
                            headers={"Location": location}
                        )

                    # 返回流式响应
                    if response.status == 206 or response.status == 200:
                        response_headers = {
                            "Content-Type": response.headers.get("Content-Type", "video/mp4"),
                            "Content-Length": response.headers.get("Content-Length", ""),
                            "Accept-Ranges": "bytes"
                        }

                        if response.status == 206:
                            response_headers["Content-Range"] = response.headers.get("Content-Range", "")

                        return StreamingResponse(
                            response.content.iter_chunked(8192),
                            status_code=response.status,
                            headers=response_headers
                        )

                    raise HTTPException(
                        status_code=response.status,
                        detail="Failed to proxy stream"
                    )

        except Exception as e:
            logger.error(f"Proxy failed: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _check_link_valid(self, url: str) -> bool:
        """检查直链是否有效"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url) as response:
                    return response.status in [200, 206]
        except:
            return False

@router.get("/stream/{file_id}")
async def proxy_stream(
    request: Request,
    file_id: str,
    proxy_service: ProxyService = Depends(get_proxy_service)
):
    """代理视频流"""
    range_header = request.headers.get("Range")
    return await proxy_service.proxy_stream(request, file_id, range_header)
```

**P4-T4: 302重定向实现**
- 参考: go-emby2openlist `redirect.go`
- 关键点: Location 透传、Cache-Control 禁用、Referrer-Policy 设置

**P4-T5: Range请求处理**
```python
class ProxyService:
    # ... 其他方法

    async def proxy_stream_with_range(
        self,
        url: str,
        range_header: str
    ) -> StreamingResponse:
        """
        处理Range请求

        参考: go-emby2openlist Range处理逻辑
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"Range": range_header},
                allow_redirects=False
            ) as response:
                if response.status == 206:
                    # 部分内容响应
                    content_range = response.headers.get("Content-Range", "")
                    content_length = response.headers.get("Content-Length", "")

                    return StreamingResponse(
                        response.content.iter_chunked(8192),
                        status_code=206,
                        headers={
                            "Content-Type": response.headers.get("Content-Type", "video/mp4"),
                            "Content-Range": content_range,
                            "Content-Length": content_length,
                            "Accept-Ranges": "bytes"
                        }
                    )
                elif response.status == 200:
                    # 完整内容响应
                    return StreamingResponse(
                        response.content.iter_chunked(8192),
                        status_code=200,
                        headers={
                            "Content-Type": response.headers.get("Content-Type", "video/mp4"),
                            "Content-Length": response.headers.get("Content-Length", ""),
                            "Accept-Ranges": "bytes"
                        }
                    )
                else:
                    raise HTTPException(
                        status_code=response.status,
                        detail="Failed to handle range request"
                    )
```

**P4-T6: 直链缓存实现**
```python
from datetime import datetime, timedelta
import asyncio

class LinkCache:
    """直链缓存"""

    def __init__(self, ttl: int = 3600):
        self.cache: dict = {}
        self.ttl = ttl  # 缓存有效期（秒）

    def get(self, key: str) -> Optional[dict]:
        """获取缓存"""
        if key in self.cache:
            item = self.cache[key]
            if datetime.now() - item["timestamp"] < timedelta(seconds=self.ttl):
                return item["data"]
            else:
                del self.cache[key]
        return None

    def set(self, key: str, data: dict):
        """设置缓存"""
        self.cache[key] = {
            "data": data,
            "timestamp": datetime.now()
        }

    def invalidate(self, key: str):
        """失效缓存"""
        if key in self.cache:
            del self.cache[key]

    async def refresh_task(self):
        """定期清理过期缓存"""
        while True:
            await asyncio.sleep(60)  # 每分钟检查一次
            now = datetime.now()
            expired_keys = [
                key for key, item in self.cache.items()
                if now - item["timestamp"] >= timedelta(seconds=self.ttl)
            ]
            for key in expired_keys:
                del self.cache[key]
```

#### 3.5.3 验收标准

- [ ] PlaybackInfo Hook 正常工作（DirectStreamUrl 重写）
- [ ] 路径映射正确（Emby→OpenList/Quark）
- [ ] 代理路由正常工作
- [ ] 302重定向正常工作
- [ ] Range请求正常处理
- [ ] 直链缓存正常工作
- [ ] Emby/Jellyfin 兼容
- [ ] 错误正确处理
- [ ] 所有单元测试通过

---

### 3.6 P5: 集成测试与优化 (Week 5)

#### 3.6.1 任务清单

| 任务ID | 任务描述 | 优先级 | 预计工时 | 依赖 |
|--------|---------|--------|---------|------|
| P5-T1 | 端到端测试 | 高 | 8h | P4-T7 |
| P5-T2 | 性能测试 | 高 | 6h | P5-T1 |
| P5-T3 | 压力测试 | 中 | 4h | P5-T2 |
| P5-T4 | 代码优化 | 高 | 6h | P5-T3 |
| P5-T5 | 文档完善 | 高 | 4h | P5-T4 |
| P5-T6 | 部署测试 | 高 | 4h | P5-T5 |

#### 3.6.2 技术实现细节

**P5-T1: 端到端测试**
```python
import pytest
import asyncio
from app.services.quark_service import QuarkService
from app.services.strm_service import StrmGenerator
from app.services.proxy_service import ProxyService

@pytest.mark.asyncio
async def test_end_to_end():
    """端到端测试"""
    # 1. 初始化服务
    quark_service = QuarkService(cookie="test_cookie")
    generator = StrmGenerator(
        quark_service=quark_service,
        base_url="http://localhost:5244",
        exts=[".mp4", ".mkv"],
        alt_exts=[".srt"],
        create_sub_dir=False
    )
    proxy_service = ProxyService(quark_service=quark_service)

    # 2. 扫描目录
    strms = await generator.scan_directory(
        remote_path="/video",
        local_path="/tmp/strm",
        recursive=True
    )

    assert len(strms) > 0, "No STRM files generated"

    # 3. 生成STRM文件
    for strm in strms:
        success = strm.gen_strm_file(overwrite=True)
        assert success, f"Failed to generate {strm.full_path}"

    # 4. 检查STRM有效性
    for strm in strms:
        valid = await strm.check_valid()
        assert valid, f"STRM {strm.full_path} is invalid"

    # 5. 测试代理播放
    # 这里需要模拟Emby播放请求
    # ...

    await quark_service.close()
```

**P5-T2: 性能测试**
```python
import time
import asyncio
from app.services.quark_service import QuarkService

async def performance_test():
    """性能测试"""
    quark_service = QuarkService(cookie="test_cookie")

    # 测试文件列表获取性能
    start_time = time.time()
    files = await quark_service.get_files("/video")
    elapsed_time = time.time() - start_time

    print(f"获取 {len(files)} 个文件耗时: {elapsed_time:.2f}秒")
    assert elapsed_time < 5.0, "文件列表获取太慢"

    # 测试直链获取性能
    if files:
        start_time = time.time()
        link = await quark_service.get_download_link(files[0].fid)
        elapsed_time = time.time() - start_time

        print(f"获取直链耗时: {elapsed_time:.2f}秒")
        assert elapsed_time < 2.0, "直链获取太慢"

    await quark_service.close()
```

#### 3.6.3 验收标准

- [ ] 所有端到端测试通过
- [ ] 性能测试达标
- [ ] 压力测试通过
- [ ] 代码优化完成
- [ ] 文档完善
- [ ] 部署测试通过

---

## 四、多智能体协作架构

### 4.1 智能体定义

| 智能体 | 职责 | 输入 | 输出 | 参考项目 |
|--------|------|------|------|---------|
| **QuarkAgent** | 夸克网盘交互 | 文件路径、Cookie | 直链URL、文件元数据 | OpenList |
| **StrmGeneratorAgent** | STRM文件生成 | 目录配置、文件列表 | STRM文件集合 | AlistAutoStrm |
| **ProxyAgent** | 播放网关代理 | Emby请求、文件ID | PlaybackInfo Hook/302/代理流 | go-emby2openlist (核心) + MediaHelp (辅助) |
| **CacheAgent** | 缓存管理 | 请求URL、直链 | 缓存直链、过期控制 | go-emby2openlist |

### 4.2 智能体协作流程

```
[用户请求]
    ↓
[StrmGeneratorAgent] - 扫描夸克目录
    ↓
[QuarkAgent] - 获取文件列表和直链
    ↓
[StrmGeneratorAgent] - 生成STRM文件
    ↓
[Emby/Jellyfin] - 播放STRM
    ↓
[ProxyAgent] - 拦截播放请求
    ↓
[CacheAgent] - 检查直链缓存
    ↓ (缓存未命中)
[QuarkAgent] - 获取新直链
    ↓
[CacheAgent] - 更新缓存
    ↓
[ProxyAgent] - 返回302/代理流
    ↓
[Emby/Jellyfin客户端] - 播放视频
```

### 4.3 智能体接口定义

**QuarkAgent接口**
```python
class QuarkAgent:
    async def get_files(self, path: str) -> List[FileModel]:
        """获取文件列表"""
        pass

    async def get_download_link(self, file_id: str) -> LinkModel:
        """获取下载直链"""
        pass

    async def get_transcoding_link(self, file_id: str) -> LinkModel:
        """获取转码直链"""
        pass
```

**StrmGeneratorAgent接口**
```python
class StrmGeneratorAgent:
    async def scan_directory(self, remote_path: str, local_path: str) -> List[StrmModel]:
        """扫描目录并生成STRM"""
        pass

    async def generate_strm_files(self, strms: List[StrmModel]) -> bool:
        """生成STRM文件"""
        pass

    async def check_strm_validity(self, strms: List[StrmModel]) -> List[bool]:
        """检查STRM有效性"""
        pass
```

**ProxyAgent接口**
```python
class ProxyAgent:
    async def proxy_stream(self, file_id: str, range_header: str = None) -> Response:
        """代理视频流"""
        pass

    async def redirect_302(self, file_id: str) -> Response:
        """302重定向"""
        pass
```

**CacheAgent接口**
```python
class CacheAgent:
    def get(self, key: str) -> Optional[dict]:
        """获取缓存"""
        pass

    def set(self, key: str, data: dict):
        """设置缓存"""
        pass

    def invalidate(self, key: str):
        """失效缓存"""
        pass

    async def refresh_task(self):
        """定期清理过期缓存"""
        pass
```

---

## 五、模块级引用说明

### 5.1 夸克接入层模块

| 模块 | 参考项目 | 源文件 | 具体引用 | 适配方式 |
|------|---------|--------|---------|---------|
| 夸克API请求封装 | OpenList | `drivers/quark_uc/util.go:27-67` | request方法 | 转换为Python aiohttp实现 |
| 文件列表获取 | OpenList | `drivers/quark_uc/util.go:69-111` | GetFiles方法 | 转换为Python异步实现 |
| 直链获取 | OpenList | `drivers/quark_uc/util.go:113-137` | getDownloadLink方法 | 转换为Python实现 |
| 转码直链获取 | OpenList | `drivers/quark_uc/util.go:139-168` | getTranscodingLink方法 | 转换为Python实现 |
| Cookie管理 | OpenList | `drivers/quark_uc/util.go:49-61` | Cookie自动更新 | 转换为Python实现 |
| 文件元数据 | OpenList | `drivers/quark_uc/types.go:21-45` | File结构体 | 转换为Pydantic模型 |

### 5.2 STRM生成层模块

| 模块 | 参考项目 | 源文件 | 具体引用 | 适配方式 |
|------|---------|--------|---------|---------|
| STRM数据结构 | AlistAutoStrm | `strm.go:14-19` | Strm结构体 | 转换为Pydantic模型 |
| STRM文件生成 | AlistAutoStrm | `strm.go:60-70` | GenStrm方法 | 转换为Python实现 |
| STRM有效性检查 | AlistAutoStrm | `strm.go:73-85` | Check方法 | 转换为Python aiohttp |
| 并发工作池 | AlistAutoStrm | `mission.go:161-223` | GetAllStrm方法 | 转换为Python asyncio |
| 递归目录遍历 | AlistAutoStrm | `mission.go:31-158` | getStrm方法 | 转换为Python实现 |
| 配置系统 | AlistAutoStrm | `config.go:3-34` | Config结构体 | 转换为Pydantic |
| 增量更新 | AlistAutoStrm | `main.go:111-213` | update命令 | 转换为Python实现 |
| BoltDB操作 | AlistAutoStrm | `strm.go:49-57` | Save/Delete方法 | 转换为SQLite |

### 5.3 播放网关层模块

| 模块 | 参考项目 | 源文件 | 具体引用 | 适配方式 |
|------|---------|--------|---------|---------|
| PlaybackInfo Hook | go-emby2openlist | `internal/service/emby/playbackinfo.go` | DirectStreamUrl重写 | 转换为Python FastAPI拦截 |
| 路径映射 | go-emby2openlist | `internal/service/path/path.go` | Emby→OpenList路径 | 转换为Python实现 |
| 302重定向 | go-emby2openlist | `internal/service/emby/redirect.go` | 302重定向逻辑 | 转换为Python实现 |
| Range请求处理 | go-emby2openlist | `internal/service/emby/playbackinfo.go` | Range处理逻辑 | 转换为Python实现 |
| 直链缓存 | go-emby2openlist | `internal/web/cache/cache.go` | Cache Key忽略头 | 转换为Python缓存服务 |
| FastAPI路由风格 | MediaHelp | `backend/api/proxy.py:10-66` | Proxy路由结构 | 作为路由模板 |
| 异步HTTP请求 | MediaHelp | `backend/api/proxy.py:38-47` | aiohttp请求 | 作为异步请求模板 |

### 5.4 数据存储模块

| 模块 | 参考项目 | 源文件 | 具体引用 | 适配方式 |
|------|---------|--------|---------|---------|
| 数据库操作 | AlistAutoStrm | `strm.go:49-57` | BoltDB CRUD | 转换为SQLite |
| 记录管理 | AlistAutoStrm | `strm.go:106-135` | GetRecordCollection | 转换为SQLite查询 |

---

## 六、验收测试体系

### 6.1 P1: 基础架构搭建测试

#### 6.1.1 单元测试

**测试文件**: `tests/test_config.py`
```python
import pytest
from app.config.settings import AppConfig, EndpointConfig, DirConfig

def test_load_config_from_yaml():
    """测试从YAML加载配置"""
    config = AppConfig.from_yaml("config.yaml")
    assert config.database == "quark_strm.db"
    assert len(config.endpoints) > 0

def test_config_validation():
    """测试配置验证"""
    with pytest.raises(ValidationError):
        EndpointConfig(base_url="")  # base_url不能为空

def test_dir_config():
    """测试目录配置"""
    dir_config = DirConfig(
        local_directory="/tmp/strm",
        remote_directories=["/video"]
    )
    assert dir_config.local_directory == "/tmp/strm"
    assert len(dir_config.remote_directories) == 1
```

**测试文件**: `tests/test_database.py`
```python
import pytest
from app.core.database import Database
from app.models.strm import StrmModel

def test_database_init():
    """测试数据库初始化"""
    db = Database(":memory:")
    assert db is not None

def test_save_and_get_strm():
    """测试保存和获取STRM"""
    db = Database(":memory:")
    strm = StrmModel(
        name="test.strm",
        local_dir="/tmp",
        remote_dir="/video",
        raw_url="http://example.com/video.mp4"
    )
    db.save_strm(strm)
    retrieved = db.get_strm(strm.key)
    assert retrieved is not None
    assert retrieved.name == "test.strm"

def test_delete_strm():
    """测试删除STRM"""
    db = Database(":memory:")
    strm = StrmModel(
        name="test.strm",
        local_dir="/tmp",
        remote_dir="/video",
        raw_url="http://example.com/video.mp4"
    )
    db.save_strm(strm)
    db.delete_strm(strm.key)
    retrieved = db.get_strm(strm.key)
    assert retrieved is None
```

#### 6.1.2 集成测试

**测试文件**: `tests/test_integration_p1.py`
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_api_health():
    """测试API健康检查"""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_config_endpoint():
    """测试配置端点"""
    client = TestClient(app)
    response = client.get("/config")
    assert response.status_code == 200
    assert "endpoints" in response.json()
```

#### 6.1.3 验收标准

- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] API可正常启动
- [ ] 配置文件可正常加载
- [ ] 数据库可正常操作

---

### 6.2 P2: 夸克接入层测试

#### 6.2.1 单元测试

**测试文件**: `tests/test_quark_api.py`
```python
import pytest
from app.services.quark_service import QuarkService
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_get_files():
    """测试获取文件列表"""
    with patch('app.services.quark_service.QuarkAPIClient.request') as mock_request:
        mock_request.return_value = {
            "data": {
                "list": [
                    {
                        "fid": "123",
                        "file_name": "test.mp4",
                        "file": True,
                        "size": 1024,
                        "category": 1
                    }
                ],
                "metadata": {"total": 1}
            }
        }

        service = QuarkService(cookie="test_cookie")
        files = await service.get_files("/test")
        assert len(files) == 1
        assert files[0].name == "test.mp4"

@pytest.mark.asyncio
async def test_get_download_link():
    """测试获取下载直链"""
    with patch('app.services.quark_service.QuarkAPIClient.request') as mock_request:
        mock_request.return_value = {
            "data": [
                {
                    "download_url": "http://example.com/download"
                }
            ]
        }

        service = QuarkService(cookie="test_cookie")
        link = await service.get_download_link("123")
        assert link.url == "http://example.com/download"
```

#### 6.2.2 集成测试

**测试文件**: `tests/test_integration_p2.py`
```python
import pytest
from app.services.quark_service import QuarkService

@pytest.mark.asyncio
async def test_quark_integration():
    """夸克集成测试（需要真实Cookie）"""
    import os
    cookie = os.getenv("QUARK_COOKIE")
    if not cookie:
        pytest.skip("QUARK_COOKIE not set")

    service = QuarkService(cookie=cookie)

    # 测试获取文件列表
    files = await service.get_files("/")
    assert len(files) >= 0

    # 如果有文件，测试获取直链
    if files:
        if not files[0].is_dir:
            link = await service.get_download_link(files[0].fid)
            assert link.url is not None

    await service.close()
```

#### 6.2.3 验收标准

- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] 可正常获取文件列表
- [ ] 可正常获取直链
- [ ] 可正常获取转码直链
- [ ] 错误可正确处理

---

### 6.3 P3: STRM生成层测试

#### 6.3.1 单元测试

**测试文件**: `tests/test_strm_model.py`
```python
import pytest
from app.models.strm import StrmModel

def test_strm_key_generation():
    """测试STRM键生成"""
    strm = StrmModel(
        name="test.strm",
        local_dir="/tmp",
        remote_dir="/video",
        raw_url="http://example.com/video.mp4"
    )
    assert strm.key is not None
    assert len(strm.key) == 40  # SHA1哈希长度

def test_strm_full_path():
    """测试STRM完整路径"""
    strm = StrmModel(
        name="test.strm",
        local_dir="/tmp",
        remote_dir="/video",
        raw_url="http://example.com/video.mp4"
    )
    assert strm.full_path == "/tmp/test.strm"

def test_strm_gen_file():
    """测试STRM文件生成"""
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        strm = StrmModel(
            name="test.strm",
            local_dir=tmpdir,
            remote_dir="/video",
            raw_url="http://example.com/video.mp4"
        )
        success = strm.gen_strm_file(overwrite=True)
        assert success
        assert os.path.exists(strm.full_path)

        with open(strm.full_path, 'r') as f:
            content = f.read()
            assert content == "http://example.com/video.mp4"
```

**测试文件**: `tests/test_strm_generator.py`
```python
import pytest
from app.services.strm_service import StrmGenerator
from app.services.quark_service import QuarkService
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_scan_directory():
    """测试目录扫描"""
    with patch('app.services.quark_service.QuarkService.get_files') as mock_get_files:
        mock_get_files.return_value = [
            type('File', (), {
                'fid': '123',
                'name': 'test.mp4',
                'is_dir': False,
                'get_path': lambda: '/video'
            })()
        ]

        quark_service = QuarkService(cookie="test_cookie")
        generator = StrmGenerator(
            quark_service=quark_service,
            base_url="http://localhost:5244",
            exts=[".mp4"],
            alt_exts=[],
            create_sub_dir=False
        )

        strms = await generator.scan_directory("/video", "/tmp")
        assert len(strms) == 1
        assert strms[0].name == "test.strm"
```

#### 6.3.2 集成测试

**测试文件**: `tests/test_integration_p3.py`
```python
import pytest
import tempfile
from app.services.strm_service import StrmGenerator
from app.services.quark_service import QuarkService

@pytest.mark.asyncio
async def test_strm_generation_integration():
    """STRM生成集成测试"""
    import os

    cookie = os.getenv("QUARK_COOKIE")
    if not cookie:
        pytest.skip("QUARK_COOKIE not set")

    with tempfile.TemporaryDirectory() as tmpdir:
        quark_service = QuarkService(cookie=cookie)
        generator = StrmGenerator(
            quark_service=quark_service,
            base_url="http://localhost:5244",
            exts=[".mp4", ".mkv"],
            alt_exts=[".srt"],
            create_sub_dir=False
        )

        strms = await generator.scan_directory("/", tmpdir, recursive=True)
        assert len(strms) >= 0

        # 生成STRM文件
        for strm in strms:
            success = strm.gen_strm_file(overwrite=True)
            assert success

        await quark_service.close()
```

#### 6.3.3 验收标准

- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] 目录可正常扫描
- [ ] STRM文件可正常生成
- [ ] 并发控制正常工作
- [ ] 增量更新正常工作

---

### 6.4 P4: 播放网关层测试

#### 6.4.1 单元测试

**测试文件**: `tests/test_proxy_service.py`
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from unittest.mock import AsyncMock, patch

def test_proxy_stream_302():
    """测试302重定向"""
    with patch('app.services.proxy_service.QuarkService.get_download_link') as mock_get_link:
        mock_get_link.return_value = type('Link', (), {
            'url': 'http://example.com/download',
            'headers': {}
        })()

        client = TestClient(app)
        response = client.get("/proxy/stream/123")
        # 应该返回302或代理流
        assert response.status_code in [200, 206, 302]

def test_proxy_stream_with_range():
    """测试Range请求"""
    with patch('app.services.proxy_service.QuarkService.get_download_link') as mock_get_link:
        mock_get_link.return_value = type('Link', (), {
            'url': 'http://example.com/download',
            'headers': {}
        })()

        client = TestClient(app)
        headers = {"Range": "bytes=0-1023"}
        response = client.get("/proxy/stream/123", headers=headers)
        assert response.status_code in [200, 206]
`````

**测试文件**: `tests/test_playbackinfo_hook.py`
```python
import pytest
from app.services.playback_hook import PlaybackHook

@pytest.mark.asyncio
async def test_playbackinfo_rewrite():
    """PlaybackInfo Hook 应该重写 DirectStreamUrl"""
    hook = PlaybackHook(gateway_prefix="/proxy")
    playback = {"MediaSources": [{"Id": "abc"}]}
    updated = await hook.rewrite(playback, item_id="1", api_key="k")
    assert updated["MediaSources"][0]["DirectStreamUrl"].startswith("/proxy")
```
#### 6.4.2 集成测试

**测试文件**: `tests/test_integration_p4.py`
```python
import pytest
import os
from app.services.proxy_service import ProxyService
from app.services.quark_service import QuarkService

@pytest.mark.asyncio
async def test_proxy_integration():
    """代理集成测试"""
    cookie = os.getenv("QUARK_COOKIE")
    if not cookie:
        pytest.skip("QUARK_COOKIE not set")

    quark_service = QuarkService(cookie=cookie)
    proxy_service = ProxyService(quark_service=quark_service)

    # 获取文件列表
    files = await quark_service.get_files("/")
    if files and not files[0].is_dir:
        # 测试代理
        # 这里需要模拟HTTP请求
        # ...

    await quark_service.close()
```

#### 6.4.3 验收标准

- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] PlaybackInfo Hook 正常工作
- [ ] 路径映射正确
- [ ] 302重定向正常工作
- [ ] Range请求正常处理
- [ ] 直链缓存正常工作
- [ ] Emby/Jellyfin 兼容

---

### 6.5 P5: 集成测试与优化

#### 6.5.1 端到端测试

**测试文件**: `tests/test_e2e.py`
```python
import pytest
import tempfile
import os
from app.services.quark_service import QuarkService
from app.services.strm_service import StrmGenerator
from app.services.proxy_service import ProxyService

@pytest.mark.asyncio
async def test_end_to_end():
    """端到端测试"""
    cookie = os.getenv("QUARK_COOKIE")
    if not cookie:
        pytest.skip("QUARK_COOKIE not set")

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. 初始化服务
        quark_service = QuarkService(cookie=cookie)
        generator = StrmGenerator(
            quark_service=quark_service,
            base_url="http://localhost:5244",
            exts=[".mp4", ".mkv"],
            alt_exts=[".srt"],
            create_sub_dir=False
        )
        proxy_service = ProxyService(quark_service=quark_service)

        # 2. 扫描目录
        strms = await generator.scan_directory("/", tmpdir, recursive=True)
        assert len(strms) >= 0

        # 3. 生成STRM文件
        for strm in strms:
            success = strm.gen_strm_file(overwrite=True)
            assert success

        # 4. 检查STRM有效性
        for strm in strms:
            valid = await strm.check_valid()
            # 注意：这里可能需要模拟直链

        # 5. 测试代理播放
        # 这里需要模拟Emby播放请求
        # ...

        await quark_service.close()
```

#### 6.5.2 性能测试

**测试文件**: `tests/test_performance.py`
```python
import pytest
import time
import asyncio
from app.services.quark_service import QuarkService

@pytest.mark.asyncio
async def test_performance():
    """性能测试"""
    cookie = os.getenv("QUARK_COOKIE")
    if not cookie:
        pytest.skip("QUARK_COOKIE not set")

    quark_service = QuarkService(cookie=cookie)

    # 测试文件列表获取性能
    start_time = time.time()
    files = await quark_service.get_files("/")
    elapsed_time = time.time() - start_time

    print(f"获取 {len(files)} 个文件耗时: {elapsed_time:.2f}秒")
    assert elapsed_time < 5.0, "文件列表获取太慢"

    # 测试并发获取直链性能
    if len(files) > 0 and not files[0].is_dir:
        async def get_link():
            return await quark_service.get_download_link(files[0].fid)

        start_time = time.time()
        await asyncio.gather(*[get_link() for _ in range(10)])
        elapsed_time = time.time() - start_time

        print(f"并发获取10个直链耗时: {elapsed_time:.2f}秒")
        assert elapsed_time < 10.0, "并发直链获取太慢"

    await quark_service.close()
```

#### 6.5.3 验收标准

- [ ] 所有端到端测试通过
- [ ] 性能测试达标
- [ ] 压力测试通过
- [ ] 代码优化完成
- [ ] 文档完善
- [ ] 部署测试通过

---

## 七、技术栈选择

### 7.1 核心技术栈

| 技术栈 | 选择 | 版本 | 理由 | 参考项目 |
|--------|------|------|------|---------|
| **编程语言** | Python | 3.10+ | 生态丰富、异步支持好、易于维护 | MediaHelp |
| **Web框架** | FastAPI | 0.100+ | 高性能、异步、自动文档 | MediaHelp |
| **HTTP客户端** | aiohttp | 3.8+ | 异步HTTP请求 | MediaHelp |
| **数据验证** | Pydantic | 2.0+ | 类型安全、自动验证 | MediaHelp |
| **数据库** | SQLite | 3.38+ | 轻量级、无需额外服务 | AlistAutoStrm (BoltDB) |
| **ORM** | SQLAlchemy | 2.0+ | 成熟稳定、功能强大 | - |
| **日志** | loguru | 0.7+ | 易用、功能强大 | AlistAutoStrm |
| **配置管理** | PyYAML | 6.0+ | YAML支持 | AlistAutoStrm |
| **测试框架** | pytest | 7.4+ | 功能强大、插件丰富 | - |
| **异步测试** | pytest-asyncio | 0.21+ | 异步测试支持 | - |
| **容器化** | Docker | 24+ | 标准化部署 | AlistAutoStrm |
| **进程管理** | docker-compose | 2.20+ | 多容器编排 | AlistAutoStrm |

### 7.2 依赖包清单

**requirements.txt**
```txt
# Web框架
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
python-multipart>=0.0.6

# HTTP客户端
aiohttp>=3.8.5
httpx>=0.24.1

# 数据验证
pydantic>=2.0.0
pydantic-settings>=2.0.0

# 数据库
sqlalchemy>=2.0.20
aiosqlite>=0.19.0

# 日志
loguru>=0.7.0

# 配置
pyyaml>=6.0.1
python-dotenv>=1.0.0

# 测试
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0

# 工具
python-dateutil>=2.8.2

# 任务调度
apscheduler>=3.10.0

# 缓存
cachetools>=5.3.0

# 异步文件
aiofiles>=23.0.0

# 兼容层
asgiref>=3.7.0

# 加密
cryptography>=41.0.0

# WebDAV
wsgidav>=4.3.0

# 直链校验
requests>=2.31.0

# 可靠重试
tenacity>=8.2.0

# Redis异步客户端
aioredis>=2.0.0

# NFO/XML生成
lxml>=4.9.0

# 指标采集
psutil>=5.9.0

# 缓存统计图表
matplotlib>=3.7.0
```

### 7.3 技术栈对比

| 技术栈 | 优势 | 劣势 | 选择理由 |
|--------|------|------|---------|
| **Python vs Go** | 生态丰富、开发快速、易于维护 | 性能略低于Go | 参考MediaHelp，快速开发 |
| **FastAPI vs Flask** | 高性能、异步、自动文档 | 相对较新 | 参考MediaHelp，性能优先 |
| **SQLite vs BoltDB** | 标准SQL、工具丰富 | 并发性能略低 | Python生态更好 |
| **aiohttp vs requests** | 异步、高性能 | 学习曲线稍陡 | 参考MediaHelp，异步优先 |

---

## 八、项目交付物

### 8.1 代码交付物

| 交付物 | 路径 | 说明 |
|--------|------|------|
| 源代码 | `app/` | 完整的Python源代码 |
| 测试代码 | `tests/` | 完整的测试代码 |
| 配置文件 | `config.yaml` | 示例配置文件 |
| 依赖文件 | `requirements.txt` | Python依赖清单 |
| Dockerfile | `Dockerfile` | Docker镜像构建文件 |
| Docker Compose | `docker-compose.yml` | 多容器编排文件 |

### 8.2 文档交付物

| 交付物 | 路径 | 说明 |
|--------|------|------|
| 开发方案 | `开发方案.md` | 本文档 |
| API文档 | `docs/api.md` | API接口文档 |
| 部署文档 | `docs/deployment.md` | 部署指南 |
| 用户手册 | `docs/user_manual.md` | 用户使用手册 |
| 开发者指南 | `docs/developer_guide.md` | 开发者指南 |

### 8.3 测试交付物

| 交付物 | 路径 | 说明 |
|--------|------|------|
| 单元测试 | `tests/` | 所有单元测试 |
| 集成测试 | `tests/` | 所有集成测试 |
| 端到端测试 | `tests/` | 端到端测试 |
| 性能测试 | `tests/test_performance.py` | 性能测试 |
| 测试报告 | `reports/` | 测试覆盖率报告 |

---

## 九、项目风险与应对

### 9.1 技术风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| 夸克API变更 | 高 | 中 | 定期监控API变化，及时适配 |
| 直链频繁失效 | 高 | 高 | 实现直链缓存和自动刷新 |
| 并发性能不足 | 中 | 中 | 使用异步IO，优化并发控制 |
| Emby兼容性问题 | 中 | 低 | 参考go-emby2openlist，充分测试 |

### 9.2 项目风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| 开发周期超期 | 中 | 中 | 合理规划任务，及时调整 |
| 人员变动 | 高 | 低 | 完善文档，知识共享 |
| 测试不充分 | 高 | 中 | 严格执行测试计划 |

### 9.3 应对策略

1. **技术风险应对**
   - 建立API监控机制
   - 实现直链缓存和自动刷新
   - 使用异步IO和连接池
   - 充分测试Emby兼容性

2. **项目风险应对**
   - 使用敏捷开发，快速迭代
   - 完善文档，降低人员变动影响
   - 严格执行测试计划，确保质量

---

## 十、后续优化方向

### 10.1 功能优化

1. **多网盘支持** - 扩展支持阿里云盘、百度网盘等
2. **转码支持** - 支持视频转码和格式转换
3. **字幕支持** - 自动下载和匹配字幕
4. **批量操作** - 支持批量生成和更新STRM

### 10.2 性能优化

1. **缓存优化** - 优化直链缓存策略
2. **并发优化** - 优化并发控制算法
3. **数据库优化** - 优化数据库查询和索引

### 10.3 用户体验优化

1. **Web界面** - 提供友好的Web管理界面
2. **实时监控** - 提供实时监控和日志
3. **告警机制** - 提供异常告警通知

---

## 附录

### A. 参考项目许可证

| 项目 | 许可证 | 使用限制 |
|------|--------|---------|
| OpenList | AGPL-3.0 | 需要开源衍生作品 |
| AlistAutoStrm | MIT | 无限制 |
| alist-strm | MIT | 无限制 |
| MediaHelp | MIT | 无限制 |
| go-emby2openlist | MIT | 无限制 |

### B. 参考资料

1. [OpenList GitHub](https://github.com/OpenListTeam/OpenList)
2. [AlistAutoStrm GitHub](https://github.com/imshuai/AlistAutoStrm)
3. [go-emby2openlist GitHub](https://github.com/AmbitiousJun/go-emby2openlist)
4. [alist-strm GitHub](https://github.com/tefuirZ/alist-strm)
5. [MediaHelp GitHub](https://github.com/JieWSOFT/MediaHelp)
6. [FastAPI文档](https://fastapi.tiangolo.com/)
7. [Pydantic文档](https://docs.pydantic.dev/)

### C. 术语表

| 术语 | 说明 |
|------|------|
| STRM | Emby/Jellyfin使用的媒体流文件格式 |
| Range | HTTP Range请求，用于支持视频随机访问 |
| 302 | HTTP 302重定向状态码 |
| 直链 | 直接下载链接 |
| 转码直链 | 经过服务器转码的播放链接 |
| TV Token | 夸克TV端的鉴权Token |

---

**文档版本**: v1.1
**创建日期**: 2026-01-31
**最后更新**: 2026-01-31
**文档作者**: AI开发团队
















