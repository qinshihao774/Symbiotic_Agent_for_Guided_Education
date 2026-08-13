"""GNN 推荐路由"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/recommend")
async def recommend():
    """基于 GNN 的题目推荐"""
    pass


@router.post("/lesson-plan")
async def recommend_lesson_plan():
    """基于 GNN 的教案推荐生成（教师侧）"""
    pass
