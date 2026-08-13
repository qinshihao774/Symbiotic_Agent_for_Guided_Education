"""每日用户画像更新任务"""

from app.tasks.registry import scheduled_task


@scheduled_task("daily_profile", trigger="cron", hour=4, minute=0)
async def update_student_profiles():
    """每天凌晨 4:00 更新所有学生的知识掌握画像"""
    # TODO:
    # 1. 从 backend 拉取学生列表和近期做题记录
    # 2. 基于 GNN 或统计方法更新知识掌握度
    # 3. 将结果写回 backend
    pass
