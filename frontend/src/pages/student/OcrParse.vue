<!-- frontend/src/pages/student/OcrParse.vue -->
<template>
  <BorderGlow class="ocr-page" background-color="transparent">
    <h1 class="page-title">OCR 文档解析</h1>

    <!-- 上传区域 -->
    <el-card class="upload-card">
      <template #header>
        <span>上传文件</span>
      </template>

      <el-upload
        v-model:file-list="fileList"
        action="#"
        :auto-upload="false"
        :before-upload="beforeUpload"
        :limit="5"
        multiple
        drag
        accept=".pdf,.jpg,.jpeg,.png"
        class="upload-area"
      >
        <el-icon class="upload-icon"><upload-filled /></el-icon>
        <div class="upload-text">
          拖拽文件到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="upload-tip">
            支持 PDF、JPG、PNG 格式，单文件最大 50MB，单次最多 5 个文件
          </div>
        </template>
      </el-upload>
    </el-card>

    <!-- 解析参数 -->
    <el-card class="params-card">
      <template #header>
        <span>解析参数</span>
      </template>

      <el-form :model="params" label-width="120px">
        <el-form-item label="文档语言">
          <el-select v-model="params.lang" placeholder="请选择语言">
            <el-option label="中文" value="ch" />
            <el-option label="英文" value="en" />
            <el-option label="日文" value="japan" />
            <el-option label="韩文" value="korean" />
          </el-select>
        </el-form-item>

        <el-form-item label="公式识别">
          <el-switch v-model="params.formula_enable" />
        </el-form-item>

        <el-form-item label="表格识别">
          <el-switch v-model="params.table_enable" />
        </el-form-item>

        <el-form-item label="页码范围">
          <el-input-number v-model="params.start_page_id" :min="0" placeholder="起始页" />
          <span class="page-separator">至</span>
          <el-input-number v-model="params.end_page_id" :min="-1" placeholder="结束页（-1 表示全部）" />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 提交按钮 -->
    <div class="submit-area">
      <StarBorder as="div" color="#409eff" speed="3s">
        <el-button
          type="primary"
          size="large"
          :loading="isSubmitting"
          :disabled="fileList.length === 0"
          @click="handleSubmit"
        >
          开始解析
        </el-button>
      </StarBorder>
    </div>

    <!-- 任务列表 -->
    <el-card v-if="tasks.length > 0" class="tasks-card">
      <template #header>
        <span>任务列表</span>
      </template>

      <div class="task-list">
        <div
          v-for="task in tasks"
          :key="task.taskId"
          class="task-item"
          :class="`task-${task.status}`"
        >
          <div class="task-header">
            <span class="task-files">{{ task.fileNames.join(', ') }}</span>
            <el-tag
              :type="getStatusType(task.status)"
              size="small"
            >
              {{ getStatusLabel(task.status) }}
            </el-tag>
          </div>

          <!-- 处理中状态 -->
          <div v-if="task.status === 'pending' || task.status === 'processing'" class="task-progress">
            <el-progress :percentage="getProgress(task)" :status="task.status === 'processing' ? '' : 'warning'" />
            <span class="task-time">已耗时: {{ getElapsedTime(task) }}</span>
          </div>

          <!-- 完成状态 -->
          <div v-else-if="task.status === 'completed'" class="task-stats">
            <div class="stats-grid">
              <div class="stat-item">
                <span class="stat-label">文件数</span>
                <span class="stat-value">{{ task.fileNames.length }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">处理耗时</span>
                <span class="stat-value">{{ getProcessingTime(task) }}</span>
              </div>
            </div>
            <el-alert title="处理完成" type="success" :closable="false" show-icon />

            <!-- 下载按钮 -->
            <div class="download-area">
              <el-button
                type="primary"
                :icon="Download"
                @click="downloadResult(task)"
              >
                下载解析结果
              </el-button>
            </div>
          </div>

          <!-- 失败状态 -->
          <div v-else-if="task.status === 'failed'" class="task-error">
            <el-alert
              :title="task.error || '处理失败'"
              type="error"
              :closable="false"
              show-icon
            />
              <StarBorder as="div" color="#909399" speed="4s">
                <el-button size="small" @click="handleRetry(task)">
                  重新上传
                </el-button>
              </StarBorder>
            </div>

            <!-- 移除按钮 -->
            <StarBorder as="div" color="#f56c6c" speed="5s">
              <el-button
                type="danger"
                size="small"
                text
                @click="removeTask(task.taskId)"
              >
                移除
              </el-button>
            </StarBorder>
          </div>
      </div>
    </el-card>
  </BorderGlow>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { UploadFilled, Download } from '@element-plus/icons-vue'
import { getOcrTaskResultDownloadUrl } from '@/api/ocr'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { useOcr, type OcrTask } from '@/composables/useOcr'
import type { OcrParams } from '@/api/ocr'
import StarBorder from '@/components/StarBorder.vue'
import BorderGlow from '@/components/BorderGlow.vue'

const { tasks, isSubmitting, submitTask, removeTask } = useOcr()

const fileList = ref<UploadFile[]>([])

const params = ref<OcrParams>({
  lang: 'ch',
  formula_enable: true,
  table_enable: true,
  start_page_id: 0,
  end_page_id: -1,
})

// 文件上传前校验
function beforeUpload(file: File): boolean {
  const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png']
  const allowedExts = ['.pdf', '.jpg', '.jpeg', '.png']

  const isValidType = allowedTypes.includes(file.type) ||
    allowedExts.some(ext => file.name.toLowerCase().endsWith(ext))

  if (!isValidType) {
    ElMessage.error('仅支持 PDF、JPG、PNG 格式')
    return false
  }

  const isValidSize = file.size <= 50 * 1024 * 1024
  if (!isValidSize) {
    ElMessage.error('单文件大小不能超过 50MB')
    return false
  }

  if (fileList.value.length >= 5) {
    ElMessage.error('单次最多上传 5 个文件')
    return false
  }

  return true
}

async function handleSubmit(): Promise<void> {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }

  const files = fileList.value
    .filter(f => f.raw)
    .map(f => f.raw as File)

  if (files.length === 0) {
    ElMessage.warning('文件读取失败，请重新选择')
    return
  }

  try {
    await submitTask(files, params.value)
    ElMessage.success('任务已提交')
    fileList.value = [] // 清空文件列表
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '提交失败')
  }
}

