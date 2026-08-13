/** AI 学习分析 API 封装 */

import request from '@/utils/request'

/** AI 分析结果类型 */
export interface StuAnalysisResult {
  stu_id: number
  dimensions_available: number
  weights: {
    level: number
    mastery: number
    wrong_exercises: number
  }
  dimensions_detail: {
    level: {
      available: boolean
      value: string | null
    }
    mastery: {
      available: boolean
      node_count: number
      weakest_nodes: Array<{ name: string; degree: number }>
    }
    wrong_exercises: {
      available: boolean
      total_count: number
      knowledge_summary: Array<{ node: string; wrong_count: number; avg_score: number | null }>
    }
  }
  analysis: {
    summary: string
    weakness_analysis: string
    improvement_suggestions: string
    comprehensive_rating: string
    priority_focus: string[]
  } | null
  error?: string
}

/** 发起 AI 学习分析 */
export const fetchStuAnalysis = (stuId: number): Promise<StuAnalysisResult> => {
  return request.post<StuAnalysisResult>('/ai/analysis/stu_analysis', { stu_id: stuId })
}
