"""把抖音链接解析成标准化结果（视频 / 图集）。

流程：
1. 跟随短链/分享页重定向，一次请求同时拿到最终 URL 和分享页 HTML。
2. **图文帖（图集）**：抖音分享页（iesdouyin）会把内容服务端渲染进
   `window._ROUTER_DATA`，其中 `images[*].url_list` 就是**无水印**大图直链
   （注意 `download_url_list` 反而是带水印版本，不能用）。这条路不依赖签名，最稳。
3. **视频**：交给 yt-dlp（抖音接口/签名的适配由其社区维护），规范化成它认识的
   `https://www.douyin.com/video/<id>` 再解析；cookie 相关报错时刷新一次重试。

维护要点：视频解析失败时，第一步永远是升级 yt-dlp（`pip install -U yt-dlp`
或重建镜像）。图集解析失败通常是分享页结构变了，看 `_ROUTER_DATA` 的取值路径。
"""
from __future__ import annotations

import json
import re

import httpx
import yt_dlp

from .config import USER_AGENT
from .cookies import get_cookiefile, get_cookies
from .schemas import MediaImage, ParseResult

# 从"复制此链接，打开抖音…"这类整段分享文案里抽出真正的 URL。
# 停在中文标点/空白/括号处，避免把后面的文字也吞进链接。
_URL_RE = re.compile(r"""https?://[^\s，,。、"'）)】\]<>]+""", re.IGNORECASE)

# 从任意抖音 URL 里提取内容 id
_ID_RE = re.compile(r"/(?:share/)?(?:video|note|slides)/(\d+)")
_MODAL_RE = re.compile(r"[?&](?:modal_id|aweme_id)=(\d+)")

# 分享页内嵌的服务端渲染数据
_ROUTER_DATA_RE = re.compile(r"window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*</script>", re.S)

# 触发"抓分享页 HTML"的链接特征（短链 / 分享页 / 图文帖）
_RESOLVE_HINTS = ("v.douyin.com", "iesdouyin.com", "/share/", "/note/", "/slides/")

_IMAGE_EXTS = {"jpg", "jpeg", "png", "webp", "heic", "gif", "bmp"}

_HTTP_HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": "https://www.douyin.com/",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

_YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "noplaylist": False,  # 图集会以 playlist 形式返回，需要保留
    "extract_flat": False,
    "http_headers": {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.douyin.com/",
    },
}


def extract_url(text: str) -> str | None:
    """从任意粘贴文本里提取第一个 http(s) 链接。"""
    if not text:
        return None
    m = _URL_RE.search(text.strip())
    return m.group(0) if m else None


def parse(url: str) -> ParseResult:
    """解析单条抖音链接，返回标准化结果。可能抛异常，由调用方兜底。"""
    final_url, html = _resolve(url)
    aweme_id = _extract_id(final_url) or _extract_id(url)

    # 1) 图文帖：分享页 _ROUTER_DATA 里直接有无水印大图
    images = _images_from_html(html, final_url)
    if images:
        return images

    # 2) 视频：交给 yt-dlp（它维护抖音签名/格式适配）
    video_url = f"https://www.douyin.com/video/{aweme_id}" if aweme_id else final_url
    try:
        info = _run_ydl(video_url)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e).lower()
        if "cookie" in msg:
            info = _run_ydl(video_url, force_cookies=True)
        elif aweme_id:
            # yt-dlp 抖音 extractor 只会解视频；若其实是图文帖，抓分享页兜底。
            fallback = _images_from_html(_fetch_share_html(aweme_id), video_url)
            if fallback:
                return fallback
            raise
        else:
            raise
    return _normalize(info, video_url)


# ---------------------------------------------------------------------------
# 链接解析 / 抓分享页
# ---------------------------------------------------------------------------


def _extract_id(url: str | None) -> str | None:
    if not url:
        return None
    m = _ID_RE.search(url) or _MODAL_RE.search(url)
    return m.group(1) if m else None


def _resolve(url: str) -> tuple[str, str | None]:
    """跟随重定向，返回 (最终URL, HTML)。非分享类链接不抓 HTML（HTML 为 None）。"""
    if not any(h in url for h in _RESOLVE_HINTS):
        return url, None
    try:
        with httpx.Client(
            follow_redirects=True, timeout=15, headers=_HTTP_HEADERS, cookies=get_cookies()
        ) as hc:
            resp = hc.get(url)
            return str(resp.url), resp.text
    except httpx.HTTPError:
        return url, None


def _fetch_share_html(aweme_id: str) -> str | None:
    """兜底：直接抓 iesdouyin 图文分享页 HTML。"""
    try:
        with httpx.Client(
            follow_redirects=True, timeout=15, headers=_HTTP_HEADERS, cookies=get_cookies()
        ) as hc:
            resp = hc.get(f"https://www.iesdouyin.com/share/note/{aweme_id}/")
            return resp.text
    except httpx.HTTPError:
        return None


# ---------------------------------------------------------------------------
# 图文帖：从分享页 _ROUTER_DATA 提取无水印大图
# ---------------------------------------------------------------------------


