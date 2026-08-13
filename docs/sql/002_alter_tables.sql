-- ============================================================
-- 智教慧学 — 增量迁移脚本（只新增字段/表，不删除任何内容）
-- 数据库: chuma (PostgreSQL)
-- 日期: 2026-08-03
-- 说明: 用于把现有数据库表结构补齐到与 001_create_tables.sql 一致。
--       所有语句均使用 IF NOT EXISTS 判断，可安全重复执行。
--       本脚本只做“新增”，绝不删除表或字段。
-- ============================================================

-- 1. classes — 班级表：新增 AI 相关字段
ALTER TABLE classes
    ADD COLUMN IF NOT EXISTS ai_level            VARCHAR(32),
    ADD COLUMN IF NOT EXISTS ai_suggestion       TEXT,
    ADD COLUMN IF NOT EXISTS course_avg_process  FLOAT;

-- 2. teachers — 教师表：新增管理员标记字段
ALTER TABLE teachers
    ADD COLUMN IF NOT EXISTS isadmin  SMALLINT  DEFAULT 0;

-- 3. kg_graphs — 知识图谱元数据表：新增学科绑定字段（学科 → 知识图谱 映射）
ALTER TABLE kg_graphs
    ADD COLUMN IF NOT EXISTS course_id  BIGINT;

-- 为 course_id 建立索引，加速按学科查询图谱
CREATE INDEX IF NOT EXISTS ix_kg_graphs_course_id ON kg_graphs (course_id);

