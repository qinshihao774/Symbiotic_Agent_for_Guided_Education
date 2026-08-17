"""AI 网关 — 代理转发到 ai/ 服务"""

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.deps import get_current_user

router = APIRouter()


def _ai_headers() -> dict[str, str]:
    """构造转发到 AI 引擎的请求头（含服务间认证 token）"""
    return {"X-Service-Token": settings.AI_SERVICE_TOKEN}


def _inject_user_id(body: dict, current_user: dict) -> dict:
    """将当前登录用户 ID 注入请求体（严格对应登录用户）"""
    body = dict(body)
    body["user_id"] = current_user.get("id")
    return body


@router.post("/chat/quick")
async def chat_quick(request: Request, current_user: dict = Depends(get_current_user)):
    """快速回答 — SSE 透传到 AI 引擎"""
    body = await request.json()
    body = _inject_user_id(body, current_user)

    async def proxy_stream():
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{settings.AI_SERVICE_URL}/rag/query/stream",
                    headers=_ai_headers(),
                    json=body,
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
        except httpx.RemoteProtocolError:
            pass

    return StreamingResponse(
        proxy_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/deep")
async def deep_chat(request: Request, current_user: dict = Depends(get_current_user)):
    """深度解答 — SSE 透传到 AI 引擎（调用 DeepSeek）"""
    body = await request.json()
    body = _inject_user_id(body, current_user)

    async def proxy_stream():
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{settings.AI_SERVICE_URL}/rag/chat/deep/stream",
                    headers=_ai_headers(),
                    json=body,
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
        except httpx.RemoteProtocolError:
            pass

    return StreamingResponse(
        proxy_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/agent/chat")
async def agent_chat(request: Request, current_user: dict = Depends(get_current_user)):
    """智能体模式对话 — SSE 透传到 AI 引擎 Agent 路由"""
    body = await request.json()
    # 注入当前登录用户 ID（严格对应登录用户）
    body = _inject_user_id(body, current_user)

    # Resolve kg_graph_ids → graph_names
    kg_graph_ids: list[int] = body.get("kg_graph_ids", [])
    graph_names: list[str] = []
    if kg_graph_ids:
        from app.core.database import async_session
        from app.services.kg_graph_service import KgGraphService
        kg_service = KgGraphService()
        async with async_session() as db:
            for gid in kg_graph_ids:
                graph = await kg_service.get_graph_by_id(gid, db)
                if graph and graph.graph_name:
                    graph_names.append(graph.graph_name)
    else:
        # 未选教材 → 查询全部图谱
        from app.core.database import async_session
        from app.services.kg_graph_service import KgGraphService
        kg_service = KgGraphService()
        async with async_session() as db:
            all_graphs = await kg_service.list_graphs(db)
            graph_names = [g.graph_name for g in all_graphs]
            kg_graph_ids = [g.id for g in all_graphs]

    body["kg_graph_ids"] = kg_graph_ids
    body["graph_names"] = graph_names

    async def proxy_stream():
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                async with client.stream(
                    "POST",
                    f"{settings.AI_SERVICE_URL}/agent/chat/stream",
                    headers=_ai_headers(),
                    json=body,
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
        except httpx.RemoteProtocolError:
            pass

    return StreamingResponse(
        proxy_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/analysis/stu_analysis")
async def stu_analysis(request: Request):
    """学生 AI 学习分析 — 转发到 ai/ 服务，并将分析结果写入评价分析表"""
    body = await request.json()
    user = getattr(request.state, "user", None)
    stu_id = body.get("stu_id") or (user.get("id") if user else None)
    if not stu_id:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "缺少 stu_id 参数"}, status_code=400)

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.AI_SERVICE_URL}/analysis/stu_analysis",
            headers=_ai_headers(),
            params={"stu_id": stu_id},
        )
        result = resp.json()

    # ── AI 分析完成后写入评价分析表 ──
    # 仅当分析成功（analysis 非空）时才落库
    analysis = result.get("analysis")
    if analysis:
        try:
            import json as _json
            from app.core.database import async_session
            from app.services.evaluation_service import EvaluationAnalysisService

            ea_description = _json.dumps(analysis, ensure_ascii=False)
            async with async_session() as db:
                await EvaluationAnalysisService().upsert_ai_analysis(
                    stu_id=stu_id,
                    ea_description=ea_description,
                    db=db,
                )
        except Exception as e:
            # 落库失败不应阻断分析结果返回，仅记录日志
            import logging
            logging.getLogger(__name__).error(
                f"[AI Gateway] 写入评价分析表失败 stu_id={stu_id}: {e}",
                exc_info=True,
            )

        # ── 同步综合评级到 students.stu_level ──
        # 将 AI 分析得出的综合评级（A/B/C/D/E）写入学生表，并更新 updated_at
        rating = analysis.get("comprehensive_rating")
        if rating:
            try:
                from sqlalchemy import select
                from app.core.database import async_session
                from app.models.user import Student

                async with async_session() as db:
                    stu_result = await db.execute(
                        select(Student).where(Student.stu_id == stu_id)
                    )
                    student = stu_result.scalar_one_or_none()
                    if student is not None:
                        student.stu_level = rating
                        # updated_at 由 onupdate=func.now() 自动更新为当前时间
                        await db.commit()
            except Exception as e:
                # 更新评级失败不应阻断分析结果返回，仅记录日志
                import logging
                logging.getLogger(__name__).error(
                    f"[AI Gateway] 更新学生评级失败 stu_id={stu_id}: {e}",
                    exc_info=True,
                )

    return result


