"""网页访问密码验证与鉴权。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from typing import Optional

from fastapi import Cookie, Header, HTTPException, Request, status

from .config import settings

COOKIE_NAME = "dwm_auth"


def is_auth_enabled() -> bool:
    """是否启用了访问密码验证。若环境变量 AUTH_PASSWORD 非空则启用。"""
    return bool(settings.auth_password)


def create_token() -> str:
    """生成带时间戳与 HMAC-SHA256 签名的 token，格式为 <timestamp>.<signature>。"""
    ts = int(time.time())
    sig = _sign(ts, settings.auth_password)
    return f"{ts}.{sig}"


def _sign(timestamp: int, secret: str) -> str:
    msg = f"{timestamp}:{secret}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def verify_token(token: str | None) -> bool:
    """校验 token 是否有效且在有效期内。"""
    if not is_auth_enabled():
        return True
    if not token or "." not in token:
        return False
    try:
        ts_part, sig = token.split(".", 1)
        ts = int(ts_part)
    except (ValueError, TypeError):
        return False

    now = time.time()
    if now < ts or (now - ts) > settings.auth_token_ttl:
        return False

    expected_sig = _sign(ts, settings.auth_password)
    return hmac.compare_digest(expected_sig, sig)


def check_password(password: str) -> bool:
    """校验明文密码是否正确（使用 compare_digest 防止时序攻击）。"""
    if not is_auth_enabled():
        return True
    return secrets.compare_digest(password or "", settings.auth_password)


def extract_token(
    request: Request,
    dwm_auth: Optional[str] = None,
    authorization: Optional[str] = None,
) -> str | None:
    """从 Cookie、Authorization 头（Bearer）或 Query 参数提取 token。"""
    if dwm_auth:
        return dwm_auth
    if authorization:
        if authorization.startswith("Bearer "):
            return authorization[7:].strip()
        return authorization.strip()
    return request.query_params.get("token") or request.query_params.get("auth")


def is_request_authenticated(
    request: Request,
    dwm_auth: Optional[str] = None,
    authorization: Optional[str] = None,
) -> bool:
    """检查当前请求是否已通过认证。"""
    if not is_auth_enabled():
        return True

    # 1. 优先校验 token（Cookie / Bearer Header / Query 参数 token/auth）
    token = extract_token(request, dwm_auth, authorization)
    if token and verify_token(token):
        return True

    # 2. 支持 Authorization 头部（Bearer 携带密码 或 HTTP Basic Auth）
    if authorization:
        if authorization.startswith("Basic "):
            try:
                decoded = base64.b64decode(authorization[6:].strip()).decode("utf-8")
                parts = decoded.split(":", 1)
                pw = parts[1] if len(parts) > 1 else parts[0]
                if check_password(pw):
                    return True
            except Exception:
                pass
        else:
            raw_val = authorization.removeprefix("Bearer ").strip()
            if check_password(raw_val):
                return True

    # 3. 支持在 Query 参数中直接携带密码（如 ?pwd=xxx 或 ?password=xxx），便于外部播放器直接打开媒体链接
    query_pwd = request.query_params.get("pwd") or request.query_params.get("password")
    if query_pwd and check_password(query_pwd):
        return True

    return False


def verify_auth(
    request: Request,
    dwm_auth: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None),
) -> bool:
    """FastAPI 依赖项：验证请求。若未通过认证则抛出 401。"""
    if not is_auth_enabled():
        return True

    if is_request_authenticated(request, dwm_auth, authorization):
        return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未授权或访问密码已过期，请重新验证",
    )
