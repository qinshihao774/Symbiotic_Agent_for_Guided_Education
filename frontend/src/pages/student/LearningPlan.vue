<template>
  <BorderGlow class="learning-plan-page" background-color="transparent">
    <div class="page-container glass-card">
      <!-- 顶部标题 -->
      <div class="header">
        <div class="title-badge">{{ studentName }}——建议学习规划</div>
        <el-button
          v-if="!planLoading"
          type="primary"
          size="small"
          :icon="Refresh"
          @click="loadPlan"
        >
          重新生成
        </el-button>
      </div>

      <!-- 规划内容大框 -->
      <div class="plan-content-wrapper glass-card">
        <div class="scroll-area">
          <!-- 加载状态 -->
          <div v-if="planLoading" class="plan-state">
            <div class="spinner-container">
              <div class="analysis-spinner"></div>
              <div class="spinner-ring spinner-ring-1"></div>
              <div class="spinner-ring spinner-ring-2"></div>
            </div>
            <p class="state-text">AI 正在为各学科制定学习规划...</p>
            <p class="state-subtext">正在综合 AI 分析、知识图谱、习题情况与老师意见</p>
          </div>

          <!-- 全局错误（数据库异常 / 无学科） -->
          <div v-else-if="globalError" class="plan-state">
            <p class="state-error">{{ globalError }}</p>
            <el-button type="primary" size="small" @click="loadPlan">重试</el-button>
          </div>

          <!-- 未加载状态 -->
          <div v-else-if="!planResult" class="plan-state">
            <p class="state-text">点击"生成学习规划"按钮，AI 将为你的各门学科制定个性化学习规划。</p>
            <el-button type="primary" size="large" :icon="MagicStick" @click="loadPlan">
              生成学习规划
            </el-button>
          </div>

          <!-- 规划结果 -->
          <div v-else class="plan-result">
            <!-- 各学科规划卡片 -->
            <div
              v-for="subject in planResult.subjects"
              :key="subject.course_id"
              class="subject-plan-card"
            >
              <!-- 学科标题 + 状态 -->
              <div class="subject-plan-header">
                <h3 class="subject-plan-title">{{ subject.course_name }}</h3>
                <span class="status-badge" :class="`status-${subject.status}`">
                  {{ statusText(subject.status) }}
                </span>
              </div>

              <!-- 维度可用性指示 -->
              <div class="dimension-indicators">
                <span
                  v-for="dim in dimensionMeta"
                  :key="dim.key"
                  class="dimension-tag"
                  :class="dimAvailable(subject, dim.key) ? 'dim-available' : 'dim-missing'"
                >
                  {{ dim.label }}
                </span>
              </div>

              <!-- 权重说明 -->
              <div v-if="subject.status === 'ok'" class="weight-info">
                <span class="weight-label">维度权重：</span>
                <span v-for="dim in dimensionMeta" :key="dim.key" class="weight-chip">
                  {{ dim.label }} {{ (subject.weights[dim.key] * 100).toFixed(0) }}%
                </span>
              </div>

              <!-- 状态：维度不足 -->
              <div v-if="subject.status === 'insufficient'" class="subject-error">
                <p class="error-text">{{ subject.error_message }}</p>
                <p class="error-hint">可能用户还没有开展学习哦~</p>
              </div>

              <!-- 状态：数据库异常 -->
              <div v-else-if="subject.status === 'db_error'" class="subject-error">
                <p class="error-text">{{ subject.error_message }}</p>
              </div>

              <!-- 状态：规划成功 -->
              <div v-else-if="subject.plan" class="plan-detail">
                <!-- 总体目标 -->
                <div class="plan-section">
                  <h4 class="section-title">总体目标</h4>
                  <p class="section-text">{{ subject.plan.overall_goal }}</p>
                </div>

                <!-- 薄弱知识点 -->
                <div v-if="subject.plan.weak_points?.length" class="plan-section">
                  <h4 class="section-title">薄弱知识点</h4>
                  <div class="chip-list">
                    <span v-for="(wp, idx) in subject.plan.weak_points" :key="idx" class="weak-chip">
                      {{ wp }}
                    </span>
                  </div>
                </div>

                <!-- 每周计划 -->
                <div v-if="subject.plan.weekly_plan?.length" class="plan-section">
                  <h4 class="section-title">每周计划</h4>
                  <div v-for="week in subject.plan.weekly_plan" :key="week.week" class="week-item">
                    <div class="week-header">
                      <span class="week-badge">第 {{ week.week }} 周</span>
                      <span class="week-theme">{{ week.theme }}</span>
                    </div>
                    <ul class="week-tasks">
                      <li v-for="(task, idx) in week.tasks" :key="idx">{{ task }}</li>
                    </ul>
                    <p v-if="week.exercises" class="week-exercises">练习量：{{ week.exercises }}</p>
                  </div>
                </div>

                <!-- 优先突破点 -->
                <div v-if="subject.plan.priority_focus?.length" class="plan-section">
                  <h4 class="section-title">优先突破点</h4>
                  <div class="chip-list">
                    <span v-for="(pf, idx) in subject.plan.priority_focus" :key="idx" class="priority-chip">
                      {{ idx + 1 }}. {{ pf }}
                    </span>
                  </div>
                </div>

                <!-- 老师意见补充 -->
                <div v-if="subject.plan.teacher_notes" class="plan-section">
                  <h4 class="section-title">老师意见补充</h4>
                  <p class="section-text">{{ subject.plan.teacher_notes }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </BorderGlow>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, MagicStick } from '@element-plus/icons-vue'
