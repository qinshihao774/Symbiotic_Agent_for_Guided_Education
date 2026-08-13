<template>
  <BorderGlow class="interactive-detail-page" background-color="transparent">
    <div class="glass-card page-container">
      <!-- 顶部返回与标题 -->
      <div class="header-actions">
        <el-button link @click="goBack" class="back-btn">
          <el-icon><ArrowLeft /></el-icon> 返回互动专区
        </el-button>
        <h2 class="page-title">互动详情</h2>
      </div>

      <!-- 上半部分：问题区 -->
      <div class="section-container question-section">
        <h3 class="section-title">问题区:</h3>
        <div class="scroll-area">
          <div class="post-content">
            <p v-if="message">
              <strong>{{ message.stu_name || '学生' }}:</strong> {{ message.msg_texts }}
            </p>
            <p v-else class="mock-text">加载中...</p>
          </div>
          <div class="spacer"></div>
        </div>
      </div>

      <!-- 分割线 -->
      <div class="divider"></div>

      <!-- 下半部分：答疑区 -->
      <div class="section-container answer-section">
        <h3 class="section-title">答疑区:</h3>
        <div class="scroll-area">
          <div class="reply-list">
            <div v-if="answers.length === 0" class="reply-item">
              <p class="mock-text">暂无回答，快来抢答吧~</p>
            </div>
            <div v-for="answer in answers" :key="answer.answer_id" class="reply-item">
              <p>
                <strong>{{ answer.author_name || '匿名' }}:</strong> {{ answer.answer_text }}
              </p>
            </div>
          </div>
          <div class="spacer"></div>
        </div>
      </div>

      <!-- 回答输入框 -->
      <div class="answer-input-container">
        <el-input
          v-model="answerText"
          type="textarea"
          :rows="2"
          placeholder="请输入你的回答..."
          maxlength="500"
          show-word-limit
          resize="none"
          class="answer-input"
        />
        <div class="answer-actions">
          <el-button type="primary" class="answer-btn" :loading="submitting" @click="handleSubmitAnswer">
            提交回答
          </el-button>
        </div>
      </div>

    </div>
  </BorderGlow>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import BorderGlow from '@/components/BorderGlow.vue'
import {
  fetchMessageDetail,
  fetchAnswers,
  publishAnswer,
  type InteractionMessage,
  type InteractionAnswer
} from '@/api/interaction'

const route = useRoute()
const router = useRouter()

const message = ref<InteractionMessage | null>(null)
const answers = ref<InteractionAnswer[]>([])
const answerText = ref('')
const submitting = ref(false)

const msgId = Number(route.params.id)

const loadDetail = async () => {
  try {
    message.value = await fetchMessageDetail(msgId)
  } catch (e) {
    ElMessage.error('加载互动消息失败')
  }
  try {
    answers.value = await fetchAnswers(msgId)
  } catch (e) {
    ElMessage.error('加载回答失败')
  }
}

const handleSubmitAnswer = async () => {
  const text = answerText.value.trim()
  if (!text) {
    ElMessage.warning('请输入回答内容')
    return
  }
  submitting.value = true
  try {
    await publishAnswer(msgId, text)
    ElMessage.success('回答成功')
    answerText.value = ''
    await loadDetail()
  } catch (e) {
    ElMessage.error('提交回答失败')
  } finally {
    submitting.value = false
  }
}

const goBack = () => {
  router.push('/student/interactive')
}

onMounted(() => {
  loadDetail()
})
</script>

<style scoped>
.interactive-detail-page {
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

.header-actions {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  flex-shrink: 0;
  position: relative;
}

.back-btn {
  color: #000;
  font-weight: bold;
  font-size: 1rem;
  position: absolute;
  left: 0;
}

.back-btn:hover {
  color: #2980b9;
}

.page-title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: bold;
  color: #000;
  width: 100%;
  text-align: center;
}

/* 区域容器 */
.section-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden; /* 保证内部滚动 */
}

.section-title {
  margin: 0 0 12px 0;
  font-size: 1.1rem;
  font-weight: 600;
  flex-shrink: 0;
}

.divider {
  height: 1px;
  background: rgba(0, 0, 0, 0.1);
  margin: 16px 0;
  flex-shrink: 0;
}

/* 滚动区域通用样式 (完全独立，互不影响) */
.scroll-area {
  flex: 1;
  overflow-y: auto;
  padding-right: 8px;
}

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

.spacer {
  height: 16px;
}

/* 内容细节 */
.post-content, .reply-item {
  line-height: 1.6;
  font-size: 1rem;
}

.reply-item {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px dashed rgba(0, 0, 0, 0.1);
}

.reply-item:last-child {
  border-bottom: none;
}

.mock-text {
  color: #555;
}

/* 回答输入框区域 */
.answer-input-container {
  margin-top: 16px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.answer-input {
  width: 100%;
}

.answer-input :deep(.el-textarea__inner) {
  background: rgba(255, 255, 255, 0.5);
  color: #000;
  border-radius: 8px;
}

.answer-actions {
  display: flex;
  justify-content: flex-end;
}

.answer-btn {
  background: #2980b9;
  border-color: #2980b9;
}
</style>
