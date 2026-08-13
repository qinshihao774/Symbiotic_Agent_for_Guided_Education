"""应用配置 — 从环境变量加载"""

from pathlib import Path

# 支持从环境变量或.env文件读取字符串形式的DEBUG配置，兼容多种常用真假标识格式并自动转换为布尔值
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（本文件位于 backend/app/core/，向上三级到根目录）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "ChuMa Backend"
    DEBUG: bool = False

    # 数据库
    DATABASE_URL: str = "postgresql+asyncpg://chuma:chuma@localhost:5432/chuma"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 小时

    # AI 服务
    AI_SERVICE_URL: str
    AI_SERVICE_TOKEN: str  # 必须与 ai/app/config.py 中的 SERVICE_TOKEN 一致

    # 本地模型（vLLM）
    LOCAL_MODEL_URL: str
    LOCAL_MODEL_NAME: str

    # 远程大模型
    REMOTE_MODEL_API_KEY: str
    REMOTE_MODEL_BASE_URL: str
    REMOTE_MODEL_NAME: str

    # ChromaDB
    CHROMADB_HOST: str
    CHROMADB_PORT: int

    # Apache AGE（知识图谱图数据库）
    AGE_HOST: str
    AGE_PORT: int
    AGE_DB: str
    AGE_USER: str
    AGE_PASSWORD: str
    AGE_GRAPH_NAME: str

    # 服务间认证（兼容 ai/ 的 SERVICE_TOKEN 字段名）
    SERVICE_TOKEN: str

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:80"]

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_flag(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "dev", "development"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return value

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        extra="ignore"
    )

settings = Settings()
