"""FastAPI 入口：/api/parse 解析、/api/download 流式下载代理，并托管前端静态文件。"""
from __future__ import annotations

import re
import time
from urllib.parse import quote

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.staticfiles import StaticFiles

from .auth import (
    COOKIE_NAME,
    check_password,
    create_token,
    is_auth_enabled,
    is_request_authenticated,
    verify_auth,
)
from .config import settings
from .parser import extract_url, parse
from .platforms import detect_source
from .proxy import stream_download
from .schemas import AuthStatusResponse, LoginRequest, LoginResponse, ParseResult
from .security import is_allowed_source

app = FastAPI(title="视频去水印", docs_url="/api/docs", openapi_url="/api/openapi.json")

# 简单的内存 TTL 缓存：link -> (timestamp, ParseResult)
_cache: dict[str, tuple[float, ParseResult]] = {}


def _safe_filename(title: str | None, ext: str) -> str:
    base = (title or "video").strip()
    base = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", base)[:60].strip() or "video"
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
    if result.cover:
        # 封面预览也走代理：小红书/B站等 CDN 对图片同样有防盗链，直连 <img> 会 403。
        result.cover_download_url = _proxied(
            result.cover, _safe_filename(f"{result.title or 'cover'}", _img_ext(result.cover))
        )
    for i, img in enumerate(result.images, start=1):
        img.download_url = _proxied(
            img.url, _safe_filename(f"{result.title or 'image'}_{i}", _img_ext(img.url))
        )
    return result


@app.get("/api/auth/status", response_model=AuthStatusResponse)
def api_auth_status(
    request: Request,
    dwm_auth: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
):
    enabled = is_auth_enabled()
    authenticated = is_request_authenticated(request, dwm_auth, authorization) if enabled else True
    return AuthStatusResponse(required=enabled, authenticated=authenticated)


@app.post("/api/auth/login", response_model=LoginResponse)
def api_auth_login(req: LoginRequest, response: Response):
    if not is_auth_enabled():
        return LoginResponse(ok=True)

    if not check_password(req.password):
        raise HTTPException(status_code=401, detail="密码错误，请重新输入")

    token = create_token()
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.auth_token_ttl,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return LoginResponse(ok=True, token=token)


@app.post("/api/auth/logout")
def api_auth_logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/parse", response_model=ParseResult, dependencies=[Depends(verify_auth)])
def api_parse(url: str = Query(..., description="抖音 / 西瓜 / 小红书 / B站 分享文案或链接")):
    link = extract_url(url) or url.strip()
    if not is_allowed_source(link):
        raise HTTPException(status_code=400, detail="仅支持抖音 / 西瓜 / 小红书 / B站 链接")

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

    plat = detect_source(link)
    result.platform = plat.name if plat else None
    result = _attach_download_urls(result)
    _cache[link] = (now, result)
    return result


@app.get("/api/download", dependencies=[Depends(verify_auth)])
async def api_download(
    url: str = Query(..., description="媒体 CDN 直链"),
    filename: str = Query("douyin.mp4"),
    inline: bool = Query(False, description="内联打开（浏览器直接显示/播放）而非强制下载"),
):
    return await stream_download(url, filename, inline=inline)


@app.get("/api/health")
def health():
    return {"ok": True}


# 生产环境：托管前端构建产物（单 Origin，避免 CORS）。开发环境用 Vite dev server，
# 此目录不存在则不挂载。必须放在所有 /api 路由之后，才不会抢占它们。
_dist = settings.frontend_dist
if _dist is not None:
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
