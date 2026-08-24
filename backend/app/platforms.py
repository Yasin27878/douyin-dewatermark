"""平台注册表：把"每个平台哪里不一样"（来源域名 / CDN 白名单 / Referer / 是否要访客
cookie）集中到一处，避免这些差异散落在 config / proxy / parser 里各写一份硬编码。

新增一个平台 = 在 PLATFORMS 里加一条。字节系（抖音 / 西瓜）复用同一份访客 cookie，
且在多数通用 CDN 上共用。
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

# 抖音/西瓜（字节系）用移动端 UA；B站/小红书要用桌面端 UA——B站在移动 UA 下会让
# yt-dlp 退回 generic 提取器（拿不到真实格式），desktop UA 才会走 BiliBili 提取器。
MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class Platform:
    key: str                       # 内部标识，如 "douyin"
    name: str                      # 展示名，如 "抖音"
    source_hosts: tuple[str, ...]  # 识别输入链接的域名（含短链域名）
    media_hosts: tuple[str, ...]   # 允许下载代理转发的 CDN 域名
    referer: str | None            # 下载 / 抓页面时带的 Referer（None 表示不带）
    user_agent: str                # 抓页面 / 解析 / 下载统一用的 UA
    use_guest_cookies: bool        # 是否附带字节系访客 cookie（仅字节系需要）


# 字节系视频/图片 CDN 经常轮换，抖音与西瓜在多数通用 CDN 上共用这批。
_BYTEDANCE_SHARED = (
    "byteimg.com",
    "bytecdn.cn",
    "365yg.com",
    "pstatp.com",
    "snssdk.com",
    "volccdn.com",
    "toutiaovod.com",
    "vlabvod.com",
)

PLATFORMS: tuple[Platform, ...] = (
    Platform(
        key="douyin",
        name="抖音",
        source_hosts=("douyin.com", "iesdouyin.com"),  # douyin.com 已覆盖 v.douyin.com
        media_hosts=("douyinvod.com", "douyinpic.com", "amemv.com", "zjcdn.com") + _BYTEDANCE_SHARED,
        referer="https://www.douyin.com/",
        user_agent=MOBILE_UA,
        use_guest_cookies=True,
    ),
    Platform(
        key="ixigua",
        name="西瓜视频",
        source_hosts=("ixigua.com",),  # 覆盖 www./v.ixigua.com
        media_hosts=("ixiguavideo.com", "ixigua.com") + _BYTEDANCE_SHARED,
        referer="https://www.ixigua.com/",
        user_agent=MOBILE_UA,
        use_guest_cookies=True,
    ),
    Platform(
        key="xiaohongshu",
        name="小红书",
        source_hosts=("xiaohongshu.com", "xhslink.com", "xhslink.cn"),  # 分享短链有 .com 和 .cn 两种
        media_hosts=("xhscdn.com",),  # 覆盖 sns-video-*/sns-img-*.xhscdn.com
        referer="https://www.xiaohongshu.com/",
        user_agent=DESKTOP_UA,
        use_guest_cookies=False,
    ),
    Platform(
        key="bilibili",
        name="B站",
        source_hosts=("bilibili.com", "b23.tv"),
        media_hosts=("bilivideo.com", "bilivideo.cn", "hdslb.com", "akamaized.net"),
        referer="https://www.bilibili.com/",
        user_agent=DESKTOP_UA,
        use_guest_cookies=False,
    ),
)


def _host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _match(host: str, patterns: tuple[str, ...]) -> bool:
    if not host:
        return False
    return any(host == p or host.endswith("." + p) for p in patterns)


def detect_source(url: str) -> Platform | None:
    """按来源域名判断输入链接属于哪个平台。"""
    host = _host_of(url)
    for p in PLATFORMS:
        if _match(host, p.source_hosts):
            return p
    return None


def for_media(url: str) -> Platform | None:
    """按 CDN 域名判断媒体直链属于哪个平台（用于挑下载 Referer）。
    共享 CDN（如 byteimg.com）会命中注册表中靠前的平台，字节系 CDN 对 douyin/ixigua
    两种 Referer 都放行，不影响下载。"""
    host = _host_of(url)
    for p in PLATFORMS:
        if _match(host, p.media_hosts):
            return p
    return None


def all_source_hosts() -> list[str]:
    """所有平台来源域名的去重并集，作为 ALLOWED_SOURCE_HOSTS 的默认值。"""
    seen: list[str] = []
    for p in PLATFORMS:
        for h in p.source_hosts:
            if h not in seen:
                seen.append(h)
    return seen


def all_media_hosts() -> list[str]:
    """所有平台 CDN 域名的去重并集，作为 ALLOWED_MEDIA_HOSTS 的默认值。"""
    seen: list[str] = []
    for p in PLATFORMS:
        for h in p.media_hosts:
            if h not in seen:
                seen.append(h)
    return seen
