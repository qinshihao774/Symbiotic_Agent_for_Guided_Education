import { ref } from 'vue'
import {
  sendQuickMessage,
  sendDeepMessage,
  sendAgentMessage,
  createConversation,
  listConversations,
  getConversation,
  updateConversation,
  deleteConversation,
  type ChatHistoryItem,
  type ChatChunk,
  type AgentSSEEvent,
  type LegacyAgentSSEEvent,
  type SuggestedQuestion,
  type ConversationSummary,
} from '@/api/ai'
import { useSubgraph } from '@/composables/useSubgraph'
import {
  isAgentEventV2,
  type AgentEventV2,
  type AgentRun,
  type AgentStep,
  type AgentStepKind,
} from '@/types/agent'

export type ChatMode = 'quick' | 'deep' | 'agent'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  mode: ChatMode
  content: string
  reasoning?: string
  agentRun?: AgentRun
  suggestedQuestions?: SuggestedQuestion[]
}

export interface KgHitNode {
  nodeId: string
  nodeName: string
  nodeType: string
  graphName: string
}

const TOOL_LABELS: Record<string, string> = {
  search_kg: '搜索课程知识库',
  read_document: '阅读教材资料',
  search_web: '搜索公开资料',
  list_tables: '检查可用学习数据',
  describe_table: '了解数据结构',
  query_postgresql: '查询学习记录',
}

function createId(prefix: string): string {
  const randomId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `${prefix}_${randomId}`
}

function createInitialRun(): AgentRun {
  const now = new Date().toISOString()
  return {
    runId: createId('run'),
    status: 'running',
    phase: 'planning',
    summary: '正在分析问题并选择合适的资料来源',
    startedAt: now,
    lastSeq: 0,
    steps: [{
      id: 'planning',
      kind: 'planning',
      title: '分析任务',
      description: '理解问题并准备执行步骤',
      status: 'running',
      startedAt: now,
    }],
  }
}

function getStep(run: AgentRun, stepId: string): AgentStep | undefined {
  return run.steps.find(step => step.id === stepId)
}

function markRunFinished(run: AgentRun, status: AgentRun['status'], durationMs?: number) {
  run.status = status
  run.finishedAt = new Date().toISOString()
  run.durationMs = durationMs ?? Math.max(0, Date.now() - new Date(run.startedAt).getTime())
  for (const step of run.steps) {
    if (step.status === 'running') {
      step.status = status === 'success' ? 'success' : status
      step.finishedAt = run.finishedAt
      if (step.startedAt && step.durationMs === undefined) {
        step.durationMs = Math.max(0, Date.now() - new Date(step.startedAt).getTime())
      }
    }
  }
}

