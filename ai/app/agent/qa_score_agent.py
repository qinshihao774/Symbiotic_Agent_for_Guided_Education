"""AI 简答题（Q_A）评分 Agent

根据题目题干、标准答案与学生回答，由大模型酌情给分（满分 10 分，float）。

===== 输出格式 =====

{
    "score": float,   # 0.0 ~ 10.0
    "reason": str      # 评分理由（简要）
}
"""
import json
import logging
from typing import Any

from app.engines.llm.client import LLMClient
from app.engines.llm.profiles import deepseek_profile

logger = logging.getLogger(__name__)


# ── 评分系统提示词 ─────────────────────────────────────────────
QA_SCORE_SYSTEM_PROMPT = """你是一位资深的 408 考研辅导老师，负责对学生的简答题作答进行评分。

## 评分规则

1. 以题目标准答案（question_answer）为评分基准，结合题目题干（question_description）考察的知识点。
2. 对比学生回答（stu_answer）与标准答案的契合程度，从以下维度酌情给分（满分 10 分）：
   - 知识点覆盖是否完整；
   - 关键要点是否答出；
   - 表述是否准确、逻辑是否清晰；
   - 是否存在明显错误或遗漏。
3. 评分必须客观、实事求是，只能基于给定的题目与答案数据，不得臆造。
4. 分数为 0.0 ~ 10.0 之间的浮点数，保留两位小数。

## 输出格式

只输出一行纯 JSON，不要包含任何其他内容、解释或 markdown 标记：
{"score": 8.5, "reason": "简要说明评分理由"}"""


class QaScoreAgent:
    """AI 简答题评分 Agent"""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    async def score(
        self,
        question_description: str,
        question_answer: str,
        stu_answer: str,
    ) -> dict[str, Any]:
        """对简答题作答进行评分

        Args:
            question_description: 题目题干
            question_answer: 标准答案
            stu_answer: 学生回答

        Returns:
            {"score": float, "reason": str}；解析失败时 score 为 0.0
        """
        user_prompt = f"""请对以下简答题作答进行评分。

## 题目题干

{question_description}

## 标准答案

{question_answer}

## 学生回答

{stu_answer}

请根据评分规则，给出 0.0 ~ 10.0 的分数并简要说明理由。"""

        messages: list[dict] = [
            {"role": "system", "content": QA_SCORE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self.llm.chat(
                messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            if response.content:
                parsed = self._parse_score_json(response.content)
                score = float(parsed.get("score", 0.0))
                # 限制在 0~10 分范围内
                score = max(0.0, min(10.0, round(score, 2)))
                return {
                    "score": score,
                    "reason": str(parsed.get("reason", "")),
                }
        except Exception as e:
            logger.error(
                f"[QaScoreAgent] 评分生成异常: {e}",
                exc_info=True,
            )

        return {"score": 0.0, "reason": "评分失败，默认 0 分"}

    @staticmethod
    def _parse_score_json(text: str) -> dict[str, Any]:
        """解析 LLM 输出的评分 JSON，带多层容错处理"""
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        if "```json" in text:
            try:
                return json.loads(text.split("```json")[1].split("```")[0].strip())
            except (json.JSONDecodeError, IndexError):
                pass

        if "```" in text:
            try:
                return json.loads(text.split("```")[1].split("```")[0].strip())
            except (json.JSONDecodeError, IndexError):
                pass

        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(text[first_brace:last_brace + 1])
            except json.JSONDecodeError:
                pass

        logger.warning(
            f"[QaScoreAgent] 无法解析 LLM 输出为 JSON: {text[:200]}..."
        )
        return {"score": 0.0, "reason": "解析失败"}


# 便捷函数
async def score_qa(
    question_description: str,
    question_answer: str,
    stu_answer: str,
) -> dict[str, Any]:
    """对简答题作答进行评分（便捷函数）

    Args:
        question_description: 题目题干
        question_answer: 标准答案
        stu_answer: 学生回答

    Returns:
        {"score": float, "reason": str}
    """
    llm = LLMClient(default_profile=deepseek_profile())
    agent = QaScoreAgent(llm_client=llm)
    return await agent.score(
        question_description,
        question_answer,
        stu_answer,
    )
