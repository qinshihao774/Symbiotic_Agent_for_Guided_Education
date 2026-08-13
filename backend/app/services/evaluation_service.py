"""EvaluationAnalysis 业务逻辑层 — 评价分析管理"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.evaluation_analysis import EvaluationAnalysis


class EvaluationAnalysisService:
    """评价分析服务

    提供 AI 助学建议的写入能力：
    - 若某学生已存在 AI 发布的分析记录，则更新其内容与更新时间
    - 若不存在，则新增一条记录
    """

    # AI 发布者的固定标识
    AI_PUBLISHER_NAME = "AI"

    async def upsert_ai_analysis(
        self,
        stu_id: int,
        ea_description: str,
        db: AsyncSession,
    ) -> EvaluationAnalysis:
        """插入或更新某学生的 AI 助学建议

        规则：
        - 按 stu_id + publisher_name='AI' 定位已有记录
        - 已存在 → 更新 ea_description 与 updated_at
        - 不存在 → 新增记录（publisher_id 为 null，publisher_name 为 "AI"）

        Args:
            stu_id: 学生 ID
            ea_description: AI 分析内容
            db: 数据库会话

        Returns:
            更新或新增后的 EvaluationAnalysis 记录
        """
        result = await db.execute(
            select(EvaluationAnalysis).where(
                EvaluationAnalysis.stu_id == stu_id,
                EvaluationAnalysis.publisher_name == self.AI_PUBLISHER_NAME,
            )
        )
        record = result.scalar_one_or_none()

        if record is None:
            record = EvaluationAnalysis(
                stu_id=stu_id,
                publisher_id=None,
                publisher_name=self.AI_PUBLISHER_NAME,
                ea_description=ea_description,
            )
            db.add(record)
        else:
            record.ea_description = ea_description
            # updated_at 由 onupdate=func.now() 自动更新

        await db.commit()
        await db.refresh(record)
        return record

    async def get_ai_analysis(
        self,
        stu_id: int,
        db: AsyncSession,
    ) -> Optional[EvaluationAnalysis]:
        """查询某学生的 AI 助学建议记录"""
        result = await db.execute(
            select(EvaluationAnalysis).where(
                EvaluationAnalysis.stu_id == stu_id,
                EvaluationAnalysis.publisher_name == self.AI_PUBLISHER_NAME,
            )
        )
        return result.scalar_one_or_none()