import BorderGlow from '@/components/BorderGlow.vue'
import { useAuthStore } from '@/stores/auth'
import { fetchLearningPlan, type LearningPlanResult, type SubjectPlan } from '@/api/learningPlan'

const authStore = useAuthStore()

// 学生姓名（优先从 Store 获取）
const studentName = ref(authStore.user?.name || '秦诗浩')

// 规划状态
const planLoading = ref(false)
const planResult = ref<LearningPlanResult | null>(null)
const globalError = ref('')

// 四维度元数据
const dimensionMeta = [
  { key: 'ai_analysis', label: 'AI 分析' },
  { key: 'knowledge_mastery', label: '知识图谱' },
  { key: 'exercise', label: '习题情况' },
  { key: 'teacher_opinion', label: '老师意见' },
] as const

/** 判断某学科某维度是否可用 */
const dimAvailable = (subject: SubjectPlan, dimKey: string): boolean => {
  const detail = subject.dimensions_detail?.[dimKey] as { available?: boolean } | undefined
  return !!detail?.available
}

/** 状态文案 */
const statusText = (status: string): string => {
  if (status === 'ok') return '已生成规划'
  if (status === 'insufficient') return '维度不足'
  if (status === 'db_error') return '数据异常'
  return status
}

/** 加载学习规划 */
const loadPlan = async () => {
  const userId = authStore.user?.id
  if (!userId) {
    ElMessage.warning('无法获取用户信息，请重新登录')
    return
  }

  planLoading.value = true
  globalError.value = ''
  planResult.value = null

  try {
    const result = await fetchLearningPlan(userId)
    if (result.error) {
      // 全局错误（数据库异常 / 无学科）
      globalError.value = result.error_message || '学习规划生成失败，请稍后重试'
    } else {
      planResult.value = result
    }
  } catch (err: any) {
    console.error('学习规划请求失败:', err)
    let msg = '学习规划请求失败，请稍后重试'
    const detail = err?.response?.data?.detail
    if (typeof detail === 'string') {
      msg = detail
    } else if (err?.message) {
      msg = err.message
    }
    globalError.value = msg
  } finally {
    planLoading.value = false
  }
}

onMounted(() => {
  // 页面加载时自动生成一次规划
  loadPlan()
})
</script>

<style scoped>
.learning-plan-page {
  color: #000;
  height: calc(100vh - 170px);
  margin: 20px;
}

.page-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 24px;
  background: #e5e8e4;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.5);
}

.header {
  margin-bottom: 20px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title-badge {
  font-size: 1.1rem;
  font-weight: 600;
  color: #000;
}

.plan-content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  overflow: hidden;
}

.scroll-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
}

/* --- 状态区（加载/错误/未加载） --- */
.plan-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 40px 0;
}

.state-text {
  font-size: 1rem;
  color: #333;
  font-weight: 500;
  margin: 0;
  text-align: center;
}

