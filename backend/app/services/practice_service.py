"""Practice 业务逻辑层 — 题库与做题记录"""
import logging
from typing import Optional
from sqlalchemy import select, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.question import Question
from app.models.exercise_record import ExerciseRecord
from app.models.course import Course
from app.schemas.practice import (
    QuestionCreate,
    QuestionResponse,
    ExerciseRecordCreate,
    ExerciseRecordResponse,
    ExerciseRecordListResponse,
)

logger = logging.getLogger(__name__)

OBJECTIVE_TYPES = {"single_choice", "multiple_choice", "T_or_F", "choice", "true_false"}
FILL_TYPES = {"Fill_blanks", "fill_Blanks", "fill_blanks"}
QA_TYPES = {"Q_A", "q_a"}
PASS_SCORE = 6.0


class PracticeService:
    async def create_question(self, data: QuestionCreate, db: AsyncSession) -> QuestionResponse:
        kg_id = await self._get_course_kg_id(data.course_id, db)
        question = Question(
            question_description=data.question_description,
            question_answer=data.question_answer,
            question_options=data.question_options,
            question_type=data.question_type,
            question_difficulty=data.question_difficulty,
            question_explanation=data.question_explanation,
            course_id=data.course_id,
            kg_id=kg_id,
            kg_node_name=data.kg_node_name,
        )
        db.add(question)
        await db.commit()
        await db.refresh(question)
        return QuestionResponse.model_validate(question)

    async def list_questions(
        self,
        db: AsyncSession,
        course_id: Optional[int] = None,
        kg_node_name: Optional[str] = None,
        difficulty: Optional[int] = None,
    ) -> list[QuestionResponse]:
        query = select(Question)
        if course_id is not None:
            query = query.where(Question.course_id == course_id)
        if kg_node_name is not None:
            query = query.where(Question.kg_node_name == kg_node_name)
        if difficulty is not None:
            query = query.where(Question.question_difficulty == difficulty)
        result = await db.execute(query.order_by(Question.question_id))
        questions = result.scalars().all()
        return [QuestionResponse.model_validate(q) for q in questions]

    async def get_question_by_id(self, question_id: int, db: AsyncSession) -> Optional[QuestionResponse]:
        result = await db.execute(select(Question).where(Question.question_id == question_id))
        question = result.scalar_one_or_none()
        if question is None:
            return None
        return QuestionResponse.model_validate(question)

    async def submit_exercise(
        self, stu_id: int, data: ExerciseRecordCreate, db: AsyncSession
    ) -> ExerciseRecordResponse:
        """提交答案并存入 exercise_records，根据题目类型处理 do_score / do_isTrue / iserror_firstly。

        规则（依据 questions.question_type）：
        - single_choice / multiple_choice / T_or_F：do_isTrue 生效（比较答案），do_score 置 null；
        - Fill_blanks：do_score 按空给分（满分/填空总数 × 填对数量），do_isTrue 置 null；
        - Q_A：do_score 由大模型根据题目答案对比学生回答酌情给分（满分 10 分，float），do_isTrue 置 null。

        iserror_firstly（首次作答是否错误）采用历史首次判定：
        - 客观题：首次作答做错为 true；
        - 主观题（Fill_blanks / Q_A）：首次作答得分低于 6 分为 true。
        若该题此前已做过，则保留首次作答时的判定结果，不因本次重做而改变。

        kg_id / kg_node_name 一律从 questions 表继承，不依赖前端传参。
        """
        # 从数据库查询题目信息，获取正确答案与知识点归属
        question_result = await db.execute(
            select(Question).where(Question.question_id == data.question_id)
        )
        question = question_result.scalar_one_or_none()
        if question is None:
            raise ValueError(f"题目不存在: question_id={data.question_id}")

        # 做题记录中的归属信息一律以题库为准，避免前端传参污染闭环。
        course_id = question.course_id
        kg_id = question.kg_id or await self._get_course_kg_id(course_id, db)
        kg_node_name = question.kg_node_name
        question_type = question.question_type
        question_difficulty = question.question_difficulty

        do_isTrue = None
        do_score = None

        if question_type in OBJECTIVE_TYPES:
            # 客观题：比较学生答案与正确答案，do_isTrue 生效，do_score 置 null
            do_isTrue = self._answers_equal(question.question_answer, data.do_stu_answer, question_type)
            do_score = None
        elif question_type in FILL_TYPES:
            # 填空题：按空给分，do_score 生效，do_isTrue 置 null
            do_score = self._score_fill_blanks(
                question.question_answer, data.do_stu_answer
            )
            do_isTrue = None
        elif question_type in QA_TYPES:
            # 简答题：大模型评分，do_score 生效，do_isTrue 置 null
            do_score = await self._score_qa(
                question.question_description,
                question.question_answer,
                data.do_stu_answer,
            )
            do_isTrue = None
        else:
            raise ValueError(f"不支持的题目类型: {question_type}")

        # 检查是否已存在相同 question_id + stu_id 的记录
        existing_result = await db.execute(
            select(ExerciseRecord).where(
                ExerciseRecord.question_id == data.question_id,
                ExerciseRecord.stu_id == stu_id,
            )
        )
        existing_record = existing_result.scalar_one_or_none()

        if existing_record:
            # 已存在则更新作答内容和判定结果，但保留首次作答的 iserror_firstly
            existing_record.do_stu_answer = data.do_stu_answer
            existing_record.do_isTrue = do_isTrue
            existing_record.do_score = do_score
            existing_record.kg_id = kg_id
            existing_record.kg_node_name = kg_node_name
            existing_record.course_id = course_id
            existing_record.question_type = question_type
            existing_record.question_difficulty = question_difficulty
            await db.commit()
            await db.refresh(existing_record)
            # 更新知识点掌握度（做题闭环）
            await self._update_mastery(
                stu_id=stu_id,
                course_id=course_id,
                kg_id=kg_id,
                kg_node_name=kg_node_name,
                question_type=question_type,
                do_score=do_score,
                do_isTrue=do_isTrue,
                db=db,
            )
            return ExerciseRecordResponse.model_validate(existing_record)
        else:
            # 不存在则创建新记录，本次即首次作答，判定 iserror_firstly
            iserror_firstly = self._judge_first_error(
                question_type, do_isTrue, do_score
            )
            record = ExerciseRecord(
                question_id=data.question_id,
                stu_id=stu_id,
                kg_id=kg_id,
                course_id=course_id,
                kg_node_name=kg_node_name,
                question_type=question_type,
                question_difficulty=question_difficulty,
                do_stu_answer=data.do_stu_answer,
                do_score=do_score,
                do_isTrue=do_isTrue,
                iserror_firstly=iserror_firstly,
            )
            db.add(record)
            await db.commit()
            await db.refresh(record)
            # 更新知识点掌握度（做题闭环）
            await self._update_mastery(
                stu_id=stu_id,
                course_id=course_id,
                kg_id=kg_id,
                kg_node_name=kg_node_name,
                question_type=question_type,
                do_score=do_score,
                do_isTrue=do_isTrue,
                db=db,
            )
            return ExerciseRecordResponse.model_validate(record)

    async def _update_mastery(
        self,
        stu_id: int,
        course_id: int,
        kg_id: int | None,
        kg_node_name: str | None,
        question_type: str,
        do_score: float | None,
        do_isTrue: bool | None,
        db: AsyncSession,
    ) -> None:
        """做题提交后更新学生知识点掌握度（闭环：做题→知识点→小节→章节→学科）。

        掌握度更新失败不应阻断做题提交，仅记录日志。
        """
        try:
            from app.services.mastery_service import MasteryService
            await MasteryService().update_knowledge_mastery(
                stu_id=stu_id,
                course_id=course_id,
                kg_id=kg_id,
                kg_node_name=kg_node_name,
                question_type=question_type,
                do_score=do_score,
                do_isTrue=do_isTrue,
                db=db,
            )
        except Exception as e:
            logger.error(
                f"[PracticeService] 更新知识点掌握度失败 stu_id={stu_id} "
                f"kg_node_name={kg_node_name}: {e}",
                exc_info=True,
            )

    async def _get_course_kg_id(self, course_id: int, db: AsyncSession) -> int | None:
        result = await db.execute(select(Course.kg_id).where(Course.course_id == course_id))
        return result.scalar_one_or_none()

    @classmethod
    def _answers_equal(cls, standard_answer: str, stu_answer: str, question_type: str) -> bool:
        if question_type == "multiple_choice":
            return (
                cls._normalize_choice_answer(standard_answer, split_chars=True)
                == cls._normalize_choice_answer(stu_answer, split_chars=True)
            )
        return standard_answer.strip().casefold() == stu_answer.strip().casefold()

    @staticmethod
    def _normalize_choice_answer(answer: str, split_chars: bool = False) -> tuple[str, ...]:
        cleaned = (
            answer.replace("，", ",")
            .replace("、", ",")
            .replace("；", ",")
            .replace(";", ",")
            .replace("|", ",")
            .replace(" ", "")
        )
        if "," in cleaned:
            parts = [part.strip().casefold() for part in cleaned.split(",") if part.strip()]
        elif split_chars:
            parts = [ch.casefold() for ch in cleaned if ch.strip()]
        else:
            parts = [cleaned.casefold()] if cleaned else []
        return tuple(sorted(parts))

    @staticmethod
    def _score_fill_blanks(question_answer: str, stu_answer: str) -> float:
        """填空题按空给分：得分 =（满分 10 / 填空总数）× 填对数量。

        约定：question_answer 与 do_stu_answer 均用英文逗号 "," 分隔多个空，
        逐空去除首尾空白后比对。
        """
        full_score = 10.0
        blanks = [b.strip() for b in question_answer.split(",") if b.strip()]
        if not blanks:
            # 无空位可判，视为满分
            return full_score
        stu_blanks = [b.strip() for b in stu_answer.split(",")]
        correct = 0
        for i, blank in enumerate(blanks):
            if i < len(stu_blanks) and stu_blanks[i] == blank:
                correct += 1
        return round(full_score / len(blanks) * correct, 2)

    async def _score_qa(
        self, question_description: str, question_answer: str, stu_answer: str
    ) -> float:
        """简答题大模型评分：根据题目答案对比学生回答酌情给分（满分 10 分，float）。

        调用 AI 服务评分接口；若 AI 服务不可用，则降级为 0 分并记录日志。
        """
        try:
            import httpx
            from app.core.config import settings

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{settings.AI_SERVICE_URL}/analysis/qa_score",
                    headers={"X-Service-Token": settings.AI_SERVICE_TOKEN},
                    json={
                        "question_description": question_description,
                        "question_answer": question_answer,
                        "stu_answer": stu_answer,
                    },
                )
                resp.raise_for_status()
                result = resp.json()
                score = float(result.get("score", 0.0))
                # 限制在 0~10 分范围内
                return max(0.0, min(10.0, round(score, 2)))
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(
                f"[PracticeService] Q_A 大模型评分失败，降级为 0 分: {e}",
                exc_info=True,
            )
            return 0.0

    @staticmethod
    def _judge_first_error(
        question_type: str, do_isTrue: bool | None, do_score: float | None
    ) -> bool:
        """判定首次作答是否错误。

        - 客观题：do_isTrue 为 False 即首次做错；
        - 主观题（Fill_blanks / Q_A）：得分低于 6 分为首次做错。
        """
        objective_types = {"single_choice", "multiple_choice", "T_or_F", "choice", "true_false"}
        if question_type in objective_types:
            return do_isTrue is False
        # 主观题：得分低于 6 分为错
        return do_score is not None and do_score < 6.0

    async def get_student_exercise_records(
        self, stu_id: int, db: AsyncSession
    ) -> list[ExerciseRecordListResponse]:
        """获取当前学生的所有做题记录（含题目题干和学科名称），按时间倒序"""
        result = await db.execute(
            select(ExerciseRecord, Question.question_description, Course.course_name)
            .join(Question, ExerciseRecord.question_id == Question.question_id)
            .join(Course, ExerciseRecord.course_id == Course.course_id, isouter=True)
            .where(ExerciseRecord.stu_id == stu_id)
            .order_by(ExerciseRecord.created_at.desc())
        )
        rows = result.all()
        records = []
        for record, question_description, course_name in rows:
            records.append(
                ExerciseRecordListResponse(
                    do_id=record.do_id,
                    question_id=record.question_id,
                    question_description=question_description,
                    course_name=course_name,
                    question_type=record.question_type,
                    question_difficulty=record.question_difficulty,
                    do_stu_answer=record.do_stu_answer,
                    do_score=record.do_score,
                    do_isTrue=record.do_isTrue,
                    kg_node_name=record.kg_node_name,
                    created_at=record.created_at,
                )
            )
        return records

    async def get_student_exercise_records_by_course(
        self, stu_id: int, course_id: int, db: AsyncSession
    ) -> list[ExerciseRecordListResponse]:
        """获取当前学生在指定学科下的做题记录"""
        result = await db.execute(
            select(ExerciseRecord, Question.question_description, Course.course_name)
            .join(Question, ExerciseRecord.question_id == Question.question_id)
            .join(Course, ExerciseRecord.course_id == Course.course_id, isouter=True)
            .where(
                and_(
                    ExerciseRecord.stu_id == stu_id,
                    ExerciseRecord.course_id == course_id,
                )
            )
            .order_by(ExerciseRecord.created_at.desc())
        )
        rows = result.all()
        records = []
        for record, question_description, course_name in rows:
            records.append(
                ExerciseRecordListResponse(
                    do_id=record.do_id,
                    question_id=record.question_id,
                    question_description=question_description,
                    course_name=course_name,
                    question_type=record.question_type,
                    question_difficulty=record.question_difficulty,
                    do_stu_answer=record.do_stu_answer,
                    do_score=record.do_score,
                    do_isTrue=record.do_isTrue,
                    kg_node_name=record.kg_node_name,
                    created_at=record.created_at,
                )
            )
        return records

    async def get_student_wrong_records_by_course(
        self, stu_id: int, course_id: int, db: AsyncSession
    ) -> list[ExerciseRecordListResponse]:
        """获取当前学生在指定学科下的错题记录（仅 do_isTrue=False）"""
        result = await db.execute(
            select(ExerciseRecord, Question.question_description, Course.course_name)
            .join(Question, ExerciseRecord.question_id == Question.question_id)
            .join(Course, ExerciseRecord.course_id == Course.course_id, isouter=True)
            .where(
                and_(
                    ExerciseRecord.stu_id == stu_id,
                    ExerciseRecord.course_id == course_id,
                    self._wrong_record_condition(),
                )
            )
            .order_by(ExerciseRecord.created_at.desc())
        )
        rows = result.all()
        records = []
        for record, question_description, course_name in rows:
            records.append(
                ExerciseRecordListResponse(
                    do_id=record.do_id,
                    question_id=record.question_id,
                    question_description=question_description,
                    course_name=course_name,
                    question_type=record.question_type,
                    question_difficulty=record.question_difficulty,
                    do_stu_answer=record.do_stu_answer,
                    do_score=record.do_score,
                    do_isTrue=record.do_isTrue,
                    kg_node_name=record.kg_node_name,
                    created_at=record.created_at,
                )
            )
        return records

    async def get_student_wrong_records_grouped(
        self, stu_id: int, db: AsyncSession
    ) -> dict:
        """获取当前学生所有错题，按 course_id 分组。

        返回格式：{ course_id: { course_name, records: [...] } }
        """
        result = await db.execute(
            select(ExerciseRecord, Question.question_description, Course.course_name)
            .join(Question, ExerciseRecord.question_id == Question.question_id)
            .join(Course, ExerciseRecord.course_id == Course.course_id, isouter=True)
            .where(
                and_(
                    ExerciseRecord.stu_id == stu_id,
                    self._wrong_record_condition(),
                )
            )
            .order_by(ExerciseRecord.created_at.desc())
        )
        rows = result.all()
        grouped: dict = {}
        for record, question_description, course_name in rows:
            cid = record.course_id
            if cid not in grouped:
                grouped[cid] = {
                    "course_name": course_name or f"学科{cid}",
                    "records": [],
                }
            grouped[cid]["records"].append(
                ExerciseRecordListResponse(
                    do_id=record.do_id,
                    question_id=record.question_id,
                    question_description=question_description,
                    course_name=course_name,
                    question_type=record.question_type,
                    question_difficulty=record.question_difficulty,
                    do_stu_answer=record.do_stu_answer,
                    do_score=record.do_score,
                    do_isTrue=record.do_isTrue,
                    kg_node_name=record.kg_node_name,
                    created_at=record.created_at,
                )
            )
        return grouped

    @staticmethod
    def _wrong_record_condition():
        return or_(
            ExerciseRecord.do_isTrue.is_(False),
            ExerciseRecord.do_score < PASS_SCORE,
        )

    async def get_random_new_question(
        self, stu_id: int, course_id: int, db: AsyncSession
    ) -> Optional[QuestionResponse]:
        """获取指定学科下、不在学生做题记录中的随机一道题（用于仪表盘"跳转练习"）"""
        # 子查询：该学生已做过的题目 ID
        subquery = (
            select(ExerciseRecord.question_id)
            .where(ExerciseRecord.stu_id == stu_id)
            .subquery()
        )
        result = await db.execute(
            select(Question)
            .where(
                and_(
                    Question.course_id == course_id,
                    Question.question_id.notin_(subquery),
                )
            )
            .order_by(func.random())
            .limit(1)
        )
        question = result.scalar_one_or_none()
        if question is None:
            return None
        return QuestionResponse.model_validate(question)

    async def get_random_record_question(
        self, stu_id: int, course_id: int, db: AsyncSession
    ) -> Optional[QuestionResponse]:
        """获取指定学科下、学生做题记录中的随机一道题（用于仪表盘"做题记录"）"""
        result = await db.execute(
            select(Question)
            .join(ExerciseRecord, Question.question_id == ExerciseRecord.question_id)
            .where(
                and_(
                    ExerciseRecord.stu_id == stu_id,
                    Question.course_id == course_id,
                )
            )
            .order_by(func.random())
            .limit(1)
        )
        question = result.scalar_one_or_none()
        if question is None:
            return None
        return QuestionResponse.model_validate(question)

    async def get_question_ids_by_course(
        self, course_id: int, db: AsyncSession
    ) -> list[int]:
        """获取指定学科下所有题目的 ID 列表（用于仪表盘跳转后前后切换）"""
        result = await db.execute(
            select(Question.question_id)
            .where(Question.course_id == course_id)
            .order_by(Question.question_id)
        )
        return [row[0] for row in result.all()]

    async def get_record_question_ids_by_course(
        self, stu_id: int, course_id: int, db: AsyncSession
    ) -> list[int]:
        """获取指定学科下学生做题记录中所有题目的 ID 列表（用于仪表盘做题记录跳转后前后切换）"""
        result = await db.execute(
            select(Question.question_id)
            .join(ExerciseRecord, Question.question_id == ExerciseRecord.question_id)
            .where(
                and_(
                    ExerciseRecord.stu_id == stu_id,
                    Question.course_id == course_id,
                )
            )
            .order_by(Question.question_id)
        )
        return [row[0] for row in result.all()]
