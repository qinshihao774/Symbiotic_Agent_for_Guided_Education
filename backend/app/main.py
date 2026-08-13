"""智教慧学 — FastAPI 后端应用入口"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, knowledge, learning, practice, teacher, ai_gateway, ocr_gateway, kg_gateway, interaction
from app.core.config import settings

app = FastAPI(title="ChuMa Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识图谱"])
app.include_router(learning.router, prefix="/api/learning", tags=["学习管理"])
app.include_router(practice.router, prefix="/api/practice", tags=["题目练习"])
app.include_router(teacher.router, prefix="/api/teacher", tags=["教师管理"])
app.include_router(ai_gateway.router, prefix="/api/ai", tags=["AI 网关"])
app.include_router(ocr_gateway.router, prefix="/api/ocr", tags=["OCR 网关"])
app.include_router(kg_gateway.router, prefix="/api/kg", tags=["知识图谱网关"])
app.include_router(interaction.router, prefix="/api/interaction", tags=["互动消息"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}
