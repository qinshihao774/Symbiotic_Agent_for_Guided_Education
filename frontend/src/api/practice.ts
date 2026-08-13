import request from '@/utils/request'

export interface Course {
  course_id: number;
  course_name: string;
  course_description?: string;
  kg_id?: number;
  created_at: string;
  updated_at: string;
}

export interface Question {
  question_id: number;
  question_description: string;
  question_answer: string;
  question_options?: any;
  question_type: string;
  question_difficulty: number;
  question_explanation?: string;
  course_id: number;
  kg_node_name?: string;
  created_at: string;
  updated_at: string;
}

export interface ExerciseRecordCreate {
  question_id: number;
  course_id: number;
  kg_node_name?: string;
  question_type: string;
  question_difficulty: number;
  do_stu_answer: string;
}

export interface ExerciseRecord {
  do_id: number;
  question_id: number;
  stu_id: number;
  course_id?: number;
  kg_node_name?: string;
  question_type?: string;
  question_difficulty?: number;
  do_stu_answer: string;
  do_score?: number | null;
  do_isTrue?: boolean | null;
  iserror_firstly?: boolean | null;
  created_at: string;
}

export interface ExerciseRecordListItem {
  do_id: number;
  question_id: number;
  question_description: string;
  course_name?: string;
  question_type?: string;
  question_difficulty?: number;
  do_stu_answer: string;
  do_score?: number | null;
  do_isTrue?: boolean | null;
  kg_node_name?: string;
  created_at: string;
}

// practice API 调用封装
export const fetchCourses = (): Promise<Course[]> => {
  return request.get<Course[]>('/practice/courses')
}

export const fetchQuestions = (courseId?: number, kgNodeName?: string, difficulty?: number): Promise<Question[]> => {
  return request.get<Question[]>('/practice/questions', {
    params: { course_id: courseId, kg_node_name: kgNodeName, difficulty }
  })
}

export const fetchQuestionById = (questionId: number): Promise<Question> => {
  return request.get<Question>(`/practice/questions/${questionId}`)
}

/** 提交答案并存储做题记录 */
export const submitExerciseRecord = (data: ExerciseRecordCreate): Promise<ExerciseRecord> => {
  return request.post<ExerciseRecord>('/practice/submit', data)
}

/** 获取做题记录
 *  @param courseId 可选，按学科筛选
 *  @param wrongOnly 可选，仅获取错题
 */
export const fetchExerciseRecords = (courseId?: number, wrongOnly?: boolean): Promise<ExerciseRecordListItem[]> => {
  return request.get<ExerciseRecordListItem[]>('/practice/exercise-records', {
    params: { course_id: courseId, wrong_only: wrongOnly }
  })
}

/** 获取按学科分组的错题记录
 *  返回格式：{ [course_id]: { course_name, records: [...] } }
 */
export const fetchWrongRecordsGrouped = (): Promise<Record<number, { course_name: string; records: ExerciseRecordListItem[] }>> => {
  return request.get<Record<number, { course_name: string; records: ExerciseRecordListItem[] }>>('/practice/wrong-records/grouped')
}

/** 仪表盘 - 获取学科下不在做题记录中的随机题目（跳转练习用）
 *  返回：{ question: Question | null, random_index: number, id_list: number[] }
 */
export const fetchDashboardNewQuestion = (courseId: number): Promise<{ question: Question | null; random_index: number; id_list: number[] }> => {
  return request.get('/practice/dashboard/new-question', {
    params: { course_id: courseId }
  })
}

/** 仪表盘 - 获取学科下做题记录中的随机题目（做题记录用）
 *  返回：{ question: Question | null, random_index: number, id_list: number[] }
 */
export const fetchDashboardRecordQuestion = (courseId: number): Promise<{ question: Question | null; random_index: number; id_list: number[] }> => {
  return request.get('/practice/dashboard/record-question', {
    params: { course_id: courseId }
  })
}
