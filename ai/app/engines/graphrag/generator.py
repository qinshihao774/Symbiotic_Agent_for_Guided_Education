"""生成模块 — 基于检索结果调用大模型生成回答"""

from app.engines.llm.client import LLMClient
from app.engines.llm.profiles import remote_profile


class RAGGenerator:
    """GraphRAG 生成器：检索结果 + 提示词 → 带来源标注的回答

    默认使用远程大模型（深度解答场景）。
    调用方通过注入 LLMClient 即可控制模型选择。
    """

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm = llm_client or LLMClient(default_profile=remote_profile())

    def generate(self, query: str, context: list[dict]) -> dict:
        """生成带来源引用的回答"""
        pass
