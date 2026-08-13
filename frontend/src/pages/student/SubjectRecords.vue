<template>
  <BorderGlow class="subject-records-page" background-color="transparent">
    <div class="glass-card page-container">
      <div class="header-toolbar">
        <el-button class="back-btn" plain @click="goBack">返回</el-button>
        <h2 class="page-title">{{ subjectName }}做题记录</h2>
        <div class="search-box">
          <el-input
            v-model="searchQuery"
            placeholder="搜索题目..."
            clearable
          >
            <template #append>
              <el-button @click="handleSearch">搜索</el-button>
            </template>
          </el-input>
        </div>
      </div>
      
      <!-- 记录列表区域，独立滚动 -->
      <div class="list-container scroll-area">
        <div class="records-list">
          <div 
            v-for="record in pagedRecords" 
            :key="record.do_id" 
            class="record-item"
            :class="getRecordClass(record)"
            @dblclick="goToPracticePanel(record.question_id, courseId)"
          >
            <div class="record-stem text-truncate" :title="record.question_description">
              {{ record.question_description }}
            </div>
            
            <div class="record-meta">
              <span class="subject-tag">【{{ record.course_name || subjectName }}】</span>
              <span v-if="record.kg_node_name" class="tag">{{ record.kg_node_name }}</span>
              <span class="date">{{ formatDate(record.created_at) }}</span>
            </div>
          </div>
          <div v-if="filteredRecords.length === 0 && !loading" class="empty-tip">
            {{ searchQuery.trim() ? '未找到匹配的做题记录' : '暂无做题记录' }}
          </div>
          <div v-if="loading" class="empty-tip">加载中...</div>
        </div>
        <div class="spacer"></div>
      </div>

      <!-- 分页区域 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="totalRecords"
          layout="total, prev, pager, next"
          class="custom-pagination"
        />
      </div>
    </div>
  </BorderGlow>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import BorderGlow from '@/components/BorderGlow.vue'
import { fetchCourses, fetchExerciseRecords, type Course, type ExerciseRecordListItem } from '@/api/practice'

const route = useRoute()
const router = useRouter()

const goBack = () => {
  router.back()
}

const searchQuery = ref('')
const handleSearch = () => {
  // 触发过滤：重置到第一页并重新计算 filteredRecords
  currentPage.value = 1
  filteredRecords.value = buildFilteredRecords()
}

const moduleId = route.query.module as string
const courseId = moduleId ? parseInt(moduleId, 10) : 0

const subjectName = ref('学科')
const records = ref<ExerciseRecordListItem[]>([])
const loading = ref(true)

// 搜索过滤后的记录列表
const filteredRecords = ref<ExerciseRecordListItem[]>([])

// 根据搜索词过滤记录
const buildFilteredRecords = (): ExerciseRecordListItem[] => {
  const keyword = searchQuery.value.trim().toLowerCase()
  if (!keyword) return records.value
  return records.value.filter((record) => {
    const stem = (record.question_description || '').toLowerCase()
    const kg = (record.kg_node_name || '').toLowerCase()
    const course = (record.course_name || subjectName.value || '').toLowerCase()
    return stem.includes(keyword) || kg.includes(keyword) || course.includes(keyword)
  })
}

onMounted(async () => {
  if (!courseId) {
    ElMessage.warning('未指定学科')
    loading.value = false
    return
  }

  try {
    // 获取学科名称
    const courses = await fetchCourses()
    const course = courses?.find((c: Course) => c.course_id === courseId)
    subjectName.value = course?.course_name || '学科'

    // 获取该学科下的做题记录
    const data = await fetchExerciseRecords(courseId)
    records.value = data || []
    filteredRecords.value = records.value
  } catch (error) {
    console.error('获取做题记录失败:', error)
    ElMessage.error('获取做题记录失败')
  } finally {
    loading.value = false
  }
})

// 根据记录的对错状态返回样式类
const getRecordClass = (record: ExerciseRecordListItem) => {
  if (record.do_isTrue === true) return 'correct-item'
  if (record.do_isTrue === false) return 'incorrect-item'
  // 主观题：do_isTrue 为 null，根据 do_score 判断
  if (record.do_score !== null && record.do_score !== undefined) {
    return record.do_score >= 10.0 ? 'correct-item' : 'incorrect-item'
  }
  return ''
}

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const currentPage = ref(1)
const pageSize = ref(10)
const totalRecords = computed(() => filteredRecords.value.length)

const pagedRecords = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredRecords.value.slice(start, start + pageSize.value)
})

// 双击跳转到练习面板（携带学科 ID 和题目 ID）
const goToPracticePanel = (questionId: number, courseId: number) => {
  router.push({
    path: '/student/practice/panel',
    query: {
      questionId: String(questionId),
      module: String(courseId),
    }
  })
}
</script>

<style scoped>
.subject-records-page {
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

.header-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-shrink: 0;
  position: relative;
}

.page-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: bold;
  color: #000;
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.back-btn {
  border-color: #666;
  color: #333;
  background: transparent;
}
.back-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #000;
  border-color: #000;
}

.search-box {
  width: 250px;
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

.list-container {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.scroll-area {
  overflow-y: auto;
  padding: 0 40px;
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

.records-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* --- 记录项样式及对错状态区分 --- */
.record-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 2px solid transparent;
}

.record-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

/* 正确的记录：绿色框包围与微绿背景 */
.correct-item {
  background-color: rgba(39, 174, 96, 0.1);
  border-color: rgba(39, 174, 96, 0.3);
}
.correct-item:hover {
  background-color: rgba(39, 174, 96, 0.2);
  border-color: rgba(39, 174, 96, 0.5);
}

/* 错误的记录：红色框包围与微红背景 */
.incorrect-item {
  background-color: rgba(231, 76, 60, 0.1);
  border-color: rgba(231, 76, 60, 0.3);
}
.incorrect-item:hover {
  background-color: rgba(231, 76, 60, 0.2);
  border-color: rgba(231, 76, 60, 0.5);
}

.record-stem {
  flex: 1;
  font-size: 1rem;
  color: #333;
  margin-right: 24px;
}

.text-truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.record-meta {
  display: flex;
  align-items: center;
  gap: 24px;
  flex-shrink: 0;
}

.tags {
  display: flex;
  gap: 8px;
}

.subject-tag {
  font-size: 0.9rem;
  color: #2980b9;
  font-weight: 500;
}

.tag {
  font-size: 0.9rem;
  color: #666;
}

.date {
  font-size: 0.9rem;
  color: #666;
  width: 140px;
  text-align: right;
}

.empty-tip {
  text-align: center;
  padding: 40px;
  color: #999;
  font-size: 0.95rem;
}

.spacer {
  height: 20px;
}

/* 分页组件样式覆盖 */
.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: center;
  flex-shrink: 0;
}

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
</style>
