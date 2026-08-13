"""AI 引擎配置

所有敏感配置和部署相关值均从 .env 文件读取。
本文件只提供空默认值和类型声明，不包含任何真实密钥或地址。
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（本文件位于 ai/app/，向上两级到根目录）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # Redis（任务队列 + 缓存）
    REDIS_URL: str = ""

    # 后端服务地址
    BACKEND_URL: str = ""

    # 本地微调模型
    LOCAL_MODEL_URL: str = ""
    LOCAL_MODEL_NAME: str = ""

    # 远程大模型 API
    REMOTE_MODEL_API_KEY: str = ""
    REMOTE_MODEL_BASE_URL: str = ""
    REMOTE_MODEL_NAME: str = ""

    # 快速回答模型（内网部署的 Qwen3.5-9B）
    QUICK_MODEL_URL: str = ""
    QUICK_MODEL_NAME: str = ""

    # DeepSeek 深度解答模型
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = ""
    DEEPSEEK_MODEL_NAME: str = ""

    # ChromaDB
    CHROMADB_HOST: str = ""
    CHROMADB_PORT: int = 8000

    # 服务间认证（backend → ai）
    SERVICE_TOKEN: str = ""

    # 知识图谱
    KG_DATA_DIR: str = "data/kg"
    KG_MODEL_API_KEY: str = ""
    KG_MODEL_BASE_URL: str = ""
    KG_MODEL_NAME: str = ""
    KG_PRUNING_ENABLED: bool = True  # 知识图谱后处理剪枝总开关

    # OCR 文档解析
    OCR_VLM_URL: str = ""
    OCR_OUTPUT_DIR: str = "data/ocr_output"
    OCR_TASK_RETENTION_SECONDS: int = 86400
    OCR_MAX_CONCURRENT: int = 2

    # Apache AGE
    AGE_HOST: str = ""
    AGE_PORT: int = 5432
    AGE_DB: str = ""
    AGE_USER: str = ""
    AGE_PASSWORD: str = ""
    AGE_GRAPH_NAME: str = ""

    # MCP 联网搜索
    MCP_SEARCH_URL: str = ""
    MCP_SEARCH_TOKEN: str = ""
    MCP_SERVER_URLS: str = ""  # 逗号分隔的 MCP Server URL 列表，自动遍历连接
    MCP_PROXY: str = ""

    # MCP 数据库服务 (FastMCP SSE)
    MCP_DB_URL: str = ""

    # BGE-M3 嵌入模型
    BGE_M3_URL: str = ""
    BGE_M3_DIM: int = 1024

    # BGE-Reranker-v2-M3 重排序模型
    BGE_RERANKER_URL: str = ""

    # pgvector DSN（留空则从 AGE 配置自动构建）
    PGVECTOR_DSN: str = ""

    # RAG Pipeline 三阶段参数
    RAG_VECTOR_TOP_K: int = 30
    RAG_FUSION_TOP_K: int = 15
    RAG_RERANKER_TOP_K: int = 5

    def get_mcp_server_urls(self) -> list[str]:
        """返回所有待连接的 MCP Server URL 列表

        从 MCP_SERVER_URLS（逗号分隔）解析。
        """
        if not self.MCP_SERVER_URLS:
            return []
        urls = [u.strip() for u in self.MCP_SERVER_URLS.split(",") if u.strip()]
        # 去重保序
        seen: set[str] = set()
        return [u for u in urls if not (u in seen or seen.add(u))]

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        extra="ignore"
    )

settings = Settings()


def get_pgvector_dsn() -> str:
    """返回 pgvector 连接 DSN

    优先使用 PGVECTOR_DSN，否则从 AGE 配置自动构建。
    因为 AGE 和 document_chunks 在同一个 PostgreSQL 实例中。
    """
    if settings.PGVECTOR_DSN:
        return settings.PGVECTOR_DSN
    return (
        f"postgresql://{settings.AGE_USER}:{settings.AGE_PASSWORD}"
        f"@{settings.AGE_HOST}:{settings.AGE_PORT}/{settings.AGE_DB}"
    )
