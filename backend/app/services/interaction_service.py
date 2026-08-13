"""互动消息业务逻辑层 — 消息发布、分页查询、回答发布与查询"""
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.interaction import InteractionMessage, InteractionAnswer
from app.models.user import Student, Teacher
from app.schemas.interaction import (
    InteractionMessageCreate,
    InteractionMessageResponse,
    InteractionMessageListResponse,
    InteractionAnswerCreate,
    InteractionAnswerResponse,
)


class InteractionService:
    async def create_message(
        self, stu_id: int, data: InteractionMessageCreate, db: AsyncSession
    ) -> InteractionMessageResponse:
        """学生发布一条互动消息"""
        message = InteractionMessage(
            msg_texts=data.msg_texts,
            stu_id=stu_id,
            answer_num=0,
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)
        # 查询发布者姓名
        stu_name = await self._get_student_name(stu_id, db)
        return InteractionMessageResponse(
            msg_id=message.msg_id,
            msg_texts=message.msg_texts,
            stu_id=message.stu_id,
            stu_name=stu_name,
            answer_num=message.answer_num or 0,
            created_at=message.created_at,
        )

    async def list_messages(
        self, db: AsyncSession, page: int = 1, page_size: int = 10
    ) -> InteractionMessageListResponse:
        """分页查询互动消息列表（按时间倒序），并附带发布者姓名"""
        # 总数
        total_result = await db.execute(select(func.count()).select_from(InteractionMessage))
        total = total_result.scalar() or 0

        # 分页数据
        result = await db.execute(
            select(InteractionMessage, Student.stu_name)
            .join(Student, InteractionMessage.stu_id == Student.stu_id, isouter=True)
            .order_by(InteractionMessage.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = result.all()
        items = []
        for message, stu_name in rows:
            items.append(
                InteractionMessageResponse(
                    msg_id=message.msg_id,
                    msg_texts=message.msg_texts,
                    stu_id=message.stu_id,
                    stu_name=stu_name,
                    answer_num=message.answer_num or 0,
                    created_at=message.created_at,
                )
            )
        return InteractionMessageListResponse(total=total, items=items)

    async def get_message_detail(
        self, msg_id: int, db: AsyncSession
    ) -> Optional[InteractionMessageResponse]:
        """查询单条互动消息详情（含发布者姓名）"""
        result = await db.execute(
            select(InteractionMessage, Student.stu_name)
            .join(Student, InteractionMessage.stu_id == Student.stu_id, isouter=True)
            .where(InteractionMessage.msg_id == msg_id)
        )
        row = result.first()
        if row is None:
            return None
        message, stu_name = row
        return InteractionMessageResponse(
            msg_id=message.msg_id,
            msg_texts=message.msg_texts,
            stu_id=message.stu_id,
            stu_name=stu_name,
            answer_num=message.answer_num or 0,
            created_at=message.created_at,
        )

    async def create_answer(
        self, msg_id: int, answer_text: str, stu_id: Optional[int], tea_id: Optional[int], db: AsyncSession
    ) -> InteractionAnswerResponse:
        """发布一条回答（学生或老师），并同步更新消息的回答数"""
        # 校验消息存在
        msg_result = await db.execute(
            select(InteractionMessage).where(InteractionMessage.msg_id == msg_id)
        )
        message = msg_result.scalar_one_or_none()
        if message is None:
            raise ValueError(f"互动消息不存在: msg_id={msg_id}")

        answer = InteractionAnswer(
            answer_text=answer_text,
            msg_id=msg_id,
            stu_id=stu_id,
            tea_id=tea_id,
        )
        db.add(answer)
        # 回答数 +1
        message.answer_num = (message.answer_num or 0) + 1
        await db.commit()
        await db.refresh(answer)

        author_name, author_type = await self._get_author_name(stu_id, tea_id, db)
        return InteractionAnswerResponse(
            answer_id=answer.answer_id,
            answer_text=answer.answer_text,
            msg_id=answer.msg_id,
            stu_id=answer.stu_id,
            tea_id=answer.tea_id,
            author_name=author_name,
            author_type=author_type,
            created_at=answer.created_at,
        )

    async def list_answers(
        self, msg_id: int, db: AsyncSession
    ) -> list[InteractionAnswerResponse]:
        """查询某条消息下的所有回答（按时间正序）"""
        result = await db.execute(
            select(InteractionAnswer)
            .where(InteractionAnswer.msg_id == msg_id)
            .order_by(InteractionAnswer.created_at.asc())
        )
        answers = result.scalars().all()
        items = []
        for answer in answers:
            author_name, author_type = await self._get_author_name(
                answer.stu_id, answer.tea_id, db
            )
            items.append(
                InteractionAnswerResponse(
                    answer_id=answer.answer_id,
                    answer_text=answer.answer_text,
                    msg_id=answer.msg_id,
                    stu_id=answer.stu_id,
                    tea_id=answer.tea_id,
                    author_name=author_name,
                    author_type=author_type,
                    created_at=answer.created_at,
                )
            )
        return items

    async def _get_student_name(self, stu_id: int, db: AsyncSession) -> Optional[str]:
        result = await db.execute(select(Student.stu_name).where(Student.stu_id == stu_id))
        return result.scalar_one_or_none()

    async def _get_author_name(
        self, stu_id: Optional[int], tea_id: Optional[int], db: AsyncSession
    ) -> tuple[Optional[str], Optional[str]]:
        """根据 stu_id / tea_id 返回回答者姓名与身份类型"""
        if stu_id is not None:
            name = await self._get_student_name(stu_id, db)
            return name, "student"
        if tea_id is not None:
            result = await db.execute(select(Teacher.tea_name).where(Teacher.tea_id == tea_id))
            name = result.scalar_one_or_none()
            return name, "teacher"
        return None, None
