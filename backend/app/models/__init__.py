"""ORM 模型包 — 导入所有模型以注册到 Base.metadata"""

# 已有模型
from app.models.kg_graph import KgGraph  # noqa: F401
from app.models.user import Student, Teacher  # noqa: F401
from app.models.classes import Class  # noqa: F401

# 新增模型
from app.models.course import Course  # noqa: F401
from app.models.question import Question  # noqa: F401
from app.models.learning import StudentCourseMastery, StudentKnowledgeMastery  # noqa: F401
from app.models.exercise_record import ExerciseRecord  # noqa: F401
from app.models.evaluation_analysis import EvaluationAnalysis  # noqa: F401
from app.models.teacher_relation import TeacherCourse, TeacherClass  # noqa: F401
from app.models.interaction import InteractionMessage, InteractionAnswer  # noqa: F401
