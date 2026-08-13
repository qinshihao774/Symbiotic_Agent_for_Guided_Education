<template>
  <div class="teacher-page h-full flex flex-col gap-6 p-4">
    <!-- 上半部分：互动列表 -->
    <el-card class="h-1/2 flex flex-col" shadow="never">
      <template #header>
        <span class="font-bold text-gray-800 text-sm">互动答疑</span>
        <span class="text-xs text-gray-500 ml-4">双击跳转详细对话面板</span>
      </template>
      <div class="h-full flex flex-col">
        <el-table
          :data="messageList"
          style="width: 100%; background: transparent;"
          class="flex-1"
          @row-dblclick="handleRowDblclick"
        >
          <el-table-column prop="stu_name" label="学生" width="120" />
          <el-table-column prop="msg_texts" label="问题、对话、描述等" min-width="300">
            <template #default="scope">
              <span class="truncate">{{ scope.row.msg_texts }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="answer_num" label="回答数" width="120">
            <template #default="scope">
              回答数 × {{ scope.row.answer_num }}
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间" width="170" align="right">
            <template #default="scope">
              {{ formatTime(scope.row.created_at) }}
            </template>
          </el-table-column>
        </el-table>
        <div class="mt-4 flex justify-center">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="total"
            layout="total, prev, pager, next"
            @current-change="loadMessages"
          />
        </div>
      </div>
    </el-card>

    <!-- 下半部分：作业/考试推送 -->
    <el-card class="h-1/2 flex flex-col" shadow="never">
      <template #header>
        <span class="font-bold text-gray-800 text-sm">作业 / 考试推送</span>
        <span class="text-xs text-gray-500 ml-4">当前教师：{{ authStore.user?.name || '未知' }}</span>
      </template>
      <div class="h-full flex gap-6">
        <!-- 操作区 -->
        <div class="w-56 flex flex-col gap-4">
          <div class="text-sm text-gray-600 mb-2">配置生成条件：</div>
          <el-select
            v-model="selectedCourseId"
            placeholder="选择教学学科"
            size="small"
            filterable
            @change="handleCourseChange"
          >
            <el-option
              v-for="course in courseList"
              :key="course.course_id"
              :label="course.course_name"
              :value="course.course_id"
            />
          </el-select>
          <el-select
            v-model="selectedClassId"
            placeholder="选择推送班级"
            size="small"
            filterable
            :disabled="!selectedCourseId"
            @change="handleClassChange"
          >
            <el-option
              v-for="cls in classList"
              :key="cls.class_id"
              :label="`${cls.class_name}（${cls.student_count}人）`"
              :value="cls.class_id"
            />
          </el-select>
          <el-select
            v-model="selectedChapter"
            placeholder="选择章节范围"
            size="small"
            filterable
            clearable
            :disabled="!selectedCourseId"
          >
            <el-option
              v-for="chapter in chapterList"
              :key="chapter.id"
              :label="chapter.name"
              :value="chapter.name"
            />
          </el-select>
          <el-button
            type="primary"
            class="mt-auto"
            disabled
            title="功能开发中"
          >
            点击生成（功能开发中）
          </el-button>
        </div>
        <!-- 内容展示区 -->
        <div class="flex-1 border border-gray-200 rounded-lg bg-gray-50/50 p-4 overflow-y-auto custom-scrollbar relative">
          <div v-if="!selectedCourseId" class="h-full flex items-center justify-center text-gray-400 text-sm">
            请先选择教学学科
          </div>
          <div v-else-if="!selectedClassId" class="h-full flex items-center justify-center text-gray-400 text-sm">
            请选择推送班级
          </div>
          <div v-else class="text-sm text-gray-700">
            <div class="font-bold text-gray-800 mb-3">推送对象（{{ selectedClass?.class_name }}）</div>
            <div v-if="studentList.length === 0" class="text-gray-400 text-sm">
              该班级暂无学生
            </div>
            <div v-else class="flex flex-wrap gap-2">
              <el-tag
                v-for="stu in studentList"
                :key="stu.stu_id"
                size="small"
                effect="plain"
              >
                {{ stu.stu_name }}
              </el-tag>
            </div>
            <div class="mt-4 text-gray-400 text-xs">
              已选学科：{{ selectedCourse?.course_name }}　已选章节：{{ selectedChapter || '未选择' }}
            </div>
            <div class="mt-6 text-gray-400 text-sm">
              Agent 生成作业 / 考试内容展示区（功能开发中）
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 详情对话框（微信聊天风格） -->
    <el-dialog
      v-model="detailDialogVisible"
      title="详细对话面板"
      width="70%"
      destroy-on-close
      @opened="scrollToBottom"
    >
      <div class="flex flex-col h-[500px] border border-gray-200 rounded-lg overflow-hidden">
        <!-- 问题区（置顶） -->
        <div class="p-4 border-b border-gray-200 bg-gray-50 shrink-0">
          <div class="font-bold text-sm text-gray-800 mb-2">问题区:</div>
          <div class="text-sm text-gray-700">
            <span class="font-bold mr-2">{{ currentDetail?.stu_name || '学生' }}:</span>
            {{ currentDetail?.msg_texts }}
          </div>
        </div>
        <!-- 答疑区（微信聊天风格，按时间正序：旧在上、新在下） -->
        <div ref="chatScrollRef" class="flex-1 p-4 overflow-y-auto custom-scrollbar bg-white">
          <div class="font-bold text-sm text-gray-800 mb-4">答疑区:</div>

          <div v-if="answers.length === 0" class="text-center text-gray-400 text-sm py-8">
            暂无回答，快来抢答吧~
          </div>

          <div
            v-for="answer in answers"
            :key="answer.answer_id"
            class="mb-4"
            :class="isMyAnswer(answer) ? 'text-right' : ''"
          >
            <div class="text-xs text-gray-500 mb-1">
              {{ answer.author_name || '匿名' }}
              <span v-if="answer.author_type === 'teacher'" class="ml-1 text-blue-500">(老师)</span>
              <span v-else class="ml-1 text-green-600">(学生)</span>
              <span class="ml-2">{{ formatTime(answer.created_at) }}</span>
            </div>
            <div
              class="p-3 rounded-lg text-sm text-gray-700 inline-block max-w-[80%] text-left break-words"
              :class="isMyAnswer(answer) ? 'bg-blue-50' : 'bg-gray-100'"
            >
              {{ answer.answer_text }}
            </div>
          </div>
        </div>
        <!-- 底部回复输入 -->
        <div class="p-4 border-t border-gray-200 bg-gray-50 flex gap-4 shrink-0">
          <el-input
            v-model="replyText"
            placeholder="输入回复内容..."
            class="flex-1"
            maxlength="500"
            @keyup.enter="handleReply"
          />
          <el-button type="primary" :loading="replying" @click="handleReply">回复</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  fetchMessages,
  fetchAnswers,
  publishAnswer,
  type InteractionMessage,
  type InteractionAnswer
} from '@/api/interaction'
import {
  getTeacherCourses,
  getTeacherClasses,
  getClassStudents,
  getCourseChapters,
  type TeacherCourse,
  type TeacherClass,
  type ClassStudent,
  type CourseChapter
} from '@/api/teacher'
import { useAuthStore } from '@/stores/auth'
import { fetchCurrentUser } from '@/api/auth'

