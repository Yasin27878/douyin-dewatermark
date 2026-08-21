"""运行配置。所有项都可用环境变量覆盖，便于部署时调整而无需改代码。"""
from __future__ import annotations

import os
from pathlib import Path

# 抖音网页/接口请求统一用的 UA（移动端）。
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)


def _csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if not raw:
        return default
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


class Settings:
    # 允许解析的来源站点（输入链接必须命中，否则拒绝，防 SSRF）。
    # 匹配规则：host 完全相等，或以 ".<pattern>" 结尾（即子域）。
    allowed_source_hosts: list[str] = _csv_env(
        "ALLOWED_SOURCE_HOSTS",
        ["douyin.com", "iesdouyin.com"],
    )

    # 允许下载代理转发的媒体 CDN 站点（均为字节跳动系 CDN）。抖音视频/图片分布在
    # 多个 CDN 上且经常轮换——下载报「不在白名单」时，把报错里的新 host 加进来即可。
    allowed_media_hosts: list[str] = _csv_env(
        "ALLOWED_MEDIA_HOSTS",
        [
            "douyinvod.com",
            "douyinpic.com",
            "byteimg.com",
            "bytecdn.cn",
            "365yg.com",
            "ixigua.com",
            "ixiguavideo.com",
            "amemv.com",
            "zjcdn.com",
            "pstatp.com",
            "snssdk.com",
            "volccdn.com",
            "toutiaovod.com",
            "vlabvod.com",
        ],
    )

    # 解析结果内存缓存时长（秒），减少对抖音的重复请求。
    parse_cache_ttl: int = int(os.environ.get("PARSE_CACHE_TTL", "600"))

    # 访客 cookie 缓存时长（秒）。ttwid 有效期较长，这里定期刷新即可。
    cookie_ttl: int = int(os.environ.get("COOKIE_TTL", "1800"))

    # 前端构建产物目录。Docker 里显式设为 /app/frontend/dist；
    # 本地开发若未设置，则回退到仓库内 frontend/dist（存在才挂载）。
    @property
    def frontend_dist(self) -> Path | None:
        env = os.environ.get("FRONTEND_DIST")
        candidates = []
        if env:
            candidates.append(Path(env))
        # 仓库布局：backend/app/config.py -> parents[2] = 仓库根
        candidates.append(Path(__file__).resolve().parents[2] / "frontend" / "dist")
        for c in candidates:
            if c and c.is_dir():
                return c
        return None


settings = Settings()
