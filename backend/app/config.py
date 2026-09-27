"""运行配置。所有项都可用环境变量覆盖，便于部署时调整而无需改代码。"""
from __future__ import annotations

import os
from pathlib import Path

from .platforms import MOBILE_UA, all_media_hosts, all_source_hosts

# 抖音相关（抓分享页 HTML、生成访客 cookie）统一用移动端 UA。各平台解析/下载时用的 UA
# 由 platforms.py 按平台决定（见 Platform.user_agent）。
USER_AGENT = MOBILE_UA


def _csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if not raw:
        return default
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


class Settings:
    # 允许解析的来源站点（输入链接必须命中，否则拒绝，防 SSRF）。默认取各平台来源域名
    # 的并集（见 platforms.py）。匹配规则：host 完全相等，或以 ".<pattern>" 结尾（即子域）。
    allowed_source_hosts: list[str] = _csv_env(
        "ALLOWED_SOURCE_HOSTS",
        all_source_hosts(),
    )

    # 允许下载代理转发的媒体 CDN 站点。默认取各平台 CDN 域名的并集（见 platforms.py）。
    # CDN 经常轮换——下载报「不在白名单」时，把报错里的新 host 加进来即可（逗号分隔）。
    allowed_media_hosts: list[str] = _csv_env(
        "ALLOWED_MEDIA_HOSTS",
        all_media_hosts(),
    )

    # 解析结果内存缓存时长（秒），减少对抖音的重复请求。
    parse_cache_ttl: int = int(os.environ.get("PARSE_CACHE_TTL", "600"))

    # 访客 cookie 缓存时长（秒）。ttwid 有效期较长，这里定期刷新即可。
    cookie_ttl: int = int(os.environ.get("COOKIE_TTL", "1800"))

    # 可选的网页及 API 访问保护密码。留空或未设置表示不启用密码验证。
    auth_password: str = os.environ.get("AUTH_PASSWORD", "").strip()

    # 密码验证凭据有效期（秒），默认 30 天。
    auth_token_ttl: int = int(os.environ.get("AUTH_TOKEN_TTL", str(30 * 86400)))

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