const authStore = useAuthStore()

const messageList = ref<InteractionMessage[]>([])
const currentPage = ref(1)
const pageSize = ref(5)
const total = ref(0)

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

const detailDialogVisible = ref(false)
const currentDetail = ref<InteractionMessage | null>(null)
const answers = ref<InteractionAnswer[]>([])
const replyText = ref('')
const replying = ref(false)
const chatScrollRef = ref<HTMLElement | null>(null)

/** 判断某条回答是否为当前登录老师本人发布 */
const isMyAnswer = (answer: InteractionAnswer): boolean => {
  return answer.author_type === 'teacher' && answer.tea_id === authStore.user?.id
}

const handleRowDblclick = async (row: InteractionMessage) => {
  currentDetail.value = row
  answers.value = []
  replyText.value = ''
  detailDialogVisible.value = true
  try {
    answers.value = await fetchAnswers(row.msg_id)
    await nextTick()
    scrollToBottom()
  } catch (e) {
    ElMessage.error('加载回答失败')
  }
}

/** 滚动到底部（最新消息在下方） */
const scrollToBottom = () => {
  if (chatScrollRef.value) {
    chatScrollRef.value.scrollTop = chatScrollRef.value.scrollHeight
  }
}

const handleReply = async () => {
  const text = replyText.value.trim()
  if (!text) {
    ElMessage.warning('请输入回复内容')
    return
  }
  if (!currentDetail.value) return
  replying.value = true
  try {
    await publishAnswer(currentDetail.value.msg_id, text)
    ElMessage.success('回复成功')
    replyText.value = ''
    answers.value = await fetchAnswers(currentDetail.value.msg_id)
    // 同步刷新列表中的回答数
    await loadMessages()
    await nextTick()
    scrollToBottom()
  } catch (e) {
    ElMessage.error('回复失败')
  } finally {
    replying.value = false
  }
}

