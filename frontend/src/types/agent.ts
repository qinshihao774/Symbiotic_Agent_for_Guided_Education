export type AgentRunStatus = 'running' | 'success' | 'failed' | 'cancelled'

export type AgentStepStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled'

export type AgentStepKind = 'planning' | 'tool' | 'processing' | 'generating' | 'suggesting'

export interface AgentToolField {
  label: string
  value: string
}

export interface AgentToolPresentation {
  name: string
  displayName: string
  purpose?: string
  inputSummary?: AgentToolField[]
  resultSummary?: string
  documentExcerpt?: string
  metrics?: Record<string, number | string>
}

export interface AgentStepError {
  message: string
  code?: string
  retryable: boolean
}

export interface AgentStep {
  id: string
  kind: AgentStepKind
  title: string
  description?: string
  status: AgentStepStatus
  startedAt?: string
  finishedAt?: string
  durationMs?: number
  tool?: AgentToolPresentation
  error?: AgentStepError
}

export interface AgentRun {
  runId: string
  status: AgentRunStatus
  phase: AgentStepKind
  summary?: string
  steps: AgentStep[]
  startedAt: string
  finishedAt?: string
  durationMs?: number
  lastSeq: number
}

export type AgentEventName =
  | 'run.started'
  | 'plan.updated'
  | 'step.started'
  | 'step.completed'
  | 'step.failed'
  | 'answer.delta'
  | 'knowledge.hit'
  | 'suggestions.ready'
  | 'run.completed'
  | 'run.failed'
  | 'run.cancelled'

export interface AgentStepPayload {
  id: string
  kind: AgentStepKind
  title: string
  description?: string
  status?: AgentStepStatus
  started_at?: string
  tool?: {
    name: string
    display_name: string
    purpose?: string
    input_summary?: AgentToolField[]
  }
}

export interface AgentEventData {
  summary?: string
  steps?: Array<Pick<AgentStepPayload, 'id' | 'kind' | 'title' | 'description'>>
  step?: AgentStepPayload
  step_id?: string
  duration_ms?: number
  delta?: string
  result?: {
    summary: string
    metrics?: Record<string, number | string>
    document_excerpt?: string
  }
  error?: AgentStepError
  node_id?: string
  node_name?: string
  node_type?: string
  graph_name?: string
  questions?: Array<{
    text: string
    node_id: string
    node_name: string
    node_type: string
    relation: 'upstream' | 'downstream' | 'both'
  }>
}

export interface AgentEventV2 {
  version: 2
  event: AgentEventName
  event_id: string
  run_id: string
  message_id: string
  seq: number
  timestamp: string
  data: AgentEventData
}

export function isAgentEventV2(event: unknown): event is AgentEventV2 {
  if (!event || typeof event !== 'object') return false
  const candidate = event as Partial<AgentEventV2>
  return candidate.version === 2 && typeof candidate.event === 'string'
}
