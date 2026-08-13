"""LLM 模型配置 — 定义可用的模型 profile"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelProfile:
    """一个 LLM 端点的完整配置

    无论是本地部署（vLLM/Ollama）还是远程 API（讯飞星火等），
    对调用方来说 interface 完全相同：base_url + model + auth。
    """
    base_url: str
    model_name: str
    api_key: str = ""
    timeout: float = 120.0
    max_retries: int = 2
    extra_headers: dict[str, str] = field(default_factory=dict)

    @property
    def auth_headers(self) -> dict[str, str]:
        headers = dict(self.extra_headers)
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def local_profile() -> ModelProfile:
    """从环境变量构建本地模型 profile"""
    from app.config import settings
    return ModelProfile(
        base_url=settings.LOCAL_MODEL_URL,
        model_name=settings.LOCAL_MODEL_NAME,
        timeout=60.0,
    )


def remote_profile() -> ModelProfile:
    """从环境变量构建远程模型 profile"""
    from app.config import settings
    return ModelProfile(
        base_url=settings.REMOTE_MODEL_BASE_URL,
        model_name=settings.REMOTE_MODEL_NAME,
        api_key=settings.REMOTE_MODEL_API_KEY,
        timeout=120.0,
    )


def quick_profile() -> ModelProfile:
    """快速回答模型 profile（内网 Qwen3.5-9B）"""
    from app.config import settings
    return ModelProfile(
        base_url=settings.QUICK_MODEL_URL,
        model_name=settings.QUICK_MODEL_NAME,
        timeout=60.0,
    )


def deepseek_profile() -> ModelProfile:
    """DeepSeek 深度解答模型 profile（复用远程大模型配置）"""
    from app.config import settings
    return ModelProfile(
        base_url=settings.REMOTE_MODEL_BASE_URL,
        model_name=settings.REMOTE_MODEL_NAME,
        api_key=settings.REMOTE_MODEL_API_KEY,
        timeout=120.0,
    )