// 作业/考试推送 —— 严格联动：教师 → 学科 → 班级 → 学生 → 章节
const courseList = ref<TeacherCourse[]>([])
const classList = ref<TeacherClass[]>([])
const chapterList = ref<CourseChapter[]>([])
const studentList = ref<ClassStudent[]>([])

const selectedCourseId = ref<number | null>(null)
const selectedClassId = ref<number | null>(null)
const selectedChapter = ref<string>('')

const selectedCourse = computed(() =>
  courseList.value.find((c) => c.course_id === selectedCourseId.value) || null
)
const selectedClass = computed(() =>
  classList.value.find((c) => c.class_id === selectedClassId.value) || null
)

/** 选择学科后：加载该学科知识图谱章节，并清空班级/章节/学生选择 */
const handleCourseChange = async () => {
  selectedClassId.value = null
  selectedChapter.value = ''
  studentList.value = []
  chapterList.value = []
  if (!selectedCourseId.value) return
  try {
    chapterList.value = await getCourseChapters(selectedCourseId.value)
  } catch (e) {
    ElMessage.error('加载学科章节失败')
  }
}

/** 选择班级后：加载该班级学生（需同时具备学科与班级） */
const handleClassChange = async () => {
  studentList.value = []
  if (!selectedCourseId.value || !selectedClassId.value) return
  try {
    studentList.value = await getClassStudents(selectedClassId.value, selectedCourseId.value)
  } catch (e) {
    ElMessage.error('加载班级学生失败')
  }
}

const loadTeacherData = async () => {
  try {
    const [courses, classes] = await Promise.all([
      getTeacherCourses(),
      getTeacherClasses(),
    ])
    courseList.value = courses
    classList.value = classes
  } catch (e) {
    ElMessage.error('加载教师学科/班级失败')
  }
}

/** 恢复当前登录教师信息（页面刷新后 authStore.user 为 null，需从后端重新拉取） */
const loadUserInfo = async () => {
  try {
    const me = await fetchCurrentUser()
    authStore.setUser({
      id: me.id,
      name: me.name,
      email: me.email,
      gender: me.gender,
      stu_level: me.stu_level,
      class_id: me.class_id,
      class_name: me.class_name,
      role: me.user_type as 'student' | 'teacher',
    })
  } catch {
    // 接口失败时降级使用 Store 中已有的信息
  }
}

onMounted(() => {
  loadMessages()
  loadTeacherData()
  loadUserInfo()
})
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.02);
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.25);
}

:deep(.el-table tr) {
  cursor: pointer;
}
</style>
