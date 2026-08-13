import request from '@/utils/request'

/** 错误选项的知识误区拆解 */
export interface Misconception {
  option: string
  content: string
  why_wrong: string
  misconception: string
  correction: string
}

/** 维度 1：题目与答案深度剖析 */
export interface Aspect1 {
  question_type: string
  question_difficulty: string
  core_knowledge: string
  correct_analysis: string
  misconceptions: Misconception[]
  summary: string
}

/** 知识图谱局部网络中的邻居节点 */
export interface GraphNeighbor {
  node_name: string
  relationship_name: string
  direction: string
  node_description: string
}

/** 维度 2：GraphRAG + 知识图谱局部网络视角 */
export interface Aspect2 {
  center_node: {
    name: string
    type: string
    description: string
  }
  neighbors: GraphNeighbor[]
  knowledge_network_analysis: string
  learning_suggestion: string
}

/** AI 题目分析结果 */
export interface QuestionAnalysisResult {
  question_id: number
  course_id: number | null
  course_name: string | null
  kg_node_name: string | null
  status: 'ok' | 'no_data' | 'db_error'
  error: string | null
  error_message: string | null
  analysis: {
    /** 个性化作答剖析（结合学生提交的答案） */
    personal: {
      stu_answer: string
      is_correct: boolean
      verdict: string
      personal_misconception: string
      personal_correction: string
    }
    aspect1: Aspect1
    aspect2: Aspect2
  } | null
}

/**
 * 获取 AI 题目分析与解惑（双维度：题目答案深度剖析 + 知识图谱局部网络视角）
 * @param questionId 题目 ID
 * @param stuAnswer 学生提交的答案（do_stu_answer），用于个性化作答剖析
 * @param stuId 学生 ID，可选，用于兜底查询该学生最近一次作答
 */
export const fetchQuestionAnalysis = (
  questionId: number,
  stuAnswer?: string,
  stuId?: number,
): Promise<QuestionAnalysisResult> => {
  // 仅当 stu_id 有值时传入，避免 undefined 被序列化为空字符串导致后端 422
  const body: Record<string, unknown> = { question_id: questionId }
  if (stuAnswer) body.do_stu_answer = stuAnswer
  if (stuId) body.stu_id = stuId
  return request.post<QuestionAnalysisResult>(
    '/ai/analysis/question',
    body,
    { timeout: 120000 }, // 涉及 LLM 深度分析 + 图谱遍历，放宽超时
  )
}
