# 进度存档 / Progress

> 用于续做。计划全文：`C:\Users\admin\.claude\plans\steady-plotting-glade.md`

## 项目一句话
抖音去水印工具：贴分享链接 → 拿无水印原视频。**网页 + PWA（Android 分享直达）+ yt-dlp 解析核心**。

## 已完成 ✅（后端已端到端跑通并验证，2026-08-21）
- 全部代码写好：`backend/app/*.py`、`frontend/`、`Dockerfile`、`docker-compose.yml`、`Caddyfile`、`README.md`。
- 后端依赖装在 `backend/.venv`（yt-dlp 2026.08.19）；语法编译通过；冒烟测试通过。
- 前端 `npm install` + `npm run build` 通过；FastAPI 单 Origin 托管（API+SPA+manifest+sw+icon）验证通过。
- **视频**端到端验证：`v.douyin.com/QZRHRZatLZI/` → 解析出标题/作者/时长190s → 经 `/api/download` 代理下载到 **32MB 有效 mp4**。视频 URL 无 `playwm`（=无水印变体）。样片存在仓库根 `out.mp4`。
- **图文帖/图集**端到端验证（2026-08-21 修复）：`v.douyin.com/RfTqFxK8NUQ/` → 解析出 `type=images` + 无水印大图 → 经 `/api/download` 代理下载到真实 `image/jpeg`。
- **用户已确认视频 + 图片功能均正常**（2026-08-21）。
- **Docker 部署配置就绪**（2026-08-21）：端口**全项目统一 8182**（`docker-compose.yml` `ports: "8182:8182"`，容器内 uvicorn 也监听 8182）。Dockerfile 用 `npm ci`（已本机验证 lockfile 同步、build 通过）+ pip 装依赖 + 自带 `HEALTHCHECK` 打 `/api/health`；`.dockerignore` 排除 `.venv/node_modules/dist/__pycache__/out.mp4`。删掉了冗余的 `backend/Dockerfile`（会 build 出没前端的镜像、且单独 build 时根 `.dockerignore` 不生效）。发布用：镜像 tag `0.1-beta`，服务器拉取用 `docker-compose.hub.yml`，步骤见 README「发布到 Docker Hub」。
- **已实跑通 build → 本地冒烟 → push（2026-08-22）**：在装了 Docker Desktop 4.87 的开发机上 `docker build` 成功（linux/amd64）；本地起容器 `/api/health` 秒回 `200 {"ok":true}`；`docker push` 成功。镜像 **`yasin27878/douyin-dewatermark:0.1-beta`**（public，amd64，约 63MB，digest `sha256:9503d529…`）已在 Docker Hub。
  - ⚠️ 环境坑：这台机器的 `docker` 不在 Git Bash PATH 里，需用绝对路径 `"/c/Users/admin/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe"`（或 export 该 bin 到 PATH）；WSL2 首次要先 `wsl --install`+重启，引擎才起得来。

## 修复过的关键坑（非显然）
1. 短链跟随后是 `iesdouyin.com/share/video/<id>`，yt-dlp 不认 → 规范化成 `www.douyin.com/video/<id>`（`parser`：只拼 `/video/`，因为 yt-dlp DouyinIE 只认 `/video/<id>`，detail 接口本身按 aweme_id 取，不分 video/note）。
2. yt-dlp 报 "Fresh cookies needed" → 服务端自动取访客 cookie：`ttwid`(ByteDance register 接口)+合成 `msToken`，写 cookie 文件喂 yt-dlp（`app/cookies.py`），带缓存+失败刷新重试。
3. 真实视频 CDN 是 `*.365yg.com`，已补进 `config.allowed_media_hosts`。
4. **图文帖(图集) yt-dlp 根本解不了**：DouyinIE 的 `_parse_aweme_video_app` 只从 `aweme_detail['video']` 建 video formats，无任何 images 处理。→ 改走**分享页抓取**：`iesdouyin.com/share/note/<id>` 的 HTML 里 `window._ROUTER_DATA.loaderData.*.videoInfoRes.item_list[0].images[*].url_list` 就是**无水印**大图（`parser._images_from_html`）。这条路不依赖签名，最稳；短链跟随那一次 GET 顺手拿 HTML，视频照旧走 yt-dlp。
   - ⚠️ 陷阱：同级的 `download_url_list` 反而是**带水印**版本（模板含 `-water`），千万别用；要用 `url_list`。

## 还没做 ⏳
1. **在服务器上拉取运行并验证**：镜像已发布（`yasin27878/douyin-dewatermark:0.1-beta`，amd64）。服务器上 `docker run -d -p 8182:8182 --restart unless-stopped yasin27878/douyin-dewatermark:0.1-beta`（或 `docker compose -f docker-compose.hub.yml up -d`），放行 8182 端口，访问 `http://<IP>:8182`。⚠️ 服务器若为 ARM，需另出 arm64 镜像（`docker buildx --platform linux/arm64,linux/amd64 … --push`）。
2. **Android 分享直达**：需 HTTPS 域名 → 填 `Caddyfile` → `docker compose --profile https up -d --build`（Caddy 反代容器内 `app:8182`，走 80/443）→ 手机 Chrome 安装 PWA。

## 待观察
- 若发现仍带水印 → 实现 `playwm→play` fallback（README 已记录）。
- 若某天报 cookie 错且自动刷新无效 → 退路：浏览器导出 `cookies.txt` 传给 yt-dlp。
- PWA 图标目前只有 SVG；个别机型若拒绝安装，补 PNG 192/512。
