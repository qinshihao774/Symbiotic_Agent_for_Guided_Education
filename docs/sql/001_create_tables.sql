-- ============================================================
-- 智教慧学 — 数据模型建表脚本
-- 数据库: chuma (PostgreSQL)
-- 日期: 2026-07-28
-- 说明: 所有表均使用 IF NOT EXISTS 判断，已存在的表不会重复创建，
--       可安全重复执行本脚本。
-- ============================================================

-- 1. kg_graphs — 知识图谱元数据
CREATE TABLE IF NOT EXISTS kg_graphs (
    id              BIGINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    graph_name      VARCHAR(128)  NOT NULL UNIQUE,
    original_filename VARCHAR(256) NOT NULL,
    file_path       VARCHAR(512),
    course_id       BIGINT,
    node_count      INTEGER       DEFAULT 0,
    edge_count      INTEGER       DEFAULT 0,
    chunk_count     INTEGER       DEFAULT 0,
    status          VARCHAR(20)   DEFAULT 'pending',
    created_at      TIMESTAMP     DEFAULT now(),
    updated_at      TIMESTAMP     DEFAULT now()
);

-- 如果 kg_graphs 已存在且有 user_id 列，执行以下语句删除：
-- DROP INDEX IF EXISTS ix_kg_graphs_user_id;
-- ALTER TABLE kg_graphs DROP COLUMN IF EXISTS user_id;

-- 1b. kg_nodes — 统一知识节点表
CREATE TABLE IF NOT EXISTS kg_nodes (
    kg_id           BIGINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    course_id       BIGINT,
    kg_node         VARCHAR(128)  NOT NULL,
    kg_node_type    VARCHAR(32),
    kg_parent_id    BIGINT,
    kg_featspace    JSONB
);
CREATE INDEX IF NOT EXISTS ix_kg_nodes_course_id ON kg_nodes(course_id);
CREATE INDEX IF NOT EXISTS ix_kg_nodes_parent_id  ON kg_nodes(kg_parent_id);

-- 1c. kg_edges — 统一拓扑关系表
CREATE TABLE IF NOT EXISTS kg_edges (
    edge_id         BIGINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    source_node_id  BIGINT        NOT NULL REFERENCES kg_nodes(kg_id),
    target_node_id  BIGINT        NOT NULL REFERENCES kg_nodes(kg_id),
    edge_type       VARCHAR(64),
    edge_weight     FLOAT         DEFAULT 1.0
);
CREATE INDEX IF NOT EXISTS ix_kg_edges_source ON kg_edges(source_node_id);
CREATE INDEX IF NOT EXISTS ix_kg_edges_target ON kg_edges(target_node_id);

-- 2. classes — 班级表
CREATE TABLE IF NOT EXISTS classes (
    class_id            BIGINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    class_name          VARCHAR(64)   NOT NULL UNIQUE,
    classmates_num      INTEGER       DEFAULT 0,
    ai_level            VARCHAR(32),
    ai_suggestion       TEXT,
    course_avg_process  FLOAT,
    created_at          TIMESTAMP     DEFAULT now(),
    updated_at          TIMESTAMP     DEFAULT now()
);

