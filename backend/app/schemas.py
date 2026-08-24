"""API 响应数据模型。"""
from __future__ import annotations

from pydantic import BaseModel


class MediaImage(BaseModel):
    url: str                       # 原始 CDN 直链
    download_url: str | None = None  # 走本服务代理的下载地址


class ParseResult(BaseModel):
    type: str                      # "video" | "images"
    source_url: str               # 归一化后的来源链接
    platform: str | None = None    # 平台展示名（抖音 / 西瓜视频 / 小红书 / B站）
    title: str | None = None
    author: str | None = None
    cover: str | None = None       # 封面（原始 CDN 直链）
    cover_download_url: str | None = None  # 走本服务代理的封面地址（预览用，规避防盗链）
    duration: float | None = None  # 秒
    video_url: str | None = None   # 无水印视频 CDN 直链
    download_url: str | None = None  # 走本服务代理的视频下载地址
    images: list[MediaImage] = []  # 图集
