"""add student side tables and remove kg_graphs.user_id

Revision ID: 002
Revises: 001
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Remove kg_graphs.user_id
    op.drop_index("ix_kg_graphs_user_id", table_name="kg_graphs")
    op.drop_column("kg_graphs", "user_id")

    # 2. Create students
    op.create_table(
        "students",
        sa.Column("stu_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("stu_name", sa.String(64), nullable=False),
        sa.Column("stu_gender", sa.String(4), nullable=True),
        sa.Column("stu_email", sa.String(128), nullable=True, unique=True),
        sa.Column("stu_pwd", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # 3. Create teachers
    op.create_table(
        "teachers",
        sa.Column("tea_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tea_name", sa.String(64), nullable=False),
        sa.Column("tea_email", sa.String(128), nullable=True, unique=True),
        sa.Column("tea_pwd", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # 4. Create courses
    op.create_table(
        "courses",
        sa.Column("course_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("course_name", sa.String(64), nullable=False, unique=True),
        sa.Column("course_description", sa.Text(), nullable=True),
        sa.Column("kg_id", sa.BigInteger(), sa.ForeignKey("kg_graphs.id"), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # 5. Create questions
    op.create_table(
        "questions",
        sa.Column("question_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("question_description", sa.Text(), nullable=False),
        sa.Column("question_answer", sa.Text(), nullable=False),
        sa.Column("question_options", sa.JSON(), nullable=True),
        sa.Column("question_type", sa.String(32), nullable=False),
        sa.Column("question_difficulty", sa.SmallInteger(), nullable=False),
        sa.Column("question_explanation", sa.Text(), nullable=True),
        sa.Column("course_id", sa.BigInteger(), sa.ForeignKey("courses.course_id"), nullable=False),
        sa.Column("kg_node_name", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.CheckConstraint("question_difficulty >= 1 AND question_difficulty <= 5", name="ck_question_difficulty_range"),
    )
    op.create_index("ix_questions_course_id", "questions", ["course_id"])
    op.create_index("ix_questions_kg_node_name", "questions", ["kg_node_name"])
    op.create_index("ix_questions_difficulty", "questions", ["question_difficulty"])

    # 6. Create exercise_records
    op.create_table(
        "exercise_records",
        sa.Column("do_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("question_id", sa.BigInteger(), sa.ForeignKey("questions.question_id"), nullable=False),
        sa.Column("stu_id", sa.BigInteger(), sa.ForeignKey("students.stu_id"), nullable=False),
        sa.Column("kg_node_name", sa.String(128), nullable=True),
        sa.Column("do_stu_answer", sa.Text(), nullable=False),
        sa.Column("do_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.CheckConstraint("do_score >= 0.0 AND do_score <= 10.0", name="ck_do_score_range"),
    )
    op.create_index("ix_exercise_records_question_id", "exercise_records", ["question_id"])
    op.create_index("ix_exercise_records_stu_id", "exercise_records", ["stu_id"])
    op.create_index("ix_exercise_records_kg_node_name", "exercise_records", ["kg_node_name"])
    op.create_index("ix_exercise_records_stu_node", "exercise_records", ["stu_id", "kg_node_name"])

    # 7. Create student_course_mastery
    op.create_table(
        "student_course_mastery",
        sa.Column("stu_id", sa.BigInteger(), sa.ForeignKey("students.stu_id"), primary_key=True),
        sa.Column("course_id", sa.BigInteger(), sa.ForeignKey("courses.course_id"), primary_key=True),
        sa.Column("course_degree", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.CheckConstraint("course_degree >= 0.0 AND course_degree <= 5.0", name="ck_course_degree_range"),
    )

    # 8. Create student_knowledge_mastery
    op.create_table(
        "student_knowledge_mastery",
        sa.Column("stu_id", sa.BigInteger(), sa.ForeignKey("students.stu_id"), primary_key=True),
        sa.Column("kg_node_name", sa.String(128), primary_key=True),
        sa.Column("kg_degree", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.CheckConstraint("kg_degree >= 0.0 AND kg_degree <= 5.0", name="ck_kg_degree_range"),
    )
    op.create_index("ix_student_knowledge_mastery_node_name", "student_knowledge_mastery", ["kg_node_name"])


def downgrade() -> None:
    op.drop_index("ix_student_knowledge_mastery_node_name", "student_knowledge_mastery")
    op.drop_table("student_knowledge_mastery")
    op.drop_table("student_course_mastery")

    op.drop_index("ix_exercise_records_stu_node", "exercise_records")
    op.drop_index("ix_exercise_records_kg_node_name", "exercise_records")
    op.drop_index("ix_exercise_records_stu_id", "exercise_records")
    op.drop_index("ix_exercise_records_question_id", "exercise_records")
    op.drop_table("exercise_records")

    op.drop_index("ix_questions_difficulty", "questions")
    op.drop_index("ix_questions_kg_node_name", "questions")
    op.drop_index("ix_questions_course_id", "questions")
    op.drop_table("questions")

    op.drop_table("courses")
    op.drop_table("teachers")
    op.drop_table("students")

    # Restore kg_graphs.user_id (was NOT NULL originally)
    op.add_column("kg_graphs", sa.Column("user_id", sa.BigInteger(), nullable=False))
    op.create_index("ix_kg_graphs_user_id", "kg_graphs", ["user_id"])