-- 3. students — 学生表
CREATE TABLE IF NOT EXISTS students (
    stu_id          BIGINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    stu_name        VARCHAR(64)   NOT NULL,
    stu_gender      VARCHAR(4),
    stu_email       VARCHAR(128)  UNIQUE,
    stu_pwd         VARCHAR(256),
    stu_level       VARCHAR(32),
    class_id        BIGINT        REFERENCES classes(class_id),
    created_at      TIMESTAMP     DEFAULT now(),
    updated_at      TIMESTAMP     DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_students_class_id ON students(class_id);

-- 4. teachers — 教师表
CREATE TABLE IF NOT EXISTS teachers (
    tea_id          BIGINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    tea_name        VARCHAR(64)   NOT NULL,
    tea_email       VARCHAR(128)  UNIQUE,
    tea_pwd         VARCHAR(256),
    isadmin         SMALLINT      DEFAULT 0,
    created_at      TIMESTAMP     DEFAULT now(),
    updated_at      TIMESTAMP     DEFAULT now()
);

-- 5. interaction_messages — 互动消息表
CREATE TABLE IF NOT EXISTS interaction_messages (
    msg_id          BIGINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    msg_texts       TEXT          NOT NULL,
    stu_id          BIGINT        NOT NULL REFERENCES students(stu_id),
    answer_num      INTEGER       DEFAULT 0,
    created_at      TIMESTAMP     DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_interaction_messages_stu_id ON interaction_messages(stu_id);

-- 6. interaction_answers — 互动消息-回答关系表
CREATE TABLE IF NOT EXISTS interaction_answers (
    answer_id       BIGINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    answer_text     TEXT          NOT NULL,
    msg_id          BIGINT        NOT NULL REFERENCES interaction_messages(msg_id),
    stu_id          BIGINT        REFERENCES students(stu_id),
    tea_id          BIGINT        REFERENCES teachers(tea_id),
    created_at      TIMESTAMP     DEFAULT now(),
    CONSTRAINT ck_interaction_answer_author CHECK (
        (stu_id IS NOT NULL AND tea_id IS NULL) OR
        (tea_id IS NOT NULL AND stu_id IS NULL)
    )
);
CREATE INDEX IF NOT EXISTS ix_interaction_answers_msg_id ON interaction_answers(msg_id);
CREATE INDEX IF NOT EXISTS ix_interaction_answers_stu_id ON interaction_answers(stu_id);
CREATE INDEX IF NOT EXISTS ix_interaction_answers_tea_id ON interaction_answers(tea_id);

-- 7. courses — 学科表
CREATE TABLE IF NOT EXISTS courses (
    course_id           BIGINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    course_name         VARCHAR(64)   NOT NULL UNIQUE,
    course_description  TEXT,
    kg_id               BIGINT        UNIQUE REFERENCES kg_graphs(id),
    created_at          TIMESTAMP     DEFAULT now(),
    updated_at          TIMESTAMP     DEFAULT now()
);

-- 6. questions — 题库表
CREATE TABLE IF NOT EXISTS questions (
    question_id         BIGINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    question_description TEXT         NOT NULL,
    question_answer      TEXT         NOT NULL,
    question_options     JSON,
    question_type        VARCHAR(32)  NOT NULL,
    question_difficulty  SMALLINT     NOT NULL,
    question_explanation TEXT,
    course_id            BIGINT       NOT NULL REFERENCES courses(course_id),
    kg_id                BIGINT       REFERENCES kg_graphs(id),
    kg_node_name         VARCHAR(128),
    created_at           TIMESTAMP    DEFAULT now(),
    updated_at           TIMESTAMP    DEFAULT now(),
    CONSTRAINT ck_question_difficulty_range CHECK (question_difficulty >= 1 AND question_difficulty <= 5)
);
CREATE INDEX IF NOT EXISTS ix_questions_course_id    ON questions(course_id);
CREATE INDEX IF NOT EXISTS ix_questions_kg_id        ON questions(kg_id);
CREATE INDEX IF NOT EXISTS ix_questions_kg_node_name ON questions(kg_node_name);
CREATE INDEX IF NOT EXISTS ix_questions_difficulty   ON questions(question_difficulty);

-- 7. exercise_records — 做题记录表
CREATE TABLE IF NOT EXISTS exercise_records (
    do_id               BIGINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    question_id         BIGINT        NOT NULL REFERENCES questions(question_id),
    stu_id              BIGINT        NOT NULL REFERENCES students(stu_id),
    kg_id               BIGINT        REFERENCES kg_graphs(id),
    course_id           BIGINT        REFERENCES courses(course_id),
    kg_node_name        VARCHAR(128),
    question_type       VARCHAR(32),
    question_difficulty SMALLINT,
    do_stu_answer       TEXT          NOT NULL,
    do_score            FLOAT,
    do_istrue           BOOLEAN,
    iserror_firstly     BOOLEAN,
    created_at          TIMESTAMP     DEFAULT now(),
    CONSTRAINT ck_do_score_range CHECK (do_score >= 0.0 AND do_score <= 10.0),
    CONSTRAINT ck_exercise_question_difficulty CHECK (question_difficulty >= 1 AND question_difficulty <= 5)
);
CREATE INDEX IF NOT EXISTS ix_exercise_records_question_id   ON exercise_records(question_id);
CREATE INDEX IF NOT EXISTS ix_exercise_records_stu_id        ON exercise_records(stu_id);
CREATE INDEX IF NOT EXISTS ix_exercise_records_kg_id         ON exercise_records(kg_id);
CREATE INDEX IF NOT EXISTS ix_exercise_records_course_id     ON exercise_records(course_id);
CREATE INDEX IF NOT EXISTS ix_exercise_records_kg_node_name  ON exercise_records(kg_node_name);
CREATE INDEX IF NOT EXISTS ix_exercise_records_stu_node      ON exercise_records(stu_id, kg_node_name);

-- 8. student_course_mastery — 学生-学科掌握度表
CREATE TABLE IF NOT EXISTS student_course_mastery (
    stu_id          BIGINT    NOT NULL REFERENCES students(stu_id),
    course_id       BIGINT    NOT NULL REFERENCES courses(course_id),
    course_degree   FLOAT     NOT NULL,
    course_process  FLOAT,
    updated_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (stu_id, course_id),
    CONSTRAINT ck_course_degree_range CHECK (course_degree >= 0.0 AND course_degree <= 5.0),
    CONSTRAINT ck_course_process_range CHECK (course_process >= 0.0 AND course_process <= 1.0)
);

-- 9. student_knowledge_mastery — 学生-知识点掌握度表
--    依据 003_student_mastery.sql 迁移后的最终结构：
--      1) 新增 course_id 维度（区分多学科同名知识点）
--      2) 新增 answered_count / correct_count 统计字段
--      3) 主键为 (stu_id, course_id, kg_node_name)
CREATE TABLE IF NOT EXISTS student_knowledge_mastery (
    stu_id          BIGINT       NOT NULL REFERENCES students(stu_id),
    course_id       BIGINT,
    kg_node_name    VARCHAR(128) NOT NULL,
    kg_id           BIGINT       REFERENCES kg_graphs(id),
    kg_degree       FLOAT        NOT NULL,
    answered_count  INTEGER      DEFAULT 0,
    correct_count   INTEGER      DEFAULT 0,
    updated_at      TIMESTAMP    DEFAULT now(),
    PRIMARY KEY (stu_id, course_id, kg_node_name),
    CONSTRAINT ck_kg_degree_range CHECK (kg_degree >= 0.0 AND kg_degree <= 5.0)
);
CREATE INDEX IF NOT EXISTS ix_student_knowledge_mastery_node_name ON student_knowledge_mastery(kg_node_name);
CREATE INDEX IF NOT EXISTS ix_student_knowledge_mastery_kg_id      ON student_knowledge_mastery(kg_id);
CREATE INDEX IF NOT EXISTS ix_student_knowledge_mastery_course     ON student_knowledge_mastery(course_id);

