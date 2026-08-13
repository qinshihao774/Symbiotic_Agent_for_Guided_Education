"""AI 引擎公共依赖 — 服务间认证"""

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import settings

service_token_header = APIKeyHeader(name="X-Service-Token", auto_error=False)


async def verify_service_token(token: str | None = Depends(service_token_header)):
    """验证 backend 发来的服务间认证 token

    Production: backend 在请求头中注入 X-Service-Token，AI 引擎校验。
    Testing:    通过 override dependency 跳过校验。
    """
    if token != settings.SERVICE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid service token",
        )
