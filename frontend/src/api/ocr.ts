// frontend/src/api/ocr.ts
import request from '@/utils/request'

export interface OcrParams {
  lang: 'ch' | 'en' | 'japan' | 'korean'
  formula_enable: boolean
  table_enable: boolean
  start_page_id: number
  end_page_id: number
}

export interface TaskSubmitResponse {
  task_id: string
  status: string
  status_url: string
  result_url: string
  file_names?: string[]
  created_at?: string
}

export interface TaskStatusResponse {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  file_names: string[]
  created_at: string
  started_at?: string
  completed_at?: string
  error?: string
}

/**
 * 提交 OCR 任务
 */
export async function submitOcrTask(
  files: File[],
  params: OcrParams,
): Promise<TaskSubmitResponse> {
  const formData = new FormData()

  files.forEach((file) => {
    formData.append('files', file)
  })

  formData.append('lang', params.lang)
  formData.append('formula_enable', String(params.formula_enable))
  formData.append('table_enable', String(params.table_enable))
  formData.append('start_page_id', String(params.start_page_id))
  formData.append('end_page_id', String(params.end_page_id))

  const response = await request.post('/ocr/tasks', formData)

  return response as unknown as TaskSubmitResponse
}

/**
 * 查询任务状态
 */
export async function getOcrTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  const response = await request.get(`/ocr/tasks/${taskId}`)
  return response as unknown as TaskStatusResponse
}

/**
 * 获取 OCR 任务结果下载 URL
 */
export function getOcrTaskResultDownloadUrl(taskId: string): string {
  return `/api/ocr/tasks/${taskId}/result`
}
