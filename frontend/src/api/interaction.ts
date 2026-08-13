import request from '@/utils/request'

export interface InteractionMessage {
  msg_id: number;
  msg_texts: string;
  stu_id: number;
  stu_name?: string | null;
  answer_num: number;
  created_at: string;
}

export interface InteractionMessageList {
  total: number;
  items: InteractionMessage[];
}

export interface InteractionAnswer {
  answer_id: number;
  answer_text: string;
  msg_id: number;
  stu_id?: number | null;
  tea_id?: number | null;
  author_name?: string | null;
  author_type?: string | null; // student / teacher
  created_at: string;
}

/** 发布一条互动消息 */
export const publishMessage = (msgTexts: string): Promise<InteractionMessage> => {
  return request.post<InteractionMessage>('/interaction/messages', { msg_texts: msgTexts })
}

/** 分页查询互动消息列表 */
export const fetchMessages = (page: number, pageSize: number): Promise<InteractionMessageList> => {
  return request.get<InteractionMessageList>('/interaction/messages', {
    params: { page, page_size: pageSize }
  })
}

/** 查询单条互动消息详情 */
export const fetchMessageDetail = (msgId: number): Promise<InteractionMessage> => {
  return request.get<InteractionMessage>(`/interaction/messages/${msgId}`)
}

/** 发布一条回答 */
export const publishAnswer = (msgId: number, answerText: string): Promise<InteractionAnswer> => {
  return request.post<InteractionAnswer>('/interaction/answers', {
    msg_id: msgId,
    answer_text: answerText
  })
}

/** 查询某条消息下的所有回答 */
export const fetchAnswers = (msgId: number): Promise<InteractionAnswer[]> => {
  return request.get<InteractionAnswer[]>(`/interaction/messages/${msgId}/answers`)
}
