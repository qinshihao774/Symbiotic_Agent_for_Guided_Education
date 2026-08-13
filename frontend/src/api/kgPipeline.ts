import request from '@/utils/request'

export interface TaskSubmitResponse {
  task_id: string
  status: string
  status_url: string
  result_url: string
}

export interface KgBuildStatusResponse {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  chunks?: number
  nodes?: number
  edges?: number
  error?: string
}

export interface KgBuildResult {
  chunks: number
  nodes: number
  edges: number
  status: string
  error?: string
}

export async function submitKgBuild(file: File, courseId?: number): Promise<TaskSubmitResponse> {
  const formData = new FormData()
  formData.append('file', file)
  if (courseId != null) {
    formData.append('course_id', String(courseId))
  }
  return request.post('/kg/build', formData) as unknown as TaskSubmitResponse
}

export async function getKgBuildStatus(taskId: string): Promise<KgBuildStatusResponse> {
  return request.get(`/kg/build/status/${taskId}`) as unknown as KgBuildStatusResponse
}

export async function getKgBuildResult(taskId: string): Promise<KgBuildResult> {
  return request.get(`/kg/build/result/${taskId}`) as unknown as KgBuildResult
}
