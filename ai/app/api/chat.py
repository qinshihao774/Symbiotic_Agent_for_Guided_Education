"""AI 对话路由 — 快速回答与深度解答"""

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.engines.llm.client import LLMClient
from app.engines.llm.profiles import deepseek_profile, quick_profile
from app.schemas.chat import DeepChatRequest, QuickChatRequest

router = APIRouter()


@router.post("/query")
async def rag_query():
    """GraphRAG 增强问答 — 检索知识图谱 + 远程大模型生成"""
    pass


@router.post("/query/stream")
async def quick_chat_stream(req: QuickChatRequest):
    """快速回答 — 流式输出（纯 LLM，不走 RAG）"""
    # llm = LLMClient(default_profile=quick_profile())
    llm = LLMClient(default_profile=deepseek_profile())

    messages = [
        {"role": "system", "content": "你是智教慧学，一个计算机科学学习智能助教，擅长408考研和数据库原理相关知识。请用简洁准确的中文回答用户的问题。"},
        *req.history,
        {"role": "user", "content": req.message},
    ]

    async def event_stream():
        async for chunk in llm.stream(messages):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/deep/stream")
async def deep_chat_stream(req: DeepChatRequest):
    """深度解答 — 流式输出（调用 DeepSeek）"""
    llm = LLMClient(default_profile=deepseek_profile())

    messages = [
        {"role": "system", "content": "你是智教慧学，一个计算机科学学习智能助教，擅长408考研和数据库原理相关知识。请用深入、详细、结构化的中文回答用户的问题，必要时可以分点说明。"},
        *req.history,
        {"role": "user", "content": req.question},
    ]

    async def event_stream():
        async for chunk in llm.stream(messages):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
