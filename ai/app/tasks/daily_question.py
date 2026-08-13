"""每日一题生成任务"""

from app.tasks.registry import scheduled_task


@scheduled_task("daily_question", trigger="cron", hour=4, minute=30)
async def generate_daily_questions():
    """每天凌晨 4:30 为学生生成个性化每日一题"""
    # TODO:
    # 1. 从 backend 拉取学生薄弱知识点
    # 2. 从题库中选择匹配题目，或用 LLM 生成新题
    # 3. 推送到 backend
    pass
