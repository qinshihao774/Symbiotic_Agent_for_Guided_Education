import request from '@/utils/request'
import type { GraphData } from '@/api/knowledge'
import type { MasteryHierarchy } from '@/api/learning'

export interface TeacherCourse {
  course_id: number
  course_name: string
}

export interface CourseChapter {
  id: string
  name: string
}

export interface TeacherClass {
  class_id: number
  class_name: string
  classmates_num: number | null
  student_count: number
}

export interface ClassStudent {
  stu_id: number
  stu_name: string
  stu_level: string | null
  course_process: number | null
}

export interface DifficultKnowledgePoint {
  name: string
  count: number
  ratio: number
}

export interface DifficultChapter {
  name: string
  count: number
  ratio: number
}

/** 班级教学建议 — 三维度评估结果 */
export interface ClassTeachingSuggestion {
  class_id: number
  course_id: number
  course_name: string | null
  status: 'ok' | 'insufficient' | 'db_error'
  dimensions_available: number
  weights: Record<string, number>
  dimensions_detail: Record<string, any>
  missing_dimensions: string[]
  error: string | null
  error_message: string | null
  ai_level: string | null
  course_avg_process: number | null
  suggestion: {
    ai_level?: string
    overall_assessment: string
    priority_focus: string[]
    teaching_strategies: { strategy: string; detail: string }[]
    difficult_focus: string
    homework_suggestion: string
    teacher_notes: string
  } | null
}

export function getTeacherCourses() {
  return request.get<TeacherCourse[]>('/teacher/courses')
}

export function getCourseChapters(courseId: number) {
  return request.get<CourseChapter[]>(`/teacher/courses/${courseId}/chapters`)
}

export function getTeacherClasses() {
  return request.get<TeacherClass[]>('/teacher/classes')
}

export function getClassStudents(classId: number, courseId: number) {
  return request.get<ClassStudent[]>(`/teacher/classes/${classId}/students`, {
    params: { course_id: courseId },
  })
}

export function getDifficultKnowledge(classId: number, courseId: number) {
  return request.get<DifficultKnowledgePoint[]>(
    `/teacher/classes/${classId}/difficult-knowledge`,
    {
      params: { course_id: courseId },
    },
  )
}

export function getDifficultChapters(classId: number, courseId: number) {
  return request.get<DifficultChapter[]>(
    `/teacher/classes/${classId}/difficult-chapters`,
    {
      params: { course_id: courseId },
    },
  )
}

export interface StudentKnowledgeGraph {
  graph: GraphData
  mastery: MasteryHierarchy
}

/** 获取某学生在某学科下的个人知识图谱（图数据 + 掌握度层级树）。
 *  后端严格校验当前教师-班级-学科-学生对应关系，越权返回空对象。
 */
export function getStudentKnowledgeGraph(studentId: number, courseId: number) {
  return request.get<StudentKnowledgeGraph>(
    `/teacher/students/${studentId}/knowledge-graph`,
    {
      params: { course_id: courseId },
    },
  )
}

/** 生成班级教学建议（AI ReAct Agent，三维度评估）。
 *  综合学生评级、班级知识点平均掌握度进度、疑难章节与知识点三个维度，
 *  各维度等权（3 维各 1/3，2 维各 1/2），缺失维度时触发兜底机制。
 */
export function getClassTeachingSuggestion(classId: number, courseId: number) {
  return request.get<ClassTeachingSuggestion>(
    `/teacher/classes/${classId}/teaching-suggestion`,
    {
      params: { course_id: courseId },
    },
  )
}
