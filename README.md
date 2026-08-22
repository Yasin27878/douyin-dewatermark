# 抖音去水印

粘贴抖音分享链接，拿到无水印原视频，也支持图集。

[GitHub](https://github.com/Yasin27878/douyin-dewatermark) ｜ [Docker Hub](https://hub.docker.com/r/yasin27878/douyin-dewatermark)

- 后端：FastAPI + yt-dlp 解析，带 Referer 的流式下载代理。
- 前端：原生 JS 网页，做成 PWA，可在 Android 抖音「分享」里直达。
- 单 Origin：一个 FastAPI 同时托管 API 和前端，不涉及 CORS。

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
| `ALLOWED_SOURCE_HOSTS` | 允许解析的来源站点 | `douyin.com,iesdouyin.com` |
| `ALLOWED_MEDIA_HOSTS` | 允许下载代理转发的 CDN | 见 `config.py` |
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

1. `v.douyin.com` 短链、分享页跟随重定向取出视频 id，拼成 yt-dlp 认识的地址。
2. yt-dlp 的抖音 extractor 需要新鲜访客 cookie（不必登录），服务端自动获取并缓存。
3. 拿到的是带防盗链的 CDN 直链，前端经 `/api/download` 由后端加 `Referer` 流式转发。

## 维护

- 解析失败、拿不到视频：先升级 yt-dlp（`pip install -U yt-dlp`，Docker 则重新构建）。
- 下载报「媒体地址不在允许的 CDN 白名单内」：抖音换了 CDN，把报错里的新 host 加进 `ALLOWED_MEDIA_HOSTS`。

## 反馈

如果有问题，或者有好的建议，欢迎到 [GitHub Issues](https://github.com/Yasin27878/douyin-dewatermark/issues) 提。

## 免责

仅供个人学习与备份使用，请尊重原作者版权，勿用于侵权传播或商业用途。
