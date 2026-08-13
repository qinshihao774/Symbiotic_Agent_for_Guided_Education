import request from '@/utils/request'

// auth API 调用封装

export interface StudentProfile {
  stu_id: number
  stu_name: string
  stu_gender?: string | null
  stu_email?: string | null
  created_at: string
}

export interface UpdateProfileData {
  stu_name?: string
  stu_email?: string
  stu_pwd?: string
  stu_gender?: string
}

/** 获取当前登录用户信息 */
export const fetchCurrentUser = (): Promise<{
  id: number
  user_type: string
  name: string
  email: string | null
  gender: string | null
  stu_level: string | null
  class_id: number | null
  class_name: string | null
}> => {
  return request.get('/auth/me')
}

/** 更新学生个人信息 */
export const updateProfile = (data: UpdateProfileData): Promise<StudentProfile> => {
  return request.put('/auth/profile', data)
}
