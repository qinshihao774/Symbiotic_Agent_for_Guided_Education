/** 学习规划 API 封装 */

import request from '@/utils/request'

/** 单学科学习规划结果 */
export interface SubjectPlan {
  course_id: number
  course_name: string
  /** ok=已生成规划 / insufficient=维度不足 / db_error=数据库异常 */
  status: 'ok' | 'insufficient' | 'db_error'
  dimensions_available: number
  weights: {
    ai_analysis: number
    knowledge_mastery: number
    exercise: number
    teacher_opinion: number
  }
  dimensions_detail: Record<string, unknown>
  missing_dimensions: string[]
  error: string | null
  error_message?: string
  plan: {
    overall_goal: string
    weak_points: string[]
    weekly_plan: Array<{
      week: number
      theme: string
      tasks: string[]
      exercises: string
    }>
    priority_focus: string[]
    teacher_notes: string
  } | null
}

/** 学习规划整体结果 */
export interface LearningPlanResult {
  stu_id: number
  subjects: SubjectPlan[]
  error: string | null
  error_message?: string
}

/** 发起学习规划（按学科分别制定） */
export const fetchLearningPlan = (stuId: number): Promise<LearningPlanResult> => {
  return request.post<LearningPlanResult>(
    '/ai/analysis/learning_plan',
    { stu_id: stuId },
    { timeout: 300000 }, // 学习规划涉及多轮 LLM 调用（4 学科 × ReAct 循环），放宽超时
  )
}
