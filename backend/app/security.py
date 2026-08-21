"""URL 域名白名单校验：防止本服务被当成 SSRF / 开放代理滥用。"""
from __future__ import annotations

from urllib.parse import urlparse

from .config import settings


def host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _match(host: str, patterns: list[str]) -> bool:
    if not host:
        return False
    for p in patterns:
        p = p.lower()
        if host == p or host.endswith("." + p):
            return True
    return False


def is_allowed_source(url: str) -> bool:
    """输入解析链接是否来自允许的站点（抖音）。"""
    return _match(host_of(url), settings.allowed_source_hosts)


def is_allowed_media_host(url: str) -> bool:
    """下载代理要转发的媒体地址是否在允许的 CDN 白名单内。"""
    return _match(host_of(url), settings.allowed_media_hosts)
