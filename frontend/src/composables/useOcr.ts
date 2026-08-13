// frontend/src/composables/useOcr.ts
import { ref, onUnmounted, computed } from 'vue'
import { submitOcrTask, getOcrTaskStatus, type OcrParams, type TaskStatusResponse } from '@/api/ocr'

export interface OcrTask {
  taskId: string
  fileNames: string[]
  status: 'pending' | 'processing' | 'completed' | 'failed'
  createdAt: string
  startedAt?: string
  completedAt?: string
  error?: string
}

const POLL_INTERVAL = 3000 // 3 秒
const MAX_POLL_TIME = 10 * 60 * 1000 // 10 分钟

export function useOcr() {
  const tasks = ref<OcrTask[]>([])
  const submitCount = ref(0)
  const isSubmitting = computed(() => submitCount.value > 0)
  const pollingTimers = ref<Map<string, number>>(new Map())
  const activePolling = new Set<string>()

  /**
   * 提交 OCR 任务
   */
  async function submitTask(files: File[], params: OcrParams): Promise<void> {
    submitCount.value++
    try {
      const response = await submitOcrTask(files, params)

      const task: OcrTask = {
        taskId: response.task_id,
        fileNames: response.file_names ?? files.map(f => f.name),
        status: 'pending',
        createdAt: response.created_at ?? new Date().toISOString(),
      }

      tasks.value.unshift(task)

      // 开始轮询
      startPolling(task.taskId)
    } finally {
      submitCount.value--
    }
  }

  /**
   * 开始轮询任务状态
   */
  function startPolling(taskId: string): void {
    const startTime = Date.now()
    let failCount = 0

    activePolling.add(taskId)

    const poll = async () => {
      // 检查是否还在活跃轮询列表中
      if (!activePolling.has(taskId)) {
        return
      }

      // 检查是否超时
      if (Date.now() - startTime > MAX_POLL_TIME) {
        updateTaskStatus(taskId, 'failed', '处理超时，请稍后刷新页面查看结果')
        activePolling.delete(taskId)
        return
      }

      try {
        const status = await getOcrTaskStatus(taskId)
        failCount = 0

        updateTaskFromResponse(taskId, status)

        // 如果任务还在进行中，继续轮询
        if (status.status === 'pending' || status.status === 'processing') {
          if (activePolling.has(taskId)) {
            const timer = window.setTimeout(poll, POLL_INTERVAL)
            pollingTimers.value.set(taskId, timer)
          }
        } else {
          // 任务完成，从活跃轮询列表中移除
          activePolling.delete(taskId)
        }
      } catch (error) {
        failCount++

        // 连续失败 3 次后延长轮询间隔
        const interval = failCount >= 3 ? 10000 : POLL_INTERVAL
        if (activePolling.has(taskId)) {
          const timer = window.setTimeout(poll, interval)
          pollingTimers.value.set(taskId, timer)
        }
      }
    }

    // 立即开始第一次轮询
    poll()
  }

  /**
   * 更新任务状态
   */
  function updateTaskStatus(taskId: string, status: OcrTask['status'], error?: string): void {
    const task = tasks.value.find(t => t.taskId === taskId)
    if (task) {
      task.status = status
      if (error) task.error = error
    }
  }

  /**
   * 从响应更新任务
   */
  function updateTaskFromResponse(taskId: string, status: TaskStatusResponse): void {
    const task = tasks.value.find(t => t.taskId === taskId)
    if (!task) return

    task.status = status.status as OcrTask['status']
    task.fileNames = status.file_names ?? task.fileNames
    task.createdAt = status.created_at ?? task.createdAt
    task.startedAt = status.started_at
    task.completedAt = status.completed_at
    task.error = status.error
  }

  /**
   * 移除任务
   */
  function removeTask(taskId: string): void {
    // 停止轮询
    activePolling.delete(taskId)

    // 清除轮询定时器
    const timer = pollingTimers.value.get(taskId)
    if (timer) {
      window.clearTimeout(timer)
      pollingTimers.value.delete(taskId)
    }

    // 从列表中移除
    const index = tasks.value.findIndex(t => t.taskId === taskId)
    if (index > -1) {
      tasks.value.splice(index, 1)
    }
  }

  // 组件卸载时清理所有定时器
  onUnmounted(() => {
    activePolling.clear()

    pollingTimers.value.forEach((timer) => {
      window.clearTimeout(timer)
    })
    pollingTimers.value.clear()
  })

  return {
    tasks,
    isSubmitting,
    submitTask,
    removeTask,
  }
}