def _images_from_html(html: str | None, source_url: str) -> ParseResult | None:
    if not html:
        return None
    m = _ROUTER_DATA_RE.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return None

    item = _find_aweme_item(data)
    if not item:
        return None
    raw_images = item.get("images")
    if not raw_images:
        return None  # 不是图文帖（视频），交给 yt-dlp

    urls: list[str] = []
    for im in raw_images:
        u = _pick_image_url((im or {}).get("url_list") or [])
        if u:
            urls.append(u)
    if not urls:
        return None

    return ParseResult(
        type="images",
        source_url=source_url,
        title=(item.get("desc") or "").strip() or None,
        author=_author_name(item),
        cover=urls[0],
        images=[MediaImage(url=u) for u in urls],
    )


def _find_aweme_item(data: dict) -> dict | None:
    """在 _ROUTER_DATA.loaderData.*.videoInfoRes.item_list[0] 里找到内容对象。"""
    loader = (data or {}).get("loaderData")
    if not isinstance(loader, dict):
        return None
    for page in loader.values():
        if not isinstance(page, dict):
            continue
        item_list = (page.get("videoInfoRes") or {}).get("item_list")
        if isinstance(item_list, list) and item_list and isinstance(item_list[0], dict):
            return item_list[0]
    return None


def _pick_image_url(url_list: list[str]) -> str | None:
    """从一张图的镜像直链里挑一个：优先 jpeg（通用可存），否则第一个。
    这些都是 url_list（无水印），绝不用 download_url_list（带水印）。"""
    if not url_list:
        return None
    for u in url_list:
        path = u.split("?", 1)[0].lower()
        if path.endswith(".jpeg") or path.endswith(".jpg"):
            return u
    return url_list[0]


def _author_name(item: dict) -> str | None:
    author = item.get("author") or {}
    return author.get("nickname") or author.get("unique_id") or None


def _run_ydl(url: str, force_cookies: bool = False) -> dict:
    opts = dict(_YDL_OPTS)
    opts["cookiefile"] = get_cookiefile(force=force_cookies)
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


# ---------------------------------------------------------------------------
# 视频：从 yt-dlp 的 info dict 里挑出我们需要的字段
# ---------------------------------------------------------------------------


def _normalize(info: dict, source_url: str) -> ParseResult:
    author = info.get("uploader") or info.get("creator") or info.get("uploader_id")
    title = (info.get("title") or "").strip() or None

    # 图集：某些 extractor 会把图文帖表示为 playlist，entries 里是各张图片。
    entries = info.get("entries")
    if info.get("_type") == "playlist" or entries:
        entries = [e for e in (entries or []) if e]
        image_urls: list[str] = []
        video_entries: list[dict] = []
        for e in entries:
            if _is_image_entry(e):
                u = _best_image_url(e)
                if u:
                    image_urls.append(u)
            else:
                video_entries.append(e)

        if image_urls and not video_entries:
            return ParseResult(
                type="images",
                source_url=source_url,
                title=title,
                author=author,
                cover=info.get("thumbnail") or image_urls[0],
                images=[MediaImage(url=u) for u in image_urls],
            )
        # 含视频的合集：取第一条视频继续按单视频处理
        if video_entries:
            info = video_entries[0]
            title = title or (info.get("title") or "").strip() or None
            author = author or info.get("uploader")

    return ParseResult(
        type="video",
        source_url=source_url,
        title=title,
        author=author,
        cover=info.get("thumbnail"),
        duration=info.get("duration"),
        video_url=_best_video_url(info),
    )


def _has_video(f: dict) -> bool:
    return f.get("vcodec") not in (None, "none")


def _has_audio(f: dict) -> bool:
    return f.get("acodec") not in (None, "none")


def _best_video_url(info: dict) -> str | None:
    formats = [f for f in (info.get("formats") or []) if f.get("url")]
    # 优先「音视频合一」的渐进式格式，避免下到无声视频
    progressive = [f for f in formats if _has_video(f) and _has_audio(f)]
    video_only = [f for f in formats if _has_video(f)]
    pool = progressive or video_only or formats
    if not pool:
        return info.get("url")

    def score(f: dict):
        return (
            f.get("height") or 0,
            f.get("tbr") or 0,
            f.get("filesize") or f.get("filesize_approx") or 0,
        )

    return sorted(pool, key=score)[-1]["url"]


def _is_image_entry(entry: dict) -> bool:
    if entry.get("_type") == "image":
        return True
    ext = (entry.get("ext") or "").lower()
    if ext in _IMAGE_EXTS:
        return True
    # 无视频编码 + 无音频编码，通常是图片
    if entry.get("vcodec") in ("none", None) and entry.get("acodec") in ("none", None):
        url = entry.get("url") or ""
        return any(url.lower().split("?")[0].endswith("." + e) for e in _IMAGE_EXTS)
    return False


def _best_image_url(entry: dict) -> str | None:
    if entry.get("url"):
        return entry["url"]
    formats = entry.get("formats") or []
    if formats:
        return formats[-1].get("url")
    thumbs = entry.get("thumbnails") or []
    if thumbs:
        return thumbs[-1].get("url")
    return None
