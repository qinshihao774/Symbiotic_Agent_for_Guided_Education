"""BGE-Reranker-v2-M3 重排序客户端 — vLLM :8011 POST /v1/score

API 格式（已实际验证）:
    POST /v1/score
    {"model": "/home/ll_yqs2/models/bge-reranker-v2-m3",
     "text_1": "query",
     "text_2": ["candidate1", "candidate2"]}
    → {"data": [{"index": 0, "score": 0.48}, {"index": 1, "score": 0.71}]}
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

RERANKER_MODEL = "/home/ll_yqs2/models/bge-reranker-v2-m3"


class RerankerClient:
    """BGE-Reranker 重排序客户端

    用法:
        client = RerankerClient()
        pairs = [("什么是栈", "栈的定义..."), ("什么是栈", "队列的定义...")]
        scores = await client.rerank(pairs)
        # scores = [0.48, 0.71]
    """

    def __init__(
        self,
        base_url: str = "",
        endpoint: str = "",
    ):
        self._base_url = (base_url or settings.BGE_RERANKER_URL).rstrip("/")
        self._endpoint = endpoint or "/v1/score"

    async def rerank_with_retry(
        self, pairs: list[tuple[str, str]], top_k: int | None = None, retries: int = 2,
    ) -> list[float]:
        """带重试的重排序"""
        for attempt in range(retries + 1):
            try:
                return await self.rerank(pairs, top_k=top_k)
            except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt == retries:
                    raise
                logger.warning("Reranker attempt %d/%d failed: %s", attempt + 1, retries + 1, e)
        raise RuntimeError("unreachable")

    async def rerank(
        self,
        pairs: list[tuple[str, str]],
        top_k: int | None = None,
    ) -> list[float]:
        """对 (query, candidate) 对进行重排序打分

        Args:
            pairs: (query, candidate_text) 列表
            top_k: 可选，只保留前 top_k 个分数，其余置 -inf

        Returns:
            分数列表（与输入顺序一致）
        """
        if not pairs:
            return []

        # 将 (query, candidate) 列表转换为 /v1/score 的请求格式
        queries = [p[0] for p in pairs]
        candidates = [p[1] for p in pairs]
        # 如果所有 query 相同（通常只有一个 query 对多个 candidate），简化请求
        if len(set(queries)) == 1:
            request_body = {
                "model": RERANKER_MODEL,
                "text_1": queries[0],
                "text_2": candidates,
            }
        else:
            # 多个独立评分对，逐个请求（/v1/score 不支持批量不同 query）
            return await self._rerank_separate(pairs, top_k)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}{self._endpoint}",
                json=request_body,
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()

            # /v1/score 返回格式: {"data": [{"index": 0, "score": 0.48}, ...]}
            scores_list = data.get("data", [])
            scores = [0.0] * len(scores_list)
            for entry in scores_list:
                scores[entry["index"]] = entry["score"]

            if top_k is not None and top_k < len(scores):
                indexed = list(enumerate(scores))
                indexed.sort(key=lambda x: x[1], reverse=True)
                keep = {i for i, _ in indexed[:top_k]}
                return [
                    s if i in keep else -float("inf")
                    for i, s in enumerate(scores)
                ]

            return scores

    async def _rerank_separate(
        self, pairs: list[tuple[str, str]], top_k: int | None = None,
    ) -> list[float]:
        """不同 query 对各自打分（逐对请求）"""
        scores = []
        for query, candidate in pairs:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}{self._endpoint}",
                    json={
                        "model": RERANKER_MODEL,
                        "text_1": query,
                        "text_2": [candidate],
                    },
                    timeout=60.0,
                )
                resp.raise_for_status()
                data = resp.json()
                score = data.get("data", [{}])[0].get("score", 0.0)
                scores.append(score)

        if top_k is not None and top_k < len(scores):
            indexed = list(enumerate(scores))
            indexed.sort(key=lambda x: x[1], reverse=True)
            keep = {i for i, _ in indexed[:top_k]}
            return [s if i in keep else -float("inf") for i, s in enumerate(scores)]

        return scores
