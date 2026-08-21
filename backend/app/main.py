"""FastAPI 入口：/api/parse 解析、/api/download 流式下载代理，并托管前端静态文件。"""
from __future__ import annotations

import re
import time
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from .config import settings
from .parser import extract_url, parse
from .proxy import stream_download
from .schemas import ParseResult
from .security import is_allowed_source

app = FastAPI(title="抖音去水印", docs_url="/api/docs", openapi_url="/api/openapi.json")

# 简单的内存 TTL 缓存：link -> (timestamp, ParseResult)
_cache: dict[str, tuple[float, ParseResult]] = {}


def _safe_filename(title: str | None, ext: str) -> str:
    base = (title or "douyin").strip()
    base = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", base)[:60].strip() or "douyin"
    return f"{base}.{ext}"


def _proxied(media_url: str, filename: str) -> str:
    return f"/api/download?url={quote(media_url, safe='')}&filename={quote(filename)}"


def _img_ext(url: str) -> str:
    """从图片直链推断扩展名（jpeg 归一为 jpg），认不出则默认 jpg。"""
    path = url.split("?", 1)[0].lower()
    for e in ("jpg", "jpeg", "png", "webp", "gif", "heic", "bmp"):
        if path.endswith("." + e):
            return "jpg" if e == "jpeg" else e
    return "jpg"


def _attach_download_urls(result: ParseResult) -> ParseResult:
    """把 CDN 直链包装成走本服务代理的下载地址。"""
    if result.video_url:
        result.download_url = _proxied(result.video_url, _safe_filename(result.title, "mp4"))
    for i, img in enumerate(result.images, start=1):
        img.download_url = _proxied(
            img.url, _safe_filename(f"{result.title or 'douyin'}_{i}", _img_ext(img.url))
        )
    return result


@app.get("/api/parse", response_model=ParseResult)
def api_parse(url: str = Query(..., description="抖音分享文案或链接")):
    link = extract_url(url) or url.strip()
    if not is_allowed_source(link):
        raise HTTPException(status_code=400, detail="仅支持抖音链接")

    now = time.time()
    cached = _cache.get(link)
    if cached and now - cached[0] < settings.parse_cache_ttl:
        return cached[1]

    try:
        result = parse(link)
    except Exception as e:  # yt-dlp 解析失败
        raise HTTPException(status_code=502, detail=f"解析失败：{e}")

    if not result.video_url and not result.images:
        raise HTTPException(status_code=502, detail="没有解析到可下载的媒体，试试升级 yt-dlp")

    result = _attach_download_urls(result)
    _cache[link] = (now, result)
    return result


@app.get("/api/download")
async def api_download(
    url: str = Query(..., description="媒体 CDN 直链"),
    filename: str = Query("douyin.mp4"),
):
    return await stream_download(url, filename)


@app.get("/api/health")
def health():
    return {"ok": True}


# 生产环境：托管前端构建产物（单 Origin，避免 CORS）。开发环境用 Vite dev server，
# 此目录不存在则不挂载。必须放在所有 /api 路由之后，才不会抢占它们。
_dist = settings.frontend_dist
if _dist is not None:
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
