<template>
  <BorderGlow class="interactive-page" background-color="transparent">
    <div class="glass-card page-container">
      <h2 class="page-title">互动专区</h2>

      <!-- 列表区域，独立滚动 -->
      <div class="list-container scroll-area">
        <el-table
          :data="messageList"
          style="width: 100%; background: transparent;"
          row-class-name="interactive-row"
          header-row-class-name="interactive-header"
          @row-dblclick="handleRowDblclick"
        >
          <el-table-column prop="stu_name" label="学生" width="120" />
          <el-table-column prop="msg_texts" label="问题、对话、描述等" min-width="300">
            <template #default="scope">
              <span class="text-truncate">{{ scope.row.msg_texts }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="answer_num" label="回答数" width="120">
            <template #default="scope">
              回答数×{{ scope.row.answer_num }}
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间" width="170" align="right">
            <template #default="scope">
              {{ formatTime(scope.row.created_at) }}
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 分页区域（上移，位于发布输入框上方） -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          class="custom-pagination"
          @current-change="loadMessages"
        />
      </div>

      <!-- 发布消息输入框（位于分页按钮下方） -->
      <div class="publish-container">
        <el-input
          v-model="publishText"
          type="textarea"
          :rows="2"
          placeholder="请输入你要发布的问题或对话内容..."
          maxlength="500"
          show-word-limit
          resize="none"
          class="publish-input"
        />
        <div class="publish-actions">
          <el-button type="primary" class="publish-btn" :loading="publishing" @click="handlePublish">
            发布消息
          </el-button>
        </div>
      </div>
    </div>
  </BorderGlow>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import BorderGlow from '@/components/BorderGlow.vue'
import { fetchMessages, publishMessage, type InteractionMessage } from '@/api/interaction'

const router = useRouter()

const messageList = ref<InteractionMessage[]>([])
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

const publishText = ref('')
const publishing = ref(false)

/** 将时间格式化为 YYYY-MM-DD HH:mm:ss */
const formatTime = (value: string | null | undefined): string => {
  if (!value) return ''
  const date = new Date(value)
  if (isNaN(date.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  )
}

const loadMessages = async () => {
  try {
    const data = await fetchMessages(currentPage.value, pageSize.value)
    messageList.value = data.items
    total.value = data.total
  } catch (e) {
    ElMessage.error('加载互动消息失败')
  }
}

const handlePublish = async () => {
  const text = publishText.value.trim()
  if (!text) {
    ElMessage.warning('请输入发布内容')
    return
  }
  publishing.value = true
  try {
    await publishMessage(text)
    ElMessage.success('发布成功')
    publishText.value = ''
    // 发布后回到第一页并刷新列表
    currentPage.value = 1
    await loadMessages()
  } catch (e) {
    ElMessage.error('发布失败')
  } finally {
    publishing.value = false
  }
}

const handleRowDblclick = (row: InteractionMessage) => {
  router.push(`/student/interactive/${row.msg_id}`)
}

onMounted(() => {
  loadMessages()
})
</script>

<style scoped>
.interactive-page {
  color: #000;
  height: calc(100vh - 170px);
  margin: 20px;
}

.page-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #e5e8e4;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.5);
}

.page-title {
  margin: 0 0 16px 0;
  font-size: 1.2rem;
  font-weight: bold;
  color: #000;
  flex-shrink: 0;
}

.list-container {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.scroll-area {
  overflow-y: auto;
}

/* 自定义滚动条 */
.scroll-area::-webkit-scrollbar {
  width: 6px;
}
.scroll-area::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.02);
  border-radius: 4px;
}
.scroll-area::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 4px;
}
.scroll-area::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.25);
}

/* 覆盖 el-table 的默认背景使其透明以适配玻璃态 */
:deep(.el-table) {
  background-color: transparent !important;
  --el-table-border-color: rgba(0, 0, 0, 0.1);
  --el-table-header-bg-color: rgba(255, 255, 255, 0.3);
  --el-table-tr-bg-color: transparent;
  color: #000;
}

:deep(.el-table th.el-table__cell) {
  background-color: rgba(255, 255, 255, 0.4) !important;
  color: #000;
  font-weight: bold;
}

:deep(.el-table tr) {
  background-color: transparent !important;
  cursor: pointer;
  transition: background-color 0.2s;
}

:deep(.el-table tr:hover > td.el-table__cell) {
  background-color: rgba(255, 255, 255, 0.5) !important;
}

.text-truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: center;
  flex-shrink: 0;
}

/* 分页组件样式覆盖 */
:deep(.custom-pagination .el-pager li) {
  background: transparent;
  color: #000;
}
:deep(.custom-pagination .el-pager li.is-active) {
  font-weight: bold;
  color: #2980b9;
}
:deep(.custom-pagination button) {
  background: transparent !important;
  color: #000;
}

/* 发布消息区域 */
.publish-container {
  margin-top: 16px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.publish-input {
  width: 100%;
}

.publish-input :deep(.el-textarea__inner) {
  background: rgba(255, 255, 255, 0.5);
  color: #000;
  border-radius: 8px;
}

.publish-actions {
  display: flex;
  justify-content: flex-end;
}

.publish-btn {
  background: #2980b9;
  border-color: #2980b9;
}
</style>
