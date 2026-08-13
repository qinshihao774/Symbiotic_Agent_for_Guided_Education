import request from '@/utils/request'

// learning API 调用封装

// 掌握度层级树节点（学科→章节→小节→知识点）
export interface MasteryKnowledgePoint {
  name: string
  degree: number
  answered_count: number
  correct_count: number
}

export interface MasterySection {
  name: string
  degree: number
  process: number
  knowledge_points: MasteryKnowledgePoint[]
}

export interface MasteryChapter {
  name: string
  degree: number
  process: number
  sections: MasterySection[]
  knowledge_points: MasteryKnowledgePoint[]
}

export interface MasteryHierarchy {
  course_id: number
  course_name: string
  course_degree: number
  course_process: number
  chapters: MasteryChapter[]
}

// 获取某学科下学生的掌握度层级树
export function fetchMasteryHierarchy(courseId: number): Promise<MasteryHierarchy> {
  return request.get('/learning/mastery/hierarchy', { params: { course_id: courseId } })
}

/** 获取当前学生各学科的 course_process 进度（供仪表盘使用）。
 *  返回格式：{ [course_id]: course_process }
 *  course_process 为 0~1 的浮点数，null 时返回 0。
 */
export function fetchDashboardProgress(): Promise<Record<number, number>> {
  return request.get('/learning/dashboard-progress')
}