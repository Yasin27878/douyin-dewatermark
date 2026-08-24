# 视频去水印

粘贴分享链接，拿到无水印 / 原始视频，抖音图集也支持。支持 **抖音 / 西瓜视频 / 小红书 / B站**。

[GitHub](https://github.com/Yasin27878/douyin-dewatermark) ｜ [Docker Hub](https://hub.docker.com/r/yasin27878/douyin-dewatermark)

- 后端：FastAPI + yt-dlp 解析，带 Referer 的流式下载代理。
- 前端：原生 JS 网页，做成 PWA，可在 Android「分享」里直达。
- 单 Origin：一个 FastAPI 同时托管 API 和前端，不涉及 CORS。

## 支持平台与说明

| 平台 | 支持情况 |
| --- | --- |
| 抖音 | 视频 + 图集（无水印大图），最完整。 |
| 西瓜视频 | 视频。 |
| 小红书 | 视频笔记；纯图文笔记可能解析不了（yt-dlp 限制）。 |
| B站 | 视频。音视频是分离的，直链下载**可能没有声音**；高清需登录，未登录约 480/720p。 |

短链（`v.douyin.com` / `xhslink.com` / `xhslink.cn` / `b23.tv` / `v.ixigua.com`）直接粘贴即可，会自动展开。

## 使用

用 Docker 跑起来，访问 `http://<你的IP>:8182`。

```bash
docker compose -f docker-compose.hub.yml up -d
```

或者不用 compose：

```bash
docker run -d --name douyin-dewatermark -p 8182:8182 --restart unless-stopped \
  yasin27878/douyin-dewatermark:latest
```

对外端口改 `-p` 左边的数字。`docker ps` 里 STATUS 显示 healthy 即就绪。镜像自包含，访客 cookie 运行时自动获取，不需要任何密钥。

可选环境变量：

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `ALLOWED_SOURCE_HOSTS` | 允许解析的来源站点 | 各平台域名并集，见 `platforms.py` |
| `ALLOWED_MEDIA_HOSTS` | 允许下载代理转发的 CDN | 各平台 CDN 并集，见 `platforms.py` |
| `PARSE_CACHE_TTL` | 解析结果缓存秒数 | `600` |

## 本地开发

需要 Python 3.11+ 和 Node 18+，开两个终端：

```bash
# 后端
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8182

# 前端（dev server 会把 /api 代理到 :8182）
cd frontend
npm install
npm run dev   # http://localhost:5173
```

## 工作原理

1. 识别链接属于哪个平台（`platforms.py`）；短链先跟随重定向拿到规范地址。
2. 抖音图集直接从分享页取无水印大图；视频交给 yt-dlp（字节系需要自动获取的访客 cookie，不必登录）。
3. 拿到的是带防盗链的 CDN 直链，前端经 `/api/download` 由后端按平台加 `Referer` 流式转发。

## 维护

- 新增平台：在 `backend/app/platforms.py` 的 `PLATFORMS` 里加一条（来源域名 / CDN / Referer / UA / 是否要 cookie）。
- 解析失败、拿不到视频：先升级 yt-dlp（`pip install -U yt-dlp`，Docker 则重新构建）。
- 下载报「媒体地址不在允许的 CDN 白名单内」：平台换了 CDN，把报错里的新 host 加进 `ALLOWED_MEDIA_HOSTS`。

## 反馈

如果有问题，或者有好的建议，欢迎到 [GitHub Issues](https://github.com/Yasin27878/douyin-dewatermark/issues) 提。

## 免责

仅供个人学习与备份使用，请尊重原作者版权，勿用于侵权传播或商业用途。
