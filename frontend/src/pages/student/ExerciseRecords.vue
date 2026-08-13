<template>
  <BorderGlow class="exercise-records-page" background-color="transparent">
    <div class="records-layout">
      <!-- 左侧：学科卡片 -->
      <div class="left-panel">
        <div class="grid-container">
          <div 
            v-for="subject in subjects" 
            :key="subject.course_id" 
            class="glass-card subject-card"
            @click="enterSubjectDetail(subject.course_id)"
          >
            <span class="subject-name">{{ subject.course_name }}做题记录</span>
          </div>
        </div>
      </div>

      <!-- 右侧：按学科分组的错题记录 -->
      <div class="right-panel glass-card">
        <div class="right-header">
          <h3 class="panel-title">错题记录</h3>
          <div class="search-box">
            <el-input
              v-model="searchQuery"
              placeholder="搜索错题..."
              clearable
              @keyup.enter="handleSearch"
              @clear="handleSearch"
            >
              <template #append>
                <el-button @click="handleSearch">搜索</el-button>
              </template>
            </el-input>
          </div>
        </div>
        <div class="records-list scroll-area">
          <!-- 按学科分组遍历 -->
          <div v-for="(group, cid) in filteredGroups" :key="cid" class="group-section">
            <div class="group-header">{{ group.course_name }}</div>
            <div
              v-for="record in group.records"
              :key="record.do_id"
              class="record-item"
              @dblclick="goToPracticePanel(record.question_id, Number(cid))"
            >
              <div class="record-stem text-truncate" :title="record.question_description">
                {{ record.question_description }}
              </div>
              <div class="record-meta">
                <span class="subject-tag">【{{ record.course_name || group.course_name }}】</span>
                <span v-if="record.kg_node_name" class="tag">{{ record.kg_node_name }}</span>
                <span class="date">{{ formatDate(record.created_at) }}</span>
              </div>
            </div>
          </div>
          <div v-if="hasNoRecords && !loading" class="empty-tip">
            暂无错题记录
          </div>
          <div v-if="loading" class="empty-tip">加载中...</div>
        </div>
      </div>
    </div>
  </BorderGlow>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import BorderGlow from '@/components/BorderGlow.vue'
import { fetchCourses, fetchWrongRecordsGrouped, type Course, type ExerciseRecordListItem } from '@/api/practice'

interface WrongGroup {
  course_name: string
  records: ExerciseRecordListItem[]
}

const router = useRouter()

const subjects = ref<Course[]>([])
const groupedWrongRecords = ref<Record<number, WrongGroup>>({})
const loading = ref(true)

const hasNoRecords = computed(() => {
  return Object.keys(filteredGroups.value).length === 0
})

// 搜索错题
const searchQuery = ref('')
const handleSearch = () => {
  // 触发 filteredGroups 重新计算
  filteredGroups.value = buildFilteredGroups()
}

// 根据搜索词过滤错题分组
const filteredGroups = ref<Record<number, WrongGroup>>({})
const buildFilteredGroups = (): Record<number, WrongGroup> => {
  const keyword = searchQuery.value.trim().toLowerCase()
  if (!keyword) return groupedWrongRecords.value

  const result: Record<number, WrongGroup> = {}
  for (const [cid, group] of Object.entries(groupedWrongRecords.value)) {
    const matched = group.records.filter((record) => {
      const stem = (record.question_description || '').toLowerCase()
      const kg = (record.kg_node_name || '').toLowerCase()
      const course = (record.course_name || group.course_name || '').toLowerCase()
      return stem.includes(keyword) || kg.includes(keyword) || course.includes(keyword)
    })
    if (matched.length > 0) {
      result[Number(cid)] = { course_name: group.course_name, records: matched }
    }
  }
  return result
}

onMounted(async () => {
  try {
    // 并行获取学科列表和分组错题
    const [courses, grouped] = await Promise.all([
      fetchCourses(),
      fetchWrongRecordsGrouped(),
    ])
    subjects.value = courses || []
    groupedWrongRecords.value = grouped || {}
    filteredGroups.value = grouped || {}
  } catch (error) {
    console.error('获取数据失败:', error)
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
})

// 跳转到具体学科做题记录
const enterSubjectDetail = (courseId: number) => {
  router.push({
    path: '/student/subject-records',
    query: { module: String(courseId) }
  })
}

// 双击跳转到错题练习面板（携带学科 ID 和题目 ID）
const goToPracticePanel = (questionId: number, courseId: number) => {
  router.push({
    path: '/student/practice/panel',
    query: {
      questionId: String(questionId),
      module: String(courseId),
    }
  })
}

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
</script>

<style scoped>
.exercise-records-page {
  color: #000;
  height: calc(100vh - 170px);
  margin: 20px;
}

.records-layout {
  display: flex;
  gap: 24px;
  height: 100%;
  padding: 24px;
}

/* 玻璃拟态卡片基础样式 */
.glass-card {
  background: #e5e8e4;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.5);
}

/* --- 左侧面板：四宫格 --- */
.left-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.grid-container {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: repeat(2, 1fr);
  gap: 24px;
}

.subject-card {
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background: rgba(255, 255, 255, 0.6);
}

.subject-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
  background: rgba(255, 255, 255, 0.9);
}

.subject-name {
  font-size: 1.2rem;
  font-weight: 600;
  color: #333;
}

/* --- 右侧面板：错题记录 --- */
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px;
  overflow: hidden;
}

.right-header {
  position: relative;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.panel-title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: bold;
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.search-box {
  width: 250px;
  flex-shrink: 0;
}
:deep(.search-box .el-input__wrapper) {
  background: transparent;
  box-shadow: 0 0 0 1px #666 inset;
}
:deep(.search-box .el-input-group__append) {
  background: transparent;
  border: 1px solid #666;
  border-left: none;
  color: #333;
}

.records-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 滚动区域通用样式 */
.scroll-area {
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

/* 学科分组 */
.group-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.group-header {
  font-size: 1rem;
  font-weight: 600;
  color: #2980b9;
  padding: 4px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  margin-bottom: 4px;
}

/* 记录项 */
.record-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.record-item:hover {
  background: rgba(255, 255, 255, 0.8);
}

.record-stem {
  flex: 1;
  margin-right: 16px;
  font-size: 0.95rem;
}

.text-truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.record-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.subject-tag {
  font-size: 0.85rem;
  color: #2980b9;
  font-weight: 500;
}

.tag {
  font-size: 0.85rem;
  color: #666;
}

.date {
  font-size: 0.85rem;
  color: #666;
  width: 130px;
  text-align: right;
}

.empty-tip {
  text-align: center;
  padding: 40px;
  color: #999;
  font-size: 0.95rem;
}
</style>