export function useChat() {
  const messages = ref<ChatMessage[]>([])
  const loading = ref(false)
  const streamingContent = ref('')
  const streamingReasoning = ref('')
  const chatMode = ref<ChatMode>('agent')
  const kgGraphIds = ref<number[]>([])
  const kgHitNodes = ref<KgHitNode[]>([])
  const activeKgHitIndex = ref(0)
  const subgraphPanelVisible = ref(false)
  const suggesting = ref(false)
  const currentController = ref<AbortController | null>(null)
  const { subgraphs, subgraphLoading, subgraphErrors, extractSubgraphs, clearSubgraphs } = useSubgraph()

  // ── 对话记忆状态 ──
  const conversationId = ref<number | null>(null)
  const conversations = ref<ConversationSummary[]>([])
  const conversationsLoading = ref(false)
  const conversationSaving = ref(false)

  function findMessage(messageId: string) {
    return messages.value.find(message => message.id === messageId)
  }

  function handleKnowledgeHit(data: {
    node_id?: string
    node_name?: string
    node_type?: string
    graph_name?: string
  }) {
    if (!data.node_id || !data.node_name || !data.node_type || !data.graph_name) return
    const hitNode: KgHitNode = {
      nodeId: data.node_id,
      nodeName: data.node_name,
      nodeType: data.node_type,
      graphName: data.graph_name,
    }
    const existingIndex = kgHitNodes.value.findIndex(node =>
      node.nodeId === hitNode.nodeId && node.graphName === hitNode.graphName,
    )
    const index = existingIndex >= 0 ? existingIndex : kgHitNodes.value.push(hitNode) - 1
    activeKgHitIndex.value = index
    subgraphPanelVisible.value = true
    if (!subgraphs.value[index] && !subgraphLoading.value[index]) extractSubgraphs(hitNode, index)
    suggesting.value = true
  }

  function applyV2Event(message: ChatMessage, event: AgentEventV2) {
    const run = message.agentRun ?? createInitialRun()
    message.agentRun = run

    if (event.seq > 0 && event.seq <= run.lastSeq) return
    run.lastSeq = Math.max(run.lastSeq, event.seq)

    const { data } = event
    switch (event.event) {
      case 'run.started':
        run.runId = event.run_id
        run.status = 'running'
        run.startedAt = event.timestamp || run.startedAt
        if (data.summary) run.summary = data.summary
        break
      case 'plan.updated':
        if (data.summary) run.summary = data.summary
        for (const planned of data.steps ?? []) {
          if (!getStep(run, planned.id)) {
            run.steps.push({ ...planned, status: 'pending' })
          }
        }
        break
      case 'step.started': {
        if (!data.step) break
        const existing = getStep(run, data.step.id)
        const startedAt = data.step.started_at || event.timestamp
        const nextStep: AgentStep = {
          id: data.step.id,
          kind: data.step.kind,
          title: data.step.title,
          description: data.step.description,
          status: 'running',
          startedAt,
          tool: data.step.tool ? {
            name: data.step.tool.name,
            displayName: data.step.tool.display_name,
            purpose: data.step.tool.purpose,
            inputSummary: data.step.tool.input_summary,
          } : undefined,
        }
        if (existing) Object.assign(existing, nextStep)
        else run.steps.push(nextStep)
        run.phase = data.step.kind
        break
      }
      case 'step.completed': {
        if (!data.step_id) break
        const step = getStep(run, data.step_id)
        if (!step) break
        step.status = 'success'
        step.finishedAt = event.timestamp
        step.durationMs = data.duration_ms
        if (step.tool && data.result) {
          step.tool.resultSummary = data.result.summary
          step.tool.metrics = data.result.metrics
          step.tool.documentExcerpt = data.result.document_excerpt
        }
        break
      }
      case 'step.failed': {
        if (!data.step_id) break
        const step = getStep(run, data.step_id)
        if (!step) break
        step.status = 'failed'
        step.finishedAt = event.timestamp
        step.durationMs = data.duration_ms
        step.error = data.error
        break
      }
      case 'answer.delta':
        if (data.delta) message.content += data.delta
        break
      case 'knowledge.hit':
        handleKnowledgeHit(data)
        break
      case 'suggestions.ready':
        suggesting.value = false
        message.suggestedQuestions = data.questions
        break
      case 'run.completed':
        markRunFinished(run, 'success', data.duration_ms)
        break
      case 'run.failed':
        markRunFinished(run, 'failed', data.duration_ms)
        if (!message.content) message.content = `⚠️ ${data.error?.message || '智能体执行失败，请稍后重试。'}`
        break
      case 'run.cancelled':
        markRunFinished(run, 'cancelled', data.duration_ms)
        break
    }
  }

  function safeLegacyQuery(query?: string): string | undefined {
    if (!query) return undefined
    if (query.includes('{') || query.includes('SELECT ') || query.length > 120) return undefined
    return query
  }

  function applyLegacyEvent(message: ChatMessage, event: LegacyAgentSSEEvent) {
    const run = message.agentRun ?? createInitialRun()
    message.agentRun = run

    if (event.type === 'tool_used') {
      const planning = getStep(run, 'planning')
      if (planning?.status === 'running') {
        planning.status = 'success'
        planning.finishedAt = new Date().toISOString()
      }
      const query = safeLegacyQuery(event.query)
      run.phase = 'tool'
      run.steps.push({
        id: createId('legacy-tool'),
        kind: 'tool',
        title: TOOL_LABELS[event.tool || ''] || '调用学习工具',
        description: '获取回答所需的可靠信息',
        status: 'running',
        startedAt: new Date().toISOString(),
        tool: {
          name: event.tool || 'unknown',
          displayName: TOOL_LABELS[event.tool || ''] || '学习工具',
          purpose: '获取回答所需的可靠信息',
          inputSummary: query ? [{ label: '关键词', value: query }] : undefined,
        },
      })
    } else if (event.type === 'tool_result') {
      const step = [...run.steps].reverse().find(item => item.kind === 'tool' && item.status === 'running')
      if (step) {
        const failed = /执行出错|失败|超时/.test(event.preview || '')
        step.status = failed ? 'failed' : 'success'
        step.finishedAt = new Date().toISOString()
        if (step.startedAt) step.durationMs = Date.now() - new Date(step.startedAt).getTime()
        if (step.tool) step.tool.resultSummary = failed ? '工具执行未成功' : (event.preview || '已获取相关结果')
        if (failed) step.error = { message: '工具执行未成功，请稍后重试。', retryable: true }
      }
    } else if (event.type === 'content') {
      if (run.phase !== 'generating') {
        run.phase = 'generating'
        run.steps.push({
          id: 'generating',
          kind: 'generating',
          title: '生成最终回答',
          description: '根据已获取的信息整理回答',
          status: 'running',
          startedAt: new Date().toISOString(),
        })
      }
      message.content += event.content || ''
    } else if (event.type === 'error') {
      markRunFinished(run, 'failed')
      message.content = `⚠️ 出错了：${event.content || '智能体执行失败'}`
    } else if (event.type === 'kg_hit') {
      handleKnowledgeHit(event)
    } else if (event.type === 'suggested_questions') {
      suggesting.value = false
      message.suggestedQuestions = event.questions
    } else if (event.type === 'done') {
      markRunFinished(run, 'success')
    }
  }

  function applyAgentEvent(messageId: string, event: AgentSSEEvent) {
    const message = findMessage(messageId)
    if (!message) return
    if (isAgentEventV2(event)) applyV2Event(message, event)
    else applyLegacyEvent(message, event)
  }

  // ═══════════════════════════════════════════════════════════════
  // 对话记忆 — 历史对话的保存 / 加载 / 删除
  // ═══════════════════════════════════════════════════════════════

  function toHistoryItems(): ChatHistoryItem[] {
    return messages.value
      .filter(message => message.content)
      .map(message => ({ role: message.role, content: message.content }))
  }

  /** 判断当前对话是否已有一轮完整问答（用户 + 助手均有内容） */
  function hasCompleteExchange(): boolean {
    const userCount = messages.value.filter(m => m.role === 'user' && m.content).length
    const assistantCount = messages.value.filter(m => m.role === 'assistant' && m.content).length
    return userCount > 0 && assistantCount > 0
  }

  /** 保存当前对话：无 conversationId 则创建，否则更新（空对话不存储） */
  async function persistConversation() {
    if (conversationSaving.value) return
    if (!hasCompleteExchange()) return
    const history = toHistoryItems()
    if (history.length === 0) return

    conversationSaving.value = true
    try {
      if (conversationId.value === null) {
        const firstUserMessage = messages.value.find(m => m.role === 'user' && m.content)?.content || ''
        const created = await createConversation(firstUserMessage, history)
        conversationId.value = created.conversation_id
        await refreshConversations()
      } else {
        await updateConversation(conversationId.value, history)
        await refreshConversations()
      }
    } catch (err) {
      console.warn('[对话记忆] 保存对话失败', err)
    } finally {
      conversationSaving.value = false
    }
  }

  /** 刷新侧边栏对话列表 */
  async function refreshConversations() {
    try {
      conversations.value = await listConversations()
    } catch (err) {
      console.warn('[对话记忆] 加载对话列表失败', err)
    }
  }

  /** 加载对话列表（页面初始化时调用） */
  async function loadConversations() {
    conversationsLoading.value = true
    try {
      conversations.value = await listConversations()
    } catch (err) {
      console.warn('[对话记忆] 加载对话列表失败', err)
    } finally {
      conversationsLoading.value = false
    }
  }

  /** 加载某条历史对话并恢复为当前对话 */
  async function loadConversation(id: number) {
    try {
      const detail = await getConversation(id)
      conversationId.value = detail.conversation_id
      messages.value = detail.messages.map((item, index) => ({
        id: createId('msg'),
        role: item.role as 'user' | 'assistant',
        mode: 'agent',
        content: item.content,
      }))
      kgHitNodes.value = []
      activeKgHitIndex.value = 0
      subgraphPanelVisible.value = false
      clearSubgraphs()
    } catch (err) {
      console.warn('[对话记忆] 加载对话失败', err)
    }
  }

  /** 新建对话：清空当前消息并重置 conversationId */
  function newConversation() {
    cancelCurrentRun()
    messages.value = []
    conversationId.value = null
    kgHitNodes.value = []
    activeKgHitIndex.value = 0
    subgraphPanelVisible.value = false
    clearSubgraphs()
  }

  /** 删除某条历史对话 */
  async function deleteConversationById(id: number) {
    try {
      await deleteConversation(id)
      if (conversationId.value === id) {
        conversationId.value = null
        messages.value = []
      }
      await refreshConversations()
    } catch (err) {
      console.warn('[对话记忆] 删除对话失败', err)
    }
  }

  async function sendMessage(content: string) {
    if (!content.trim() || loading.value) return

    const mode = chatMode.value
    const userMessage: ChatMessage = {
      id: createId('msg'),
      role: 'user',
      mode,
      content,
    }
    messages.value.push(userMessage)

    const history: ChatHistoryItem[] = messages.value
      .slice(0, -1)
      .filter(message => message.content)
      .map(message => ({ role: message.role, content: message.content }))

    loading.value = true
    suggesting.value = false
    streamingContent.value = ''
    streamingReasoning.value = ''
    const controller = new AbortController()
    currentController.value = controller

    const assistantMessage: ChatMessage = {
      id: createId('msg'),
      role: 'assistant',
      mode,
      content: '',
      reasoning: '',
      agentRun: mode === 'agent' ? createInitialRun() : undefined,
    }
    messages.value.push(assistantMessage)

    if (mode === 'agent') {
      await sendAgentMessage(
        content,
        history,
        kgGraphIds.value,
        assistantMessage.id,
        event => applyAgentEvent(assistantMessage.id, event),
        () => {
          const message = findMessage(assistantMessage.id)
          if (message?.agentRun?.status === 'running') markRunFinished(message.agentRun, 'success')
          loading.value = false
          suggesting.value = false
          currentController.value = null
          persistConversation()
        },
        (err) => {
          const message = findMessage(assistantMessage.id)
          if (message) {
            message.content = `⚠️ 出错了：${err.message}`
            if (message.agentRun) markRunFinished(message.agentRun, 'failed')
          }
          loading.value = false
          suggesting.value = false
          currentController.value = null
          persistConversation()
        },
        controller.signal,
      )
      return
    }

    const sendFn = mode === 'deep' ? sendDeepMessage : sendQuickMessage
    await sendFn(
      content,
      history,
      (chunk: ChatChunk) => {
        const message = findMessage(assistantMessage.id)
        if (!message) return
        if (chunk.reasoning) {
          streamingReasoning.value += chunk.reasoning
          message.reasoning = streamingReasoning.value
        }
        if (chunk.content) {
          streamingContent.value += chunk.content
          message.content = streamingContent.value
        }
      },
      () => {
        loading.value = false
        streamingContent.value = ''
        streamingReasoning.value = ''
        currentController.value = null
        persistConversation()
      },
      (err) => {
        const message = findMessage(assistantMessage.id)
        if (message) message.content = `⚠️ 出错了：${err.message}`
        loading.value = false
        currentController.value = null
        persistConversation()
      },
    )
  }

  function cancelCurrentRun() {
    currentController.value?.abort()
    currentController.value = null
    const activeMessage = [...messages.value].reverse().find(message => message.agentRun?.status === 'running')
    if (activeMessage?.agentRun) markRunFinished(activeMessage.agentRun, 'cancelled')
    loading.value = false
    suggesting.value = false
  }

  function closeSubgraphPanel() {
    subgraphPanelVisible.value = false
  }

  function openSubgraphPanel() {
    subgraphPanelVisible.value = true
  }

  function selectKgHitPage(index: number) {
    if (index >= 0 && index < kgHitNodes.value.length) activeKgHitIndex.value = index
  }

  function selectSuggestedQuestion(question: SuggestedQuestion) {
    sendMessage(question.text)
  }

  function clearMessages() {
    cancelCurrentRun()
    messages.value = []
    conversationId.value = null
    kgHitNodes.value = []
    activeKgHitIndex.value = 0
    subgraphPanelVisible.value = false
    clearSubgraphs()
  }

  return {
    messages,
    loading,
    sendMessage,
    cancelCurrentRun,
    clearMessages,
    chatMode,
    kgGraphIds,
    kgHitNodes,
    activeKgHitIndex,
    subgraphPanelVisible,
    closeSubgraphPanel,
    openSubgraphPanel,
    selectKgHitPage,
    subgraphs,
    subgraphLoading,
    subgraphErrors,
    extractSubgraphs,
    suggesting,
    selectSuggestedQuestion,
    // 对话记忆
    conversationId,
    conversations,
    conversationsLoading,
    conversationSaving,
    loadConversations,
    loadConversation,
    newConversation,
    deleteConversationById,
  }
}
