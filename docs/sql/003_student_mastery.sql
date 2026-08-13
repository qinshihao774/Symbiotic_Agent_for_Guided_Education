-- ============================================================
-- 智教慧学 — 学生掌握度表结构迁移脚本
-- 数据库: chuma (PostgreSQL)
-- 日期: 2026-08-06
-- 说明: 支持"学生维系多学科知识图谱掌握度"闭环。
--       改造 student_knowledge_mastery 表：
--         1) 新增 course_id 维度（区分多学科同名知识点）
--         2) 新增 answered_count / correct_count 统计字段
--         3) 主键由 (stu_id, kg_node_name) 重建为 (stu_id, course_id, kg_node_name)
--       注意: 本脚本会删除旧主键并重建，请先备份数据。
-- ============================================================

-- 1. 新增 course_id 列（学科维度）
ALTER TABLE student_knowledge_mastery
    ADD COLUMN IF NOT EXISTS course_id  BIGINT;

-- 2. 新增统计字段
ALTER TABLE student_knowledge_mastery
    ADD COLUMN IF NOT EXISTS answered_count  INTEGER  DEFAULT 0,
    ADD COLUMN IF NOT EXISTS correct_count   INTEGER  DEFAULT 0;

-- 3. 为 course_id 建立索引
CREATE INDEX IF NOT EXISTS ix_student_knowledge_mastery_course
    ON student_knowledge_mastery (course_id);

-- 4. 重建主键为 (stu_id, course_id, kg_node_name)
--    先删除旧主键（约束名按 PostgreSQL 默认命名规则）
DO $$
DECLARE
    pk_name text;
BEGIN
    SELECT conname INTO pk_name
    FROM pg_constraint
    WHERE conrelid = 'student_knowledge_mastery'::regclass
      AND contype = 'p'
    LIMIT 1;

    IF pk_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE student_knowledge_mastery DROP CONSTRAINT %I', pk_name);
    END IF;
END $$;

-- 5. 重建主键（course_id 为空的历史数据无法作为主键，需先回填或排除）
--    若存在 course_id 为 NULL 的历史行，请先执行下方注释中的回填语句，
--    或删除这些历史行后再执行主键重建。
--    回填示例（按 kg_node_name 关联到某学科，需按实际数据调整）：
--    UPDATE student_knowledge_mastery SET course_id = 1 WHERE course_id IS NULL;
ALTER TABLE student_knowledge_mastery
    ADD CONSTRAINT pk_student_knowledge_mastery
    PRIMARY KEY (stu_id, course_id, kg_node_name);
