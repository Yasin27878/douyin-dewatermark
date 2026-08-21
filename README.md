# 抖音去水印

[![Build & Push](https://github.com/Yasin27878/douyin-dewatermark/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/Yasin27878/douyin-dewatermark/actions/workflows/docker-publish.yml)

粘贴抖音分享链接 → 获取**无水印原始视频**（也支持图集）。

- **后端**：FastAPI + [yt-dlp](https://github.com/yt-dlp/yt-dlp) 解析 + 带 Referer 的流式下载代理。
- **前端**：轻量网页（原生 JS），做成 **PWA + Web Share Target**——在 Android 抖音里点「分享」即可直达本工具、链接自动带入。
- **架构**：FastAPI 单 Origin 同时托管 API 与前端，避免 CORS，部署简单。

> 为什么核心用 yt-dlp：抖音接口/签名经常变，这部分维护交给活跃的社区项目。**解析一旦失效，第一步永远是升级 yt-dlp。**

## 目录结构

```
backend/        FastAPI + yt-dlp
  app/
    main.py     /api/parse、/api/download，并托管前端
    parser.py   yt-dlp 封装：链接 → 标准化结果
    proxy.py    流式下载代理（带 Referer，host 白名单）
    security.py 输入/媒体 URL 域名白名单（防 SSRF / 开放代理）
    schemas.py  响应模型
    config.py   白名单、缓存等配置（可用环境变量覆盖）
frontend/       Vite + 原生 JS + PWA
Dockerfile      多阶段：Node 构建前端 → Python 运行时托管
docker-compose.yml
Caddyfile       可选的自动 HTTPS 反代
```

## 本地开发

需要 Python 3.11+ 与 Node 18+，两个终端：

```bash
# 终端 1：后端
cd backend
python -m venv .venv && . .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8182

# 终端 2：前端（dev server 会把 /api 代理到 :8182）
cd frontend
npm install
npm run dev   # 打开 http://localhost:5173
```

快速自测（用一条真实抖音分享链接）：

```bash
curl "http://localhost:8182/api/parse?url=<抖音分享文案或短链>"
curl -L "http://localhost:8182/api/download?url=<video_url>&filename=test.mp4" -o out.mp4
```

播放 `out.mp4`，确认**没有飘动水印 / 没有 @用户名 角标**。

## Docker 部署

```bash
docker compose up -d --build      # 访问 http://<服务器IP>:8182
```

> 对外端口默认 **8182**，在 `docker-compose.yml` 的 `ports`（`"8182:8182"` 左边的数字）改。容器内应用也监听 8182。

带 HTTPS（PWA 安装 / 抖音分享目标在真机上需要 HTTPS）：

1. 域名 A 记录解析到服务器公网 IP；
2. 编辑 `Caddyfile`，把 `your.domain.com` 换成你的域名；
3. `docker compose --profile https up -d --build`，访问 `https://your.domain.com`。

## 发布到 Docker Hub

> 镜像**自包含**：访客 cookie 在运行时自动获取，**不需要任何密钥 / 环境变量**，拉下来直接跑。
>
> **推荐用 CI 自动发布**：仓库已带 [.github/workflows/docker-publish.yml](.github/workflows/docker-publish.yml) —— 推到 `main` 自动发 `latest`、打 tag（如 `git tag 0.1-beta && git push origin 0.1-beta`）自动发对应版本号，一次出 `amd64` + `arm64` 多架构。只需在 GitHub 仓库 **Settings → Secrets and variables → Actions** 配好 `DOCKERHUB_USERNAME` 与 `DOCKERHUB_TOKEN`（Docker Hub Access Token）。下面是手动发布方式：

```bash
# 1) 登录 Docker Hub
docker login

# 2) 构建并打 tag —— ⚠️ 架构必须和你的服务器一致！
#    绝大多数云服务器是 linux/amd64；树莓派 / 部分 ARM 云是 linux/arm64。

# 方式 A：本机与服务器同架构，直接 build
docker build -t yasin27878/douyin-dewatermark:0.1-beta .

# 方式 B（推荐，跨架构最稳）：buildx 一次出多架构并直接推送
#   Docker Desktop 自带多架构支持；纯 Linux 首次需先跑：
#   docker run --privileged --rm tonistiigi/binfmt --install all
docker buildx build --platform linux/amd64,linux/arm64 \
  -t yasin27878/douyin-dewatermark:0.1-beta --push .

# 3) 推送（方式 A 需要这步；方式 B 带了 --push 可跳过）
docker push yasin27878/douyin-dewatermark:0.1-beta
```

在服务器上拉取运行（二选一）：

```bash
# 方式 1：用 docker-compose.hub.yml（把里面的 image 改成你的镜像名）
docker compose -f docker-compose.hub.yml up -d

# 方式 2：直接 docker run
docker run -d --name douyin-dewatermark -p 8182:8182 --restart unless-stopped \
  yasin27878/douyin-dewatermark:0.1-beta
```

访问 `http://<服务器IP>:8182`。`docker ps` 的 STATUS 出现 `healthy` 即为就绪。

## 在 Android 上「分享直达」

1. 用手机 Chrome 打开你的 **HTTPS** 站点；
2. 菜单 →「添加到主屏幕 / 安装应用」；
3. 之后在抖音点「分享」，系统分享列表里会出现「去水印」，点它即可自动带入链接并解析。

> `localhost` 被视为安全上下文，可在本机调试；但真机安装 + 分享目标需要真正的 HTTPS 域名。

## 配置（环境变量）

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `ALLOWED_SOURCE_HOSTS` | 允许解析的来源站点（逗号分隔） | `douyin.com,iesdouyin.com` |
| `ALLOWED_MEDIA_HOSTS` | 允许下载代理转发的 CDN 站点 | 见 `config.py` |
| `PARSE_CACHE_TTL` | 解析结果内存缓存秒数 | `600` |
| `FRONTEND_DIST` | 前端产物目录（Docker 内已设好） | 自动探测 |

## 工作原理（关键点）

1. **规范化链接**：`v.douyin.com` 短链 / `iesdouyin.com/share/...` 分享页会跟随重定向，
   取出数字 id，拼成 yt-dlp 认识的 `https://www.douyin.com/video/<id>`。
2. **访客 cookie**：yt-dlp 的抖音 extractor 需要"新鲜 cookie（不必登录）"。服务端会自动
   从 ByteDance register 接口取 `ttwid` + 合成 `msToken`，写成 cookie 文件喂给 yt-dlp，
   并缓存复用（`COOKIE_TTL`）。
3. **下载代理**：拿到的是 CDN 直链（如 `*.365yg.com`），前端经 `/api/download` 由后端带
   `Referer` 流式转发，规避防盗链/跨域。

## 维护 runbook

- **解析失败 / 拿不到视频**：先升级 yt-dlp
  ```bash
  # 本地
  pip install -U yt-dlp
  # Docker
  docker compose build --no-cache && docker compose up -d
  ```
- **报 cookie 相关错误（"Fresh cookies …"）**：服务已会自动刷新一次；若持续失败，可能是
  register 接口拿不到 `ttwid` 了 —— 退路是从浏览器导出 `cookies.txt`（访客态即可），
  通过 yt-dlp 的 `cookiefile` 传入。
- **下载报「媒体地址不在允许的 CDN 白名单内」**：抖音换了 CDN。把报错里出现的新 host 加进 `ALLOWED_MEDIA_HOSTS`。
- **升级后仍带水印（fallback，暂未内置）**：改为走 detail 接口取 `play_addr` 并把地址里的 `playwm` 替换为 `play`。

## 法律与免责

本项目仅供个人学习与备份使用。请遵守抖音服务条款，尊重原作者版权，不要用于侵权传播或商业用途。