.state-subtext {
  font-size: 0.8rem;
  color: #888;
  margin: 0;
}

.state-error {
  font-size: 0.95rem;
  color: #f56c6c;
  margin: 0;
  text-align: center;
  line-height: 1.6;
}

/* --- 旋转加载特效 --- */
.spinner-container {
  position: relative;
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.analysis-spinner {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 3px solid #c0c5bd;
  border-top-color: #409eff;
  animation: spin 0.8s linear infinite;
  z-index: 2;
}

.spinner-ring {
  position: absolute;
  border-radius: 50%;
  border: 2px solid transparent;
  animation: spin 1.2s linear infinite;
}

.spinner-ring-1 {
  width: 48px;
  height: 48px;
  border-top-color: #67c23a;
  border-right-color: #67c23a;
  animation-duration: 1.5s;
  animation-direction: reverse;
}

.spinner-ring-2 {
  width: 60px;
  height: 60px;
  border-bottom-color: #e6a23c;
  border-left-color: #e6a23c;
  animation-duration: 2s;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* --- 规划结果 --- */
.plan-result {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.subject-plan-card {
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 10px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.subject-plan-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.subject-plan-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: #2c3e50;
}

.status-badge {
  font-size: 0.75rem;
  padding: 3px 12px;
  border-radius: 12px;
  font-weight: 600;
}

.status-ok {
  background: #e1f3d8;
  color: #67c23a;
  border: 1px solid #b3e19d;
}

.status-insufficient {
  background: #fdf6ec;
  color: #e6a23c;
  border: 1px solid #f3d19e;
}

.status-db_error {
  background: #fef0f0;
  color: #f56c6c;
  border: 1px solid #fbc4c4;
}

/* --- 维度指示 --- */
.dimension-indicators {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.dimension-tag {
  font-size: 0.75rem;
  padding: 2px 10px;
  border-radius: 10px;
  font-weight: 500;
}

.dim-available {
  background: #e1f3d8;
  color: #67c23a;
  border: 1px solid #b3e19d;
}

.dim-missing {
  background: #f5f5f5;
  color: #aaa;
  border: 1px solid #e0e0e0;
}

/* --- 权重说明 --- */
.weight-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 0.8rem;
}

.weight-label {
  color: #666;
  font-weight: 600;
}

.weight-chip {
  background: #ecf5ff;
  color: #409eff;
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid #d9ecff;
}

/* --- 错误提示 --- */
.subject-error {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 0;
}

.error-text {
  margin: 0;
  font-size: 0.9rem;
  color: #e6a23c;
  line-height: 1.6;
}

.error-hint {
  margin: 0;
  font-size: 0.85rem;
  color: #999;
  font-style: italic;
}

/* --- 规划详情 --- */
.plan-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.plan-section {
  background: rgba(255, 255, 255, 0.5);
  border-radius: 8px;
  padding: 10px 14px;
}

.section-title {
  margin: 0 0 6px 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: #409eff;
}

.section-text {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.7;
  color: #444;
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.weak-chip {
  background: #fdf6ec;
  color: #e6a23c;
  font-size: 0.8rem;
  padding: 3px 10px;
  border-radius: 6px;
  border: 1px solid #f3d19e;
}

.priority-chip {
  background: #ecf5ff;
  color: #409eff;
  font-size: 0.8rem;
  padding: 3px 10px;
  border-radius: 6px;
  border: 1px solid #d9ecff;
}

/* --- 每周计划 --- */
.week-item {
  border-left: 3px solid #409eff;
  padding: 6px 0 6px 12px;
  margin-bottom: 10px;
}

.week-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.week-badge {
  background: #409eff;
  color: #fff;
  font-size: 0.75rem;
  padding: 2px 10px;
  border-radius: 10px;
  font-weight: 600;
  flex-shrink: 0;
}

.week-theme {
  font-size: 0.85rem;
  font-weight: 600;
  color: #2c3e50;
}

.week-tasks {
  margin: 0;
  padding-left: 18px;
  font-size: 0.82rem;
  color: #555;
  line-height: 1.8;
}

.week-exercises {
  margin: 4px 0 0 0;
  font-size: 0.8rem;
  color: #67c23a;
  font-weight: 500;
}
</style>
