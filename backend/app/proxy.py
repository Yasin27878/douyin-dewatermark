"""流式下载代理：带上抖音要求的 Referer 把 CDN 内容转发给浏览器，
强制 attachment 触发下载，同时规避浏览器直连 CDN 的跨域/防盗链问题。

安全：只转发命中媒体白名单的 host，避免变成开放代理。
"""
from __future__ import annotations

from urllib.parse import quote

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from .config import USER_AGENT
from .security import is_allowed_media_host

_HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": "https://www.douyin.com/",
}


def _content_disposition(filename: str) -> str:
    # 同时给 ASCII 回退与 UTF-8（filename*），中文文件名也能正常下载。
    ascii_fallback = filename.encode("ascii", "ignore").decode() or "download"
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"


async def stream_download(url: str, filename: str) -> StreamingResponse:
    if not is_allowed_media_host(url):
        raise HTTPException(status_code=400, detail="媒体地址不在允许的 CDN 白名单内")

    client = httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(30.0, read=None))
    req = client.build_request("GET", url, headers=_HEADERS)
    try:
        resp = await client.send(req, stream=True)
    except httpx.HTTPError as e:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"上游请求失败：{e}")

    if resp.status_code >= 400:
        status = resp.status_code
        await resp.aclose()
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"上游返回 {status}")

    media_type = resp.headers.get("content-type", "application/octet-stream")

    async def body():
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()
            await client.aclose()

    headers = {"Content-Disposition": _content_disposition(filename)}
    if "content-length" in resp.headers:
        headers["Content-Length"] = resp.headers["content-length"]
    return StreamingResponse(body(), media_type=media_type, headers=headers)
