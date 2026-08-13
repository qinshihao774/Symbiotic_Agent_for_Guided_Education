import { ref, onUnmounted, computed } from 'vue'
import { submitKgBuild, getKgBuildStatus, type KgBuildStatusResponse } from '@/api/kgPipeline'

export interface KgTask {
  taskId: string
  fileName: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  createdAt: string
  chunks?: number
  nodes?: number
  edges?: number
  error?: string
}

const POLL_INTERVAL = 3000
const MAX_POLL_TIME = 720 * 60 * 1000

export function useKgPipeline() {
  const tasks = ref<KgTask[]>([])
  const submitCount = ref(0)
  const isSubmitting = computed(() => submitCount.value > 0)
  const pollingTimers = ref<Map<string, number>>(new Map())
  const activePolling = new Set<string>()

  async function submitTask(file: File, courseId?: number): Promise<void> {
    submitCount.value++
    try {
      const response = await submitKgBuild(file, courseId)

      const task: KgTask = {
        taskId: response.task_id,
        fileName: file.name,
        status: 'pending',
        createdAt: new Date().toISOString(),
      }

      tasks.value.unshift(task)
      startPolling(task.taskId)
    } finally {
      submitCount.value--
    }
  }

  function startPolling(taskId: string): void {
    const startTime = Date.now()
    let failCount = 0

    activePolling.add(taskId)

    const poll = async () => {
      if (!activePolling.has(taskId)) return

      if (Date.now() - startTime > MAX_POLL_TIME) {
        updateTaskStatus(taskId, 'failed', '处理超时')
        activePolling.delete(taskId)
        return
      }

      try {
        const status = await getKgBuildStatus(taskId)
        failCount = 0
        updateTaskFromResponse(taskId, status)

        if (status.status === 'pending' || status.status === 'processing') {
          if (activePolling.has(taskId)) {
            const timer = window.setTimeout(poll, POLL_INTERVAL)
            pollingTimers.value.set(taskId, timer)
          }
        } else {
          activePolling.delete(taskId)
        }
      } catch {
        failCount++
        const interval = failCount >= 3 ? 10000 : POLL_INTERVAL
        if (activePolling.has(taskId)) {
          const timer = window.setTimeout(poll, interval)
          pollingTimers.value.set(taskId, timer)
        }
      }
    }

    poll()
  }

  function updateTaskStatus(taskId: string, status: KgTask['status'], error?: string): void {
    const task = tasks.value.find(t => t.taskId === taskId)
    if (task) {
      task.status = status
      if (error) task.error = error
    }
  }

  function updateTaskFromResponse(taskId: string, resp: KgBuildStatusResponse): void {
    const task = tasks.value.find(t => t.taskId === taskId)
    if (!task) return
    task.status = resp.status as KgTask['status']
    if (resp.chunks !== undefined) task.chunks = resp.chunks
    if (resp.nodes !== undefined) task.nodes = resp.nodes
    if (resp.edges !== undefined) task.edges = resp.edges
    if (resp.error) task.error = resp.error
  }

  function removeTask(taskId: string): void {
    activePolling.delete(taskId)
    const timer = pollingTimers.value.get(taskId)
    if (timer) {
      window.clearTimeout(timer)
      pollingTimers.value.delete(taskId)
    }
    const index = tasks.value.findIndex(t => t.taskId === taskId)
    if (index > -1) tasks.value.splice(index, 1)
  }

  onUnmounted(() => {
    activePolling.clear()
    pollingTimers.value.forEach(t => window.clearTimeout(t))
    pollingTimers.value.clear()
  })

  return { tasks, isSubmitting, submitTask, removeTask }
}