-- 10. teacher_student — 教师-学生关系表
CREATE TABLE IF NOT EXISTS teacher_student (
    tea_id      BIGINT      NOT NULL REFERENCES teachers(tea_id),
    stu_id      BIGINT      NOT NULL REFERENCES students(stu_id),
    created_at  TIMESTAMP   DEFAULT now(),
    PRIMARY KEY (tea_id, stu_id)
);
CREATE INDEX IF NOT EXISTS ix_teacher_student_stu_id ON teacher_student(stu_id);

-- 11. evaluation_analysis — 评价分析表
CREATE TABLE IF NOT EXISTS evaluation_analysis (
    ea_id               BIGINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    stu_id              BIGINT        NOT NULL REFERENCES students(stu_id),
    publisher_id        BIGINT,
    publisher_name      VARCHAR(64)   NOT NULL,
    ea_description      TEXT,
    created_at          TIMESTAMP     DEFAULT now(),
    updated_at          TIMESTAMP     DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_evaluation_analysis_stu_id        ON evaluation_analysis(stu_id);
CREATE INDEX IF NOT EXISTS ix_evaluation_analysis_publisher_id  ON evaluation_analysis(publisher_id);

-- 12. teacher_course — 教师-学科关系表（可选）
CREATE TABLE IF NOT EXISTS teacher_course (
    tea_id      BIGINT      NOT NULL REFERENCES teachers(tea_id),
    course_id   BIGINT      NOT NULL REFERENCES courses(course_id),
    created_at  TIMESTAMP   DEFAULT now(),
    PRIMARY KEY (tea_id, course_id)
);
CREATE INDEX IF NOT EXISTS ix_teacher_course_course_id ON teacher_course(course_id);

-- 13. teacher_class — 教师-班级关系表
CREATE TABLE IF NOT EXISTS teacher_class (
    class_id    BIGINT      NOT NULL REFERENCES classes(class_id),
    tea_id      BIGINT      NOT NULL REFERENCES teachers(tea_id),
    created_at  TIMESTAMP   DEFAULT now(),
    PRIMARY KEY (class_id, tea_id)
);
CREATE INDEX IF NOT EXISTS ix_teacher_class_tea_id ON teacher_class(tea_id);
