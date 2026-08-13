"""AI 对话请求/响应模型"""

from pydantic import BaseModel


class QuickChatRequest(BaseModel):
    """快速回答请求"""
    message: str
    history: list[dict] = []  # 多轮对话历史


class DeepChatRequest(BaseModel):
    """深度解答请求"""
    question: str
    history: list[dict] = []  # 多轮对话历史


class RAGQueryRequest(BaseModel):
    question: str
    mode: str = "deep"  # "quick" | "deep"


class RAGQueryResponse(BaseModel):
    answer: str
    sources: list[dict]  # 引用来源
    confidence: float