function handleRetry(task: OcrTask): void {
  // 重新上传逻辑：移除旧任务，重新提交
  removeTask(task.taskId)
  ElMessage.info('请重新选择文件并提交')
}

function downloadResult(task: OcrTask): void {
  const url = getOcrTaskResultDownloadUrl(task.taskId)
  const link = document.createElement('a')
  link.href = url
  link.download = `${task.fileNames[0] || task.taskId}.zip`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

function getStatusType(status: string): string {
  const map: Record<string, string> = {
    pending: 'warning',
    processing: 'info',
    completed: 'success',
    failed: 'danger',
  }
  return map[status] || 'info'
}

function getStatusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '等待中',
    processing: '处理中',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}

function getProgress(task: OcrTask): number {
  // 简化的进度计算
  if (task.status === 'pending') return 10
  if (task.status === 'processing') return 50
  return 0
}

function getElapsedTime(task: OcrTask): string {
  const start = new Date(task.createdAt).getTime()
  const now = Date.now()
  const diff = Math.floor((now - start) / 1000)

  if (diff < 60) return `${diff}秒`
  if (diff < 3600) return `${Math.floor(diff / 60)}分${diff % 60}秒`
  return `${Math.floor(diff / 3600)}时${Math.floor((diff % 3600) / 60)}分`
}

function getProcessingTime(task: OcrTask): string {
  if (!task.startedAt || !task.completedAt) return '未知'

  const start = new Date(task.startedAt).getTime()
  const end = new Date(task.completedAt).getTime()
  const diff = Math.floor((end - start) / 1000)

  if (diff < 60) return `${diff}秒`
  if (diff < 3600) return `${Math.floor(diff / 60)}分${diff % 60}秒`
  return `${Math.floor(diff / 3600)}时${Math.floor((diff % 3600) / 60)}分`
}
</script>

<style scoped>
.ocr-page { padding: 20px; max-width: 800px; margin: 20px auto; color: #eceef0; min-height: calc(100vh - 170px); }
.page-title { font-size: 24px; margin-bottom: 20px; text-align: center; }
:deep(.el-card) { background: rgba(255, 255, 255, 0.4); border-color: rgba(0, 0, 0, 0.1); color: #1f2937; backdrop-filter: blur(10px); }
:deep(.el-card__header) { border-bottom-color: rgba(0, 0, 0, 0.05); }
:deep(.el-form-item__label) { color: #1f2937; }
:deep(.el-upload-dragger) { background: rgba(255, 255, 255, 0.5); border-color: rgba(0, 0, 0, 0.1); }
:deep(.el-upload-dragger:hover) { border-color: #409eff; }
.upload-card, .params-card, .tasks-card { margin-bottom: 20px; }
.upload-area { width: 100%; }
.upload-icon { font-size: 48px; color: #9ca3af; margin-bottom: 10px; }
.upload-text { color: #4b5563; }
.upload-text em { color: #409eff; font-style: normal; }
.upload-tip { font-size: 12px; color: #6b7280; margin-top: 10px; }
.submit-area { text-align: center; margin-bottom: 20px; }
.page-separator { margin: 0 10px; color: #9ca3af; }
.task-list { display: flex; flex-direction: column; gap: 12px; }
.task-item { border: 1px solid rgba(0, 0, 0, 0.05); border-radius: 4px; padding: 12px; background: rgba(255, 255, 255, 0.3); }
.task-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.task-files { font-weight: bold; color: #1f2937; word-break: break-all; }
.task-progress { margin-top: 10px; }
.task-time { font-size: 12px; color: #6b7280; margin-top: 5px; }
.task-stats { margin-top: 10px; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-bottom: 10px; }
.stat-item { display: flex; flex-direction: column; align-items: center; padding: 8px; background: rgba(0, 0, 0, 0.02); border-radius: 4px; }
.stat-label { font-size: 12px; color: #6b7280; }
.stat-value { font-size: 18px; font-weight: bold; color: #1f2937; }
.task-error { margin-top: 10px; }
.download-area { margin-top: 12px; text-align: center; }
</style>
