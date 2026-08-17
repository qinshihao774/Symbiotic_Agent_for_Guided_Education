import type { AgentEventV2 } from '@/types/agent'

const API_BASE = '/api'

export interface ChatHistoryItem {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatChunk {
  content: string
  reasoning: string
}

export interface SuggestedQuestion {
  text: string
  node_id: string
  node_name: string
  node_type: string
  relation: 'upstream' | 'downstream' | 'both'
}

export interface LegacyAgentSSEEvent {
  type: 'tool_used' | 'tool_result' | 'content' | 'done' | 'error' | 'kg_hit' | 'suggested_questions'
  tool?: string
  query?: string
  preview?: string
  content?: string
  // kg_hit fields
  node_id?: string
  node_name?: string
  node_type?: string
  graph_name?: string
  // suggested_questions fields
  questions?: SuggestedQuestion[]
}

export type AgentSSEEvent = LegacyAgentSSEEvent | AgentEventV2

/**
 * 快速回答 — 流式调用
 */
export async function sendQuickMessage(
  message: string,
  history: ChatHistoryItem[],
  onChunk: (chunk: ChatChunk) => void,
  onDone: () => void,
  onError: (err: Error) => void,
): Promise<void> {
  try {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE}/ai/chat/quick`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message, history }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data: ')) continue

        const data = trimmed.slice(6)
        if (data === '[DONE]') {
          onDone()
          return
        }

        try {
          const parsed = JSON.parse(data) as ChatChunk
          if (parsed.content || parsed.reasoning) {
            onChunk(parsed)
          }
        } catch {
          // 忽略解析错误
        }
      }
    }

    onDone()
  } catch (err) {
    onError(err instanceof Error ? err : new Error(String(err)))
  }
}

/**
 * 深度解答 — 流式调用（调用 DeepSeek）
 */
export async function sendDeepMessage(
  question: string,
  history: ChatHistoryItem[],
  onChunk: (chunk: ChatChunk) => void,
  onDone: () => void,
  onError: (err: Error) => void,
): Promise<void> {
  try {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE}/ai/chat/deep`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ question, history }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data: ')) continue

        const data = trimmed.slice(6)
        if (data === '[DONE]') {
          onDone()
          return
        }

        try {
          const parsed = JSON.parse(data) as ChatChunk
          if (parsed.content || parsed.reasoning) {
            onChunk(parsed)
          }
        } catch {
          // 忽略解析错误
        }
      }
    }

    onDone()
  } catch (err) {
    onError(err instanceof Error ? err : new Error(String(err)))
  }
}

/**
 * 智能体模式 Agent 对话 — 流式调用（支持工具调用）
 */
export async function sendAgentMessage(
  message: string,
  history: ChatHistoryItem[],
  kgGraphIds: number[],
  messageId: string,
  onEvent: (event: AgentSSEEvent) => void,
  onDone: () => void,
  onError: (err: Error) => void,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE}/ai/agent/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message, history, kg_graph_ids: kgGraphIds, message_id: messageId }),
      signal,
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    const processEventBlock = (block: string): boolean => {
      const data = block
        .split(/\r?\n/)
        .filter(line => line.startsWith('data:'))
        .map(line => line.slice(5).trimStart())
        .join('\n')

      if (!data) return false
      if (data === '[DONE]') {
        onDone()
        return true
      }

      try {
        onEvent(JSON.parse(data) as AgentSSEEvent)
      } catch (error) {
        console.warn('[Agent SSE] 无法解析事件', { data, error })
      }
      return false
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split(/\r?\n\r?\n/)
      buffer = blocks.pop() || ''

      for (const block of blocks) {
        if (processEventBlock(block)) return
      }
    }

    buffer += decoder.decode()
    if (buffer.trim() && processEventBlock(buffer)) return

    onDone()
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') return
    onError(err instanceof Error ? err : new Error(String(err)))
  }
}

// ═══════════════════════════════════════════════════════════════
// AI 助学对话记忆 — 历史对话的增删改查
// ═══════════════════════════════════════════════════════════════

export interface ConversationSummary {
  conversation_id: number
  title: string
  created_at: string
  updated_at: string
}

export interface ConversationDetail extends ConversationSummary {
  stu_id: number
  messages: ChatHistoryItem[]
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('token')
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

/** 创建一条对话记录（标题由 AI 总结首次对话内容生成） */
export async function createConversation(
  firstMessage: string,
  messages: ChatHistoryItem[],
): Promise<{ conversation_id: number; title: string }> {
  const response = await fetch(`${API_BASE}/ai/conversations`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ first_message: firstMessage, messages }),
  })
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }
  return response.json()
}

/** 列出当前登录学生的全部对话 */
export async function listConversations(): Promise<ConversationSummary[]> {
  const response = await fetch(`${API_BASE}/ai/conversations`, {
    method: 'GET',
    headers: authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }
  return response.json()
}

/** 获取当前登录学生的单条对话详情 */
export async function getConversation(conversationId: number): Promise<ConversationDetail> {
  const response = await fetch(`${API_BASE}/ai/conversations/${conversationId}`, {
    method: 'GET',
    headers: authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }
  return response.json()
}

/** 更新当前登录学生的对话内容 */
export async function updateConversation(
  conversationId: number,
  messages: ChatHistoryItem[],
): Promise<{ success: boolean }> {
  const response = await fetch(`${API_BASE}/ai/conversations/${conversationId}`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify({ messages }),
  })
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }
  return response.json()
}

/** 删除当前登录学生的对话 */
export async function deleteConversation(conversationId: number): Promise<{ success: boolean }> {
  const response = await fetch(`${API_BASE}/ai/conversations/${conversationId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }
  return response.json()
}