@router.post("/analysis/learning_plan")
async def learning_plan(request: Request):
    """学习规划 — 转发到 ai/ 服务（按学科分别制定）"""
    body = await request.json()
    user = getattr(request.state, "user", None)
    stu_id = body.get("stu_id") or (user.get("id") if user else None)
    if not stu_id:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "缺少 stu_id 参数"}, status_code=400)

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{settings.AI_SERVICE_URL}/analysis/learning_plan",
            headers=_ai_headers(),
            params={"stu_id": stu_id},
        )
        return resp.json()


@router.post("/analysis/question")
async def question_analysis(request: Request):
    """AI 题目分析与解惑 — 转发到 ai/ 服务（双维度：题目答案深度剖析 + 知识图谱局部网络视角 + 个性化作答剖析）"""
    body = await request.json()
    question_id = body.get("question_id")
    if not question_id:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "缺少 question_id 参数"}, status_code=400)

    # 学生提交的答案（do_stu_answer）与学生 ID（stu_id），用于个性化作答剖析
    do_stu_answer = body.get("do_stu_answer")
    stu_id = body.get("stu_id")

    # 仅当 stu_id 有值时传入，避免 None 被序列化为空字符串导致 AI 服务 422
    params = {"question_id": question_id}
    if do_stu_answer:
        params["do_stu_answer"] = do_stu_answer
    if stu_id:
        params["stu_id"] = stu_id

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.AI_SERVICE_URL}/analysis/question",
            headers=_ai_headers(),
            params=params,
        )
        return resp.json()


@router.post("/recommend")
async def recommend_questions():
    """GNN 题目推荐 — 转发到 ai/ 服务"""
    pass


# ═══════════════════════════════════════════════════════════════
# AI 助学对话记忆 — 代理转发到 ai/ 服务
# 所有接口均使用当前登录用户 ID（stu_id），严格对应登录学生，
# 登录用户只能遍历到自己的历史对话。
# ═══════════════════════════════════════════════════════════════


@router.post("/conversations")
async def create_conversation(request: Request, current_user: dict = Depends(get_current_user)):
    """创建一条对话记录（标题由 AI 总结首次对话内容生成）"""
    body = await request.json()
    body["stu_id"] = current_user.get("id")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.AI_SERVICE_URL}/conversation/conversations",
            headers=_ai_headers(),
            json=body,
        )
        return resp.json()


@router.get("/conversations")
async def list_conversations(current_user: dict = Depends(get_current_user)):
    """列出当前登录学生的全部对话"""
    stu_id = current_user.get("id")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{settings.AI_SERVICE_URL}/conversation/conversations",
            headers=_ai_headers(),
            params={"stu_id": stu_id},
        )
        return resp.json()


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: int, current_user: dict = Depends(get_current_user)):
    """获取当前登录学生的单条对话详情"""
    stu_id = current_user.get("id")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{settings.AI_SERVICE_URL}/conversation/conversations/{conversation_id}",
            headers=_ai_headers(),
            params={"stu_id": stu_id},
        )
        return resp.json()


@router.put("/conversations/{conversation_id}")
async def update_conversation(conversation_id: int, request: Request, current_user: dict = Depends(get_current_user)):
    """更新当前登录学生的对话内容"""
    body = await request.json()
    body["stu_id"] = current_user.get("id")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.put(
            f"{settings.AI_SERVICE_URL}/conversation/conversations/{conversation_id}",
            headers=_ai_headers(),
            json=body,
        )
        return resp.json()


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, current_user: dict = Depends(get_current_user)):
    """删除当前登录学生的对话"""
    stu_id = current_user.get("id")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.delete(
            f"{settings.AI_SERVICE_URL}/conversation/conversations/{conversation_id}",
            headers=_ai_headers(),
            params={"stu_id": stu_id},
        )
        return resp.json()
