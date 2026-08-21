"""访客 cookie 获取与缓存。

yt-dlp 的抖音 extractor 需要"新鲜 cookie（不必登录）"才能调接口。这里在服务端
自动拿一份访客 cookie（ttwid + 合成 msToken 等），写成 Netscape 格式给 yt-dlp 用，
并做内存缓存，避免每次解析都重新获取。

维护：若某天抖音变更导致解析报 cookie 相关错误，先看 register 接口是否还能拿到
ttwid；实在不行可改为让用户从浏览器导出 cookies.txt 传入（yt-dlp 原生支持）。
"""
from __future__ import annotations

import base64
import os
import tempfile
import threading
import time

import httpx

from .config import USER_AGENT, settings

_lock = threading.Lock()
# 同时缓存 cookie 字典（给 httpx 直接抓分享页用）和 Netscape 文件（给 yt-dlp 用）。
_cache: dict = {"cookies": None, "file": None, "ts": 0.0}

_REGISTER_URL = "https://ttwid.bytedance.com/ttwid/union/register/"
_REGISTER_PAYLOAD = {
    "region": "cn",
    "aid": 1768,
    "needFid": False,
    "service": "www.ixigua.com",
    "migrate_info": {"ticket": "", "source": "node"},
    "cbUrlProtocol": "https",
    "union": True,
}


def _fetch_cookies() -> dict[str, str]:
    cookies: dict[str, str] = {}
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(timeout=20, headers=headers, follow_redirects=True) as hc:
        # ttwid：register 接口直接下发（无需登录）
        try:
            r = hc.post(_REGISTER_URL, json=_REGISTER_PAYLOAD)
            if "ttwid" in r.cookies:
                cookies["ttwid"] = r.cookies["ttwid"]
        except httpx.HTTPError:
            pass
        # 访问首页补充 __ac_nonce 等
        try:
            hc.get("https://www.douyin.com/")
            for ck in hc.cookies.jar:
                cookies.setdefault(ck.name, ck.value or "")
        except httpx.HTTPError:
            pass
    # msToken：合成一个随机串即可满足接口的存在性校验
    cookies["msToken"] = base64.b64encode(os.urandom(94)).decode().rstrip("=")
    return cookies


def _write_netscape(cookies: dict[str, str], path: str) -> None:
    expires = int(time.time()) + 3600 * 24 * 180
    lines = ["# Netscape HTTP Cookie File\n"]
    for name, value in cookies.items():
        # domain, include_subdomains, path, secure, expiry, name, value
        lines.append("\t".join([".douyin.com", "TRUE", "/", "FALSE", str(expires), name, value]) + "\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def get_cookies(force: bool = False) -> dict[str, str]:
    """返回一份访客 cookie 字典（带内存缓存），供 httpx 直接请求抖音时使用。"""
    with _lock:
        now = time.time()
        cached = _cache.get("cookies")
        if (
            not force
            and isinstance(cached, dict)
            and now - float(_cache["ts"]) < settings.cookie_ttl
        ):
            return cached

        cookies = _fetch_cookies()
        path = os.path.join(tempfile.gettempdir(), "douyin_guest_cookies.txt")
        _write_netscape(cookies, path)
        _cache["cookies"] = cookies
        _cache["file"] = path
        _cache["ts"] = now
        return cookies


def get_cookiefile(force: bool = False) -> str:
    """返回一个可交给 yt-dlp 的 Netscape cookie 文件路径（带内存缓存）。"""
    with _lock:
        now = time.time()
        cached = _cache.get("file")
        if (
            not force
            and isinstance(cached, str)
            and os.path.exists(cached)
            and now - float(_cache["ts"]) < settings.cookie_ttl
        ):
            return cached

    # 缓存失效：get_cookies 会同时刷新 cookie 字典与文件。
    get_cookies(force=True)
    return _cache["file"]  # type: ignore[return-value]
