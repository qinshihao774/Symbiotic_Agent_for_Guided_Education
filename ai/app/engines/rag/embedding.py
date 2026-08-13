"""BGE-M3 嵌入客户端 — vLLM :8010 POST /v1/embeddings"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "/home/ll_yqs2/models/bge-m3"
EMBEDDING_DIM = 1024


class EmbeddingClient:
    """BGE-M3 嵌入客户端

    用法:
        client = EmbeddingClient(query_prefix="Represent this sentence for searching: ")
        vec = await client.encode("什么是共享栈")
        vecs = await client.batch_encode(["文本1", "文本2"])
    """

    def __init__(
        self,
        base_url: str = "",
        query_prefix: str = "",
    ):
        self._base_url = (base_url or settings.BGE_M3_URL).rstrip("/")
        self._query_prefix = query_prefix

    async def encode(self, text: str) -> list[float]:
        """单条文本 → 1024 维向量"""
        input_text = f"{self._query_prefix}{text}" if self._query_prefix else text
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/v1/embeddings",
                json={"model": EMBEDDING_MODEL, "input": input_text},
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]

    async def batch_encode(self, texts: list[str]) -> list[list[float]]:
        """批量文本 → 向量列表（顺序与输入一致）"""
        if self._query_prefix:
            texts = [f"{self._query_prefix}{t}" for t in texts]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/v1/embeddings",
                json={"model": EMBEDDING_MODEL, "input": texts},
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            return [item["embedding"] for item in data]

    async def encode_with_retry(
        self, text: str, retries: int = 2
    ) -> list[float]:
        """带重试的单条编码"""
        for attempt in range(retries + 1):
            try:
                return await self.encode(text)
            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt == retries:
                    raise
                logger.warning(
                    "Embedding attempt %d/%d failed: %s",
                    attempt + 1, retries + 1, e,
                )
        raise RuntimeError("unreachable")
