<template>
  <div class="teacher-page flex h-full flex-col gap-6 p-4">
    <div class="flex min-h-[300px] gap-6 max-lg:flex-col">
      <el-card class="teacher-card w-1/4 max-lg:w-full" shadow="never">
        <template #header>
          <div class="flex gap-3 max-sm:flex-col">
            <el-select v-model="selectedClass" placeholder="选择班级" class="flex-1">
              <el-option
                v-for="cls in classList"
                :key="cls.class_id"
                :label="cls.class_name"
                :value="cls.class_id"
              />
            </el-select>
            <el-select v-model="selectedCourse" placeholder="选择学科" class="flex-1">
              <el-option
                v-for="course in courseList"
                :key="course.course_id"
                :label="course.course_name"
                :value="course.course_id"
              />
            </el-select>
          </div>
        </template>

        <div class="space-y-4 text-sm text-slate-700">
          <div class="flex items-center justify-between">
            <span>学生数量</span>
            <span class="font-semibold text-slate-900">{{ currentClassStudentCount }}</span>
          </div>
          <div class="flex items-center justify-between">
            <span>班级 AI 评级</span>
            <span class="font-semibold" :class="aiLevelColor">{{ classAiLevel || '--' }}</span>
          </div>
          <div class="flex items-center justify-between">
            <span>最近一次平均分</span>
            <span class="font-semibold text-slate-900">82.5</span>
          </div>
          <div class="flex items-center justify-between">
            <span>知识点平均掌握度</span>
            <span class="font-semibold text-sky-600">{{ classAvgProcessText }}</span>
          </div>
        </div>
      </el-card>

      <el-card class="teacher-card flex-1 max-lg:w-full" shadow="never">
        <template #header>
          <div class="flex items-center justify-between">
            <span class="text-sm font-bold text-slate-800">学生进度与评级</span>
            <span class="text-xs text-slate-500">双击查看详情</span>
          </div>
        </template>

        <div class="custom-scrollbar h-[280px] overflow-y-auto pr-2">
          <div
            v-for="stu in studentList"
            :key="stu.stu_id"
            class="flex cursor-pointer items-center justify-between rounded-lg border-b border-slate-100 p-3 transition-colors hover:bg-slate-50"
            @dblclick="openStudentDetail(stu)"
          >
            <span class="w-24 truncate text-sm text-slate-700">{{ stu.stu_name }}</span>
            <el-progress
              :percentage="progressPercent(stu.course_process)"
              :stroke-width="8"
              class="mx-4 flex-1"
            />
            <span class="w-8 text-center text-sm font-bold" :class="getRatingColor(stu.stu_level)">
              {{ stu.stu_level || '--' }}
            </span>
          </div>
          <div v-if="studentList.length === 0" class="py-8 text-center text-sm text-slate-400">
            当前班级暂无学生数据
          </div>
        </div>
      </el-card>

      <el-card class="teacher-card flex-1 max-lg:w-full" shadow="never">
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <span class="text-sm font-bold text-slate-800">疑难章节分布图</span>
            <span class="text-xs text-slate-500">
              {{ difficultChapterList.length > 0 ? `共 ${difficultChapterList.length} 个章节` : '暂无数据' }}
            </span>
          </div>
        </template>

        <div v-if="difficultChapterList.length > 0" ref="chapterChartRef" class="h-[280px] w-full"></div>
        <div
          v-else
          class="flex h-[280px] items-center justify-center rounded-xl bg-slate-50/80"
        >
          <div class="flex flex-col items-center text-sm text-slate-400">
            <el-icon :size="32" class="mb-2"><PieChart /></el-icon>
            当前班级该学科暂无疑难章节数据
          </div>
        </div>
      </el-card>
    </div>

    <div class="flex min-h-[360px] gap-6 max-lg:flex-col">
      <el-card class="teacher-card w-[45%] max-lg:w-full" shadow="never">
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <span class="text-sm font-bold text-slate-800">AI 班级教学建议</span>
            <el-button
              type="primary"
              size="small"
              :loading="teachingSuggestionLoading"
              :disabled="selectedClass === null || selectedCourse === null"
              @click="loadTeachingSuggestion"
            >
              {{ teachingSuggestionLoading ? '生成中...' : '生成建议' }}
            </el-button>
          </div>
        </template>

        <div class="custom-scrollbar h-[360px] overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/70 p-4 text-sm leading-7 text-slate-700">
          <!-- 加载中 -->
          <div v-if="teachingSuggestionLoading" class="flex h-full flex-col items-center justify-center gap-3 text-slate-400">
            <el-icon class="is-loading" :size="28"><Loading /></el-icon>
            <span>AI 正在综合分析班级学情，生成教学建议...</span>
          </div>

          <!-- 数据不足 / 异常 -->
          <div v-else-if="teachingSuggestionError" class="flex h-full flex-col items-center justify-center gap-2 text-center">
            <el-icon :size="32" class="text-amber-500"><WarningFilled /></el-icon>
            <p class="font-medium text-slate-600">{{ teachingSuggestionError }}</p>
            <p v-if="teachingSuggestionMissing.length" class="text-xs text-slate-400">
              缺失维度：{{ teachingSuggestionMissing.join('、') }}
            </p>
          </div>

          <!-- 建议内容 -->
          <div v-else-if="teachingSuggestion" class="space-y-4">
            <!-- 权重说明 -->
            <div class="flex flex-wrap items-center gap-2 rounded-lg bg-white/80 px-3 py-2 text-xs text-slate-500">
              <span class="font-semibold text-slate-600">评估维度权重：</span>
              <el-tag
                v-for="(weight, key) in teachingSuggestionWeights"
                :key="key"
                size="small"
                effect="plain"
              >
                {{ dimensionLabel(key) }} {{ (weight * 100).toFixed(0) }}%
              </el-tag>
            </div>

            <!-- 整体评估 -->
            <div>
              <h4 class="mb-1 flex items-center gap-1 font-semibold text-slate-800">
                <el-icon :size="14"><DataAnalysis /></el-icon> 班级整体学情评估
              </h4>
              <p class="text-slate-600">{{ teachingSuggestion.overall_assessment }}</p>
            </div>

            <!-- 优先教学重点 -->
            <div>
              <h4 class="mb-1 flex items-center gap-1 font-semibold text-slate-800">
                <el-icon :size="14"><Flag /></el-icon> 优先教学重点
              </h4>
              <div class="flex flex-wrap gap-2">
                <el-tag
                  v-for="(focus, idx) in teachingSuggestion.priority_focus"
                  :key="idx"
                  type="danger"
                  effect="light"
                  size="small"
                >
                  {{ focus }}
                </el-tag>
              </div>
            </div>

            <!-- 教学策略 -->
            <div>
              <h4 class="mb-1 flex items-center gap-1 font-semibold text-slate-800">
                <el-icon :size="14"><MagicStick /></el-icon> 教学策略建议
              </h4>
              <div class="space-y-2">
                <div
                  v-for="(strategy, idx) in teachingSuggestion.teaching_strategies"
                  :key="idx"
                  class="rounded-lg bg-white/80 p-3"
                >
                  <p class="font-medium text-slate-700">{{ strategy.strategy }}</p>
                  <p class="text-xs text-slate-500">{{ strategy.detail }}</p>
                </div>
              </div>
            </div>

            <!-- 疑难专项突破 -->
            <div>
              <h4 class="mb-1 flex items-center gap-1 font-semibold text-slate-800">
                <el-icon :size="14"><Aim /></el-icon> 疑难章节与知识点专项突破
              </h4>
              <p class="text-slate-600">{{ teachingSuggestion.difficult_focus }}</p>
            </div>

            <!-- 作业与练习 -->
            <div>
              <h4 class="mb-1 flex items-center gap-1 font-semibold text-slate-800">
                <el-icon :size="14"><EditPen /></el-icon> 作业与练习安排
              </h4>
              <p class="text-slate-600">{{ teachingSuggestion.homework_suggestion }}</p>
            </div>

            <!-- 教师补充说明 -->
            <div v-if="teachingSuggestion.teacher_notes" class="rounded-lg bg-amber-50/80 p-3 text-xs text-amber-700">
              <p class="font-semibold">教师补充说明</p>
              <p>{{ teachingSuggestion.teacher_notes }}</p>
            </div>
          </div>

          <!-- 初始占位 -->
          <div v-else class="flex h-full flex-col items-center justify-center gap-2 text-center text-slate-400">
            <el-icon :size="32"><ChatLineRound /></el-icon>
            <p>点击「生成建议」，AI 将综合学生评级、班级知识点平均掌握度进度、疑难章节与知识点三个维度，为班级生成下一步教学建议。</p>
          </div>
        </div>
      </el-card>

      <el-card class="teacher-card flex-1 max-lg:w-full" shadow="never">
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <span class="text-sm font-bold text-slate-800">疑难知识点词云</span>
            <span class="text-xs text-slate-500">
              {{ wordCloudList.length > 0 ? `Top ${wordCloudList.length}` : '暂无数据' }}
            </span>
          </div>
        </template>

        <div class="word-cloud-panel">
          <div
            v-if="wordCloudList.length > 0"
            ref="cloudContainerRef"
            class="word-cloud-container"
          >
            <span
              v-for="(item, idx) in wordCloudList"
              :key="item.name"
              :ref="(el) => setCloudItemRef(el, idx)"
              class="word-cloud-item"
              :class="{ 'word-cloud-item--ready': wordCloudReady }"
              :style="wordCloudStyle(item, idx)"
              :title="`${item.name} | 次数 ${item.count} | 占比 ${(item.ratio * 100).toFixed(1)}%`"
            >
              {{ item.name }}
            </span>
          </div>
          <div v-else class="flex h-full items-center justify-center text-sm text-slate-400">
            当前班级该学科暂无错题知识点数据
          </div>
        </div>
      </el-card>
    </div>

    <el-dialog
      v-model="studentDialogVisible"
      title="学生详情与图谱"
      width="80%"
      class="student-detail-dialog"
      destroy-on-close
    >
      <div class="flex h-[680px] gap-6 max-lg:h-auto max-lg:flex-col">
        <div class="flex w-1/4 flex-col gap-4 max-lg:w-full">
          <el-card shadow="never" class="bg-slate-50">
            <div class="space-y-2 text-sm text-slate-700">
              <div><span class="text-slate-500">班级：</span>{{ currentClassName }}</div>
              <div><span class="text-slate-500">姓名：</span>{{ currentStudent?.stu_name || '--' }}</div>
              <div>
                <span class="text-slate-500">评级：</span>
                <span class="font-bold text-sky-600">{{ currentStudent?.stu_level || '--' }}</span>
              </div>
              <div>
                <span class="text-slate-500">进度：</span>
                {{ progressPercent(currentStudent?.course_process ?? null) }}%
              </div>
            </div>
          </el-card>

          <el-card shadow="never" class="flex-1">
            <template #header>
              <div class="flex items-center justify-between">
                <span class="text-sm font-bold">教师建议与评价</span>
                <span v-if="stuEvaluationWeightsText" class="text-xs text-slate-400">
                  {{ stuEvaluationWeightsText }}
                </span>
              </div>
            </template>

            <!-- 加载中 -->
            <div v-if="stuEvaluationLoading" class="flex h-[220px] flex-col items-center justify-center gap-3 text-slate-400">
              <el-icon class="is-loading" :size="24"><Loading /></el-icon>
              <span>AI 正在综合分析学生学情，生成建议与评价...</span>
            </div>

            <!-- 数据不足 / 异常 -->
            <div v-else-if="stuEvaluationError" class="flex h-[220px] flex-col items-center justify-center gap-2 text-center">
              <el-icon :size="28" class="text-amber-500"><WarningFilled /></el-icon>
              <p class="text-sm text-slate-600">{{ stuEvaluationError }}</p>
              <p v-if="stuEvaluationMissing.length" class="text-xs text-slate-400">
                缺失维度：{{ stuEvaluationMissing.join('、') }}
              </p>
            </div>

            <!-- 评价内容 -->
            <template v-else>
              <el-input
                v-model="teacherSuggestion"
                type="textarea"
                :rows="8"
                placeholder="点击「生成建议」，AI 将综合学生 AI 评级与知识图谱进度两个维度，生成个性化建议与评价。"
              />
              <div v-if="stuEvaluationNotes" class="mt-2 rounded-lg bg-amber-50/80 p-2 text-xs text-amber-700">
                {{ stuEvaluationNotes }}
              </div>
            </template>

            <div class="mt-4 flex justify-end gap-2">
              <el-button
                size="small"
                :loading="stuEvaluationLoading"
                :disabled="currentStudent === null || selectedCourse === null"
                @click="loadStuEvaluation"
              >
                {{ stuEvaluationLoading ? '生成中...' : '生成建议' }}
              </el-button>
              <el-button
                type="primary"
                size="small"
                :loading="stuEvaluationSaving"
                :disabled="!teacherSuggestion.trim() || currentStudent === null || selectedCourse === null"
                @click="saveStuEvaluation"
              >
                保存
              </el-button>
            </div>
          </el-card>
        </div>

        <div class="flex flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
          <!-- 图谱工具栏 -->
          <div class="flex items-center gap-3 border-b border-slate-200 bg-white/70 px-3 py-2 backdrop-blur">
            <div class="flex flex-1 items-center gap-2 text-sm text-slate-600">
              <el-icon :size="16"><Share /></el-icon>
              <span class="font-semibold text-slate-800">学生个人知识图谱</span>
              <span v-if="studentGraphLoading" class="text-xs text-slate-400">加载中...</span>
            </div>
            <div v-if="studentGraphData" class="flex items-center gap-2">
              <el-switch v-model="studentShowLabels" active-text="标签" size="small" />
              <el-button-group size="small">
                <el-button :icon="ZoomIn" @click="studentZoomIn" />
                <el-button :icon="ZoomOut" @click="studentZoomOut" />
                <el-button :icon="Refresh" @click="studentResetView" />
              </el-button-group>
            </div>
          </div>

          <!-- 面包屑导航 -->
          <div v-if="studentDrillPath.length > 0" class="flex items-center gap-1 border-b border-slate-200 bg-white/70 px-3 py-1.5 text-xs backdrop-blur">
            <span class="cursor-pointer text-slate-500 hover:text-slate-800" @click="studentDrillPath = []">全部章节</span>
            <template v-for="(node, idx) in studentDrillPath" :key="node.id">
              <span class="text-slate-300">&gt;</span>
              <span
                class="cursor-pointer"
                :class="idx === studentDrillPath.length - 1 ? 'font-semibold text-slate-800' : 'text-slate-500 hover:text-slate-800'"
                @click="studentDrillPath = studentDrillPath.slice(0, idx + 1)"
              >
                {{ node.name }}
              </span>
            </template>
          </div>

          <!-- 图例 -->
          <div v-if="studentIsKnowledgePointLevel" class="flex flex-wrap gap-1 border-b border-slate-200 bg-white/70 px-3 py-1.5 backdrop-blur">
            <div
              v-for="(color, type) in STUDENT_TYPE_COLORS"
              :key="type"
              class="flex cursor-pointer items-center gap-1 rounded px-1.5 py-0.5 text-xs"
              :class="studentActiveTypes.has(type) ? 'text-slate-400' : 'text-slate-600'"
              @click="studentToggleType(type)"
            >
              <span class="h-2 w-2 rounded-full" :style="{ background: color }" />
              <span>{{ type }}</span>
            </div>
          </div>

          <!-- 图谱主体 -->
          <div class="relative flex-1 overflow-hidden">
            <!-- 加载状态 -->
            <div v-if="studentGraphLoading" class="absolute inset-0 flex items-center justify-center">
              <el-skeleton :rows="5" animated class="w-2/3" />
            </div>

            <!-- 错误/空状态 -->
            <div v-else-if="studentGraphError" class="absolute inset-0 flex flex-col items-center justify-center text-sm text-slate-400">
              <el-icon :size="40" class="mb-2"><Share /></el-icon>
              <p>{{ studentGraphError }}</p>
            </div>

            <!-- 图谱视图 -->
            <template v-else-if="studentGraphData">
              <KnowledgeGraph3D
                v-if="studentIsKnowledgePointLevel"
                ref="studentGraphRef3D"
                :data="studentCurrentGraphData!"
                :show-labels="studentShowLabels"
                :active-types="studentActiveTypes"
                :expanded-node-ids="studentAllExpandedNodeIds"
                :anchor-node-ids="studentAnchorNodeIds"
                :highlighted-node-ids="studentHighlightedNodeIds"
                :node-fx-map="studentNodeFxMap"
                @node-click="studentHandleNodeClick"
                @node-dbl-click="studentHandleNodeDblClick"
              />
              <KnowledgeGraph2D
                v-else
                ref="studentGraphRef2D"
                :data="studentCurrentGraphData!"
                :show-labels="studentShowLabels"
                @node-click="studentHandleNodeClick"
              />
              <!-- 本地详情面板（不依赖全局知识图谱 store） -->
              <div v-if="studentSelectedNode" class="student-detail-panel">
                <div class="panel-header">
                  <h3>{{ studentSelectedNode.name }}</h3>
                  <el-tag :color="studentTypeColor(studentSelectedNode.type)" effect="dark" size="small">
                    {{ studentSelectedNode.type }}
                  </el-tag>
                  <el-button class="close-btn" :icon="Close" text @click="studentSelectedNode = null" />
                </div>
                <div class="panel-body">
                  <p class="description">{{ studentSelectedNode.description || '暂无描述' }}</p>
                  <div class="section">
                    <h4>关系</h4>
                    <div v-if="studentSelectedRelations.length" class="relation-list">
                      <div v-for="(rel, idx) in studentSelectedRelations" :key="idx" class="relation-item">
                        <span class="rel-direction">{{ rel.direction }}</span>
                        <span class="rel-node">{{ rel.targetName }}</span>
                        <span class="rel-name">{{ rel.name }}</span>
                      </div>
                    </div>
                    <el-empty v-else description="暂无关联关系" :image-size="40" />
                  </div>
                  <div class="section">
                    <h4>属性</h4>
                    <div class="attr-list">
                      <div class="attr-item">
                        <span class="attr-key">Degree</span>
                        <span class="attr-value">{{ studentSelectedNode.degree }}</span>
                      </div>
                      <div class="attr-item">
                        <span class="attr-key">ID</span>
                        <span class="attr-value">{{ studentSelectedNode.id }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type ComponentPublicInstance,
} from 'vue'
import { ElMessage } from 'element-plus'
import { PieChart, Share, ZoomIn, ZoomOut, Refresh, Close, Loading, WarningFilled, DataAnalysis, Flag, MagicStick, Aim, EditPen, ChatLineRound } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import {
  getClassStudents,
  getClassTeachingSuggestion,
  getDifficultChapters,
  getDifficultKnowledge,
  getStudentKnowledgeGraph,
  getStuEvaluation,
  getTeacherClasses,
  getTeacherCourses,
  saveStuEvaluation,
  type ClassStudent,
  type ClassTeachingSuggestion,
  type DifficultChapter,
  type DifficultKnowledgePoint,
  type StudentKnowledgeGraph,
  type StuEvaluation,
  type TeacherClass,
  type TeacherCourse,
} from '@/api/teacher'
import KnowledgeGraph3D from '@/components/KnowledgeGraph3D.vue'
import KnowledgeGraph2D from '@/components/KnowledgeGraph2D.vue'
import { parseHierarchy, getVisibleData, tryDrillInto } from '@/utils/kgHierarchy'
import type { GraphNode, GraphData } from '@/api/knowledge'

const selectedClass = ref<number | null>(null)
const selectedCourse = ref<number | null>(null)
const classList = ref<TeacherClass[]>([])
const courseList = ref<TeacherCourse[]>([])
const studentList = ref<ClassStudent[]>([])
const wordCloudList = ref<DifficultKnowledgePoint[]>([])
const difficultChapterList = ref<DifficultChapter[]>([])
const studentDialogVisible = ref(false)
const teacherSuggestion = ref('')
const currentStudent = ref<ClassStudent | null>(null)

// ===== 教师建议与评价（专职 ReAct Agent，双维度评估） =====
const stuEvaluationLoading = ref(false)
const stuEvaluationSaving = ref(false)
const stuEvaluationError = ref('')
const stuEvaluationMissing = ref<string[]>([])
const stuEvaluationNotes = ref('')
const stuEvaluationWeights = ref<Record<string, number>>({})

const STU_DIMENSION_LABELS_MAP: Record<string, string> = {
  level: '学生 AI 评级',
  knowledge_mastery: '知识点掌握程度',
  course_mastery: '学科掌握程度',
}
const stuDimensionLabel = (key: string) => STU_DIMENSION_LABELS_MAP[key] || key
const stuEvaluationWeightsText = computed(() => {
  const parts = Object.entries(stuEvaluationWeights.value)
    .filter(([, w]) => w > 0)
    .map(([k, w]) => `${stuDimensionLabel(k)} ${(w * 100).toFixed(0)}%`)
  return parts.length ? `权重：${parts.join('、')}` : ''
})

// ===== AI 班级教学建议（三维度评估） =====
const teachingSuggestionLoading = ref(false)
const teachingSuggestion = ref<ClassTeachingSuggestion['suggestion'] | null>(null)
const teachingSuggestionWeights = ref<Record<string, number>>({})
const teachingSuggestionError = ref('')
const teachingSuggestionMissing = ref<string[]>([])
const classAiLevel = ref<string | null>(null)
const classAvgProcess = ref<number | null>(null)

const DIMENSION_LABELS_MAP: Record<string, string> = {
  student_level: '学生评级',
  class_mastery: '班级知识点平均掌握度进度',
  difficult: '疑难章节与知识点',
}

const dimensionLabel = (key: string) => DIMENSION_LABELS_MAP[key] || key

const AI_LEVEL_COLORS: Record<string, string> = {
  A: 'text-emerald-600',
  B: 'text-sky-600',
  C: 'text-amber-500',
  D: 'text-orange-500',
  E: 'text-red-500',
}
const aiLevelColor = computed(() => (classAiLevel.value ? AI_LEVEL_COLORS[classAiLevel.value] || 'text-slate-900' : 'text-slate-400'))
const classAvgProcessText = computed(() =>
  classAvgProcess.value === null || classAvgProcess.value === undefined
    ? '--'
    : `${(classAvgProcess.value * 100).toFixed(1)}%`,
)

const loadTeachingSuggestion = async () => {
  if (selectedClass.value === null || selectedCourse.value === null) return
  teachingSuggestionLoading.value = true
  teachingSuggestion.value = null
  teachingSuggestionError.value = ''
  teachingSuggestionMissing.value = []
  teachingSuggestionWeights.value = {}
  classAiLevel.value = null
  classAvgProcess.value = null

  try {
    const data = await getClassTeachingSuggestion(selectedClass.value, selectedCourse.value)
    if (data.status === 'ok' && data.suggestion) {
      teachingSuggestion.value = data.suggestion
      teachingSuggestionWeights.value = data.weights || {}
      classAiLevel.value = data.ai_level || data.suggestion.ai_level || null
      classAvgProcess.value = data.course_avg_process ?? null
    } else if (data.status === 'insufficient') {
      teachingSuggestionError.value =
        data.error_message || '当前数据不足，暂时无法给出教学建议。'
      teachingSuggestionMissing.value = data.missing_dimensions || []
    } else {
      teachingSuggestionError.value =
        data.error_message || 'AI 教学建议服务暂时不可用，请稍后重试。'
    }
  } catch (error) {
    console.error('生成班级教学建议失败:', error)
    teachingSuggestionError.value = '生成班级教学建议失败，请稍后重试'
  } finally {
    teachingSuggestionLoading.value = false
  }
}

// ===== 学生个人知识图谱（复用学生端知识图谱设计） =====
const studentGraphData = ref<StudentKnowledgeGraph | null>(null)
const studentGraphLoading = ref(false)
const studentGraphError = ref('')
const studentShowLabels = ref(true)
const studentSelectedNode = ref<GraphNode | null>(null)
const studentGraphRef3D = ref<InstanceType<typeof KnowledgeGraph3D>>()
const studentGraphRef2D = ref<InstanceType<typeof KnowledgeGraph2D>>()

// 掌握度映射：节点名 → 掌握度(0~1)，用于节点球"装水"可视化
const studentMasteryMap = ref<Record<string, number>>({})

// 钻取状态
const studentDrillPath = ref<GraphNode[]>([])

// 双击展开状态
const studentExpandedNodeMap = ref<Map<string, Set<string>>>(new Map())
const studentHighlightedNodeIds = ref<Set<string>>(new Set())
const studentNodeFxMap = ref<Record<string, { fx: number; fy: number }>>({})

const studentExpandedRefCount = computed(() => {
  const counter = new Map<string, number>()
  for (const addedNodes of studentExpandedNodeMap.value.values()) {
    for (const nodeId of addedNodes) {
      counter.set(nodeId, (counter.get(nodeId) || 0) + 1)
    }
  }
  return counter
})
const studentAllExpandedNodeIds = computed(() => new Set(studentExpandedRefCount.value.keys()))
const studentAnchorNodeIds = computed(() => new Set(studentExpandedNodeMap.value.keys()))

const STUDENT_TYPE_COLORS: Record<string, string> = {
  Concept: '#7C3AED', Algorithm: '#F59E0B', DataStructure: '#10B981',
  Protocol: '#3B82F6', Principle: '#EC4899', Term: '#94A3B8',
  Technology: '#06B6D4', Model: '#F97316',
}
const studentActiveTypes = ref<Set<string>>(new Set())

const studentHierarchy = computed(() => {
  if (!studentGraphData.value) return null
  return parseHierarchy(studentGraphData.value.graph)
})

const studentCurrentGraphData = computed<GraphData | null>(() => {
  if (!studentGraphData.value || !studentHierarchy.value) return null
  const base = getVisibleData(studentGraphData.value.graph, studentDrillPath.value, studentHierarchy.value)

  const injectMastery = (nodes: GraphNode[]) =>
    nodes.map(n => ({ ...n, mastery: studentMasteryMap.value[n.name] ?? 0 }))

  if (studentExpandedNodeMap.value.size === 0) {
    return { ...base, nodes: injectMastery(base.nodes) }
  }

  const baseNodeIds = new Set(base.nodes.map(n => n.id))
  const mergedNodes = [...base.nodes]
  for (const nodeId of studentAllExpandedNodeIds.value) {
    if (!baseNodeIds.has(nodeId)) {
      const fullNode = studentHierarchy.value.nodeMap.get(nodeId)
      if (fullNode) mergedNodes.push(fullNode)
    }
  }
  const mergedNodeIds = new Set(mergedNodes.map(n => n.id))
  const mergedEdges = studentGraphData.value.graph.edges.filter(
    e => mergedNodeIds.has(e.source) && mergedNodeIds.has(e.target),
  )
  const typeCounter: Record<string, number> = {}
  for (const n of mergedNodes) {
    typeCounter[n.type] = (typeCounter[n.type] || 0) + 1
  }
  return {
    nodes: injectMastery(mergedNodes),
    edges: mergedEdges,
    stats: {
      total_nodes: mergedNodes.length,
      total_edges: mergedEdges.length,
      node_types: typeCounter,
    },
  }
})

const studentIsKnowledgePointLevel = computed(() => {
  if (studentDrillPath.value.length === 0) return false
  const currentChapter = studentDrillPath.value[studentDrillPath.value.length - 1]
  const subSections = studentHierarchy.value?.chapterChildren.get(currentChapter.id)
  return (
    studentDrillPath.value.length === 2 ||
    (studentDrillPath.value.length === 1 && (subSections?.length || 0) === 0)
  )
})

const studentToggleType = (type: string) => {
  const next = new Set(studentActiveTypes.value)
  if (next.has(type)) next.delete(type)
  else next.add(type)
  studentActiveTypes.value = next
}

const studentHandleNodeClick = (node: GraphNode) => {
  if (!studentHierarchy.value) return
  const newPath = tryDrillInto(node, studentDrillPath.value, studentHierarchy.value)
  if (newPath !== null) {
    studentDrillPath.value = newPath
    studentSelectedNode.value = null
  } else {
    studentSelectedNode.value = node
  }
}

const studentCalculateGrowthPositions = (
  anchorPos: { x: number; y: number },
  centerPos: { x: number; y: number },
  newNeighborIds: string[],
): Map<string, { fx: number; fy: number }> => {
  const result = new Map<string, { fx: number; fy: number }>()
  const dx = anchorPos.x - centerPos.x
  const dy = anchorPos.y - centerPos.y
  const dist = Math.sqrt(dx * dx + dy * dy)
  if (dist < 1) {
    const baseDistance = 280
    newNeighborIds.forEach((id, i) => {
      const angle = (2 * Math.PI * i) / newNeighborIds.length
      result.set(id, {
        fx: anchorPos.x + baseDistance * Math.cos(angle),
        fy: anchorPos.y + baseDistance * Math.sin(angle),
      })
    })
    return result
  }
  const nx = dx / dist
  const ny = dy / dist
  const extensionDist = Math.max(500, dist * 1.4)
  if (newNeighborIds.length === 1) {
    result.set(newNeighborIds[0], {
      fx: anchorPos.x + nx * extensionDist,
      fy: anchorPos.y + ny * extensionDist,
    })
  } else {
    const spreadAngle = Math.min(Math.PI * 0.85, Math.PI / 2 + (Math.PI / 6) * newNeighborIds.length / 5)
    newNeighborIds.forEach((id, i) => {
      const ratio = newNeighborIds.length > 1 ? i / (newNeighborIds.length - 1) - 0.5 : 0
      const angle = ratio * spreadAngle
      const cosA = Math.cos(angle)
      const sinA = Math.sin(angle)
      const fxDir = nx * cosA - ny * sinA
      const fyDir = nx * sinA + ny * cosA
      const distFromAnchor = extensionDist * (1 + Math.abs(ratio) * 0.3)
      result.set(id, {
        fx: anchorPos.x + fxDir * distFromAnchor,
        fy: anchorPos.y + fyDir * distFromAnchor,
      })
    })
  }
  return result
}

const studentHandleNodeDblClick = (node: GraphNode) => {
  if (!studentHierarchy.value || !studentGraphData.value) return

  if (studentExpandedNodeMap.value.has(node.id)) {
    const newMap = new Map(studentExpandedNodeMap.value)
    newMap.delete(node.id)
    studentExpandedNodeMap.value = newMap
    studentHighlightedNodeIds.value = new Set()
    studentNodeFxMap.value = {}
    return
  }

  let currentPositions = new Map<string, { x: number; y: number }>()
  if (studentGraphRef3D.value) {
    try {
      currentPositions = studentGraphRef3D.value.getNodePositions()
    } catch {
      currentPositions = new Map()
    }
  }

  const kpTypes = new Set(['Concept', 'Algorithm', 'DataStructure', 'Protocol', 'Principle', 'Term', 'Technology', 'Model'])
  const adj = new Map<string, string[]>()
  for (const edge of studentGraphData.value.graph.edges) {
    if (!adj.has(edge.source)) adj.set(edge.source, [])
    if (!adj.has(edge.target)) adj.set(edge.target, [])
    adj.get(edge.source)!.push(edge.target)
    adj.get(edge.target)!.push(edge.source)
  }

  const visited = new Set<string>([node.id])
  const queue: string[] = [node.id]
  const oneHopNeighbors = new Set<string>()
  let distance = 0
  while (queue.length > 0 && distance < 1) {
    const levelSize = queue.length
    for (let i = 0; i < levelSize; i++) {
      const cur = queue.shift()!
      const neighbors = adj.get(cur) || []
      for (const nb of neighbors) {
        if (!visited.has(nb)) {
          visited.add(nb)
          queue.push(nb)
          const nbNode = studentHierarchy.value.nodeMap.get(nb)
          if (nbNode && kpTypes.has(nbNode.type) && nb !== node.id) {
            oneHopNeighbors.add(nb)
          }
        }
      }
    }
    distance++
  }

  const base = getVisibleData(studentGraphData.value.graph, studentDrillPath.value, studentHierarchy.value)
  const baseNodeIds = new Set(base.nodes.map(n => n.id))
  const existingNeighborIds = new Set<string>()
  const newNeighborIds: string[] = []
  for (const nbId of oneHopNeighbors) {
    if (baseNodeIds.has(nbId)) existingNeighborIds.add(nbId)
    else newNeighborIds.push(nbId)
  }

  if (newNeighborIds.length === 0 && existingNeighborIds.size === 0) return

  let centerX = 0
  let centerY = 0
  let count = 0
  for (const [id, pos] of currentPositions) {
    if (baseNodeIds.has(id)) {
      centerX += pos.x
      centerY += pos.y
      count++
    }
  }
  if (count > 0) {
    centerX /= count
    centerY /= count
  }

  const anchorPos = currentPositions.get(node.id)
  if (!anchorPos) {
    const fallbackMap = new Map<string, Set<string>>()
    fallbackMap.set(node.id, oneHopNeighbors)
    studentExpandedNodeMap.value = fallbackMap
    studentHighlightedNodeIds.value = existingNeighborIds
    studentNodeFxMap.value = {}
    return
  }

  const growthPositions = studentCalculateGrowthPositions(
    anchorPos,
    { x: centerX, y: centerY },
    newNeighborIds,
  )

  const fxMap = new Map<string, { fx: number; fy: number }>()
  for (const [id, pos] of currentPositions) {
    if (baseNodeIds.has(id) || oneHopNeighbors.has(id) || id === node.id) {
      fxMap.set(id, { fx: pos.x, fy: pos.y })
    }
  }
  for (const [id, pos] of growthPositions) {
    fxMap.set(id, pos)
  }

  const newMap = new Map<string, Set<string>>()
  newMap.set(node.id, oneHopNeighbors)
  studentExpandedNodeMap.value = newMap
  studentHighlightedNodeIds.value = new Set(existingNeighborIds)

  const fxMapObj: Record<string, { fx: number; fy: number }> = {}
  for (const [id, pos] of fxMap) {
    fxMapObj[id] = pos
  }
  studentNodeFxMap.value = fxMapObj
}

const studentZoomIn = () => {
  if (studentIsKnowledgePointLevel.value) studentGraphRef3D.value?.zoomIn()
  else studentGraphRef2D.value?.zoomIn()
}
const studentZoomOut = () => {
  if (studentIsKnowledgePointLevel.value) studentGraphRef3D.value?.zoomOut()
  else studentGraphRef2D.value?.zoomOut()
}
const studentResetView = () => {
  if (studentIsKnowledgePointLevel.value) studentGraphRef3D.value?.resetView()
  else studentGraphRef2D.value?.resetView()
}

// 学生详情面板中展示的关联关系（本地计算，避免依赖全局知识图谱 store）
const studentSelectedRelations = computed(() => {
  if (!studentSelectedNode.value || !studentGraphData.value) return []
  const nodeId = studentSelectedNode.value.id
  return studentGraphData.value.graph.edges
    .filter(e => e.source === nodeId || e.target === nodeId)
    .map(e => {
      const isOutgoing = e.source === nodeId
      const otherId = isOutgoing ? e.target : e.source
      const otherNode = studentGraphData.value!.graph.nodes.find(n => n.id === otherId)
      return {
        name: e.relationship_name,
        direction: isOutgoing ? '→' : '←',
        targetName: otherNode?.name || otherId,
      }
    })
    .slice(0, 20)
})

const studentTypeColor = (type: string) => STUDENT_TYPE_COLORS[type] || '#94A3B8'

const loadStudentKnowledgeGraph = async (studentId: number, courseId: number) => {
  studentGraphLoading.value = true
  studentGraphError.value = ''
  studentGraphData.value = null
  studentDrillPath.value = []
  studentExpandedNodeMap.value = new Map()
  studentHighlightedNodeIds.value = new Set()
  studentNodeFxMap.value = {}
  studentSelectedNode.value = null
  studentActiveTypes.value = new Set()
  studentMasteryMap.value = {}

  try {
    const data = await getStudentKnowledgeGraph(studentId, courseId)
    // 后端严格校验教师-班级-学科-学生对应，越权返回空对象
    if (!data || !data.graph || !data.graph.nodes || data.graph.nodes.length === 0) {
      studentGraphError.value = '暂无该学生的知识图谱数据（可能未构建或无权查看）'
      return
    }
    studentGraphData.value = data

    // 构建 节点名 → 掌握度 映射
    const map: Record<string, number> = {}
    const walk = (degree: number, name: string) => {
      map[name] = Math.max(0, Math.min(1, degree / 5))
    }
    const hierarchy = data.mastery
    if (hierarchy && hierarchy.chapters) {
      for (const chapter of hierarchy.chapters) {
        walk(chapter.degree, chapter.name)
        for (const section of chapter.sections) {
          walk(section.degree, section.name)
          for (const kp of section.knowledge_points) {
            walk(kp.degree, kp.name)
          }
        }
        for (const kp of chapter.knowledge_points) {
          walk(kp.degree, kp.name)
        }
      }
    }
    studentMasteryMap.value = map
  } catch (error) {
    console.error('加载学生知识图谱失败:', error)
    studentGraphError.value = '加载学生知识图谱失败，请稍后重试'
  } finally {
    studentGraphLoading.value = false
  }
}

const chapterChartRef = ref<HTMLElement | null>(null)
let chapterChartInstance: echarts.ECharts | null = null

const cloudContainerRef = ref<HTMLElement | null>(null)
const cloudItemRefs = ref<Array<HTMLElement | null>>([])
const cloudPositions = ref<Array<{ x: number; y: number }>>([])
const wordCloudReady = ref(false)

const CLOUD_COLORS = [
  '#ef4444',
  '#f97316',
  '#f59e0b',
  '#eab308',
  '#84cc16',
  '#22c55e',
  '#10b981',
  '#14b8a6',
  '#06b6d4',
  '#0ea5e9',
  '#3b82f6',
  '#6366f1',
  '#8b5cf6',
  '#a855f7',
  '#d946ef',
  '#ec4899',
  '#f43f5e',
  '#64748b',
  '#0f766e',
  '#b45309',
]

const currentClassName = computed(() => {
  const current = classList.value.find((item) => item.class_id === selectedClass.value)
  return current?.class_name ?? '--'
})

const currentClassStudentCount = computed(() => {
  const current = classList.value.find((item) => item.class_id === selectedClass.value)
  if (!current) return '--'
  return current.student_count ?? current.classmates_num ?? '--'
})

const progressPercent = (process: number | null) => {
  if (process === null || process === undefined) return 0
  return Math.round(process * 100)
}

const loadTeacherData = async () => {
  try {
    const [courses, classes] = await Promise.all([
      getTeacherCourses(),
      getTeacherClasses(),
    ])
    courseList.value = courses
    classList.value = classes
    selectedClass.value = classes[0]?.class_id ?? null
    selectedCourse.value = courses[0]?.course_id ?? null
  } catch (error) {
    console.error('加载教师班级/学科数据失败:', error)
    classList.value = []
    courseList.value = []
  }
}

const loadStudents = async () => {
  if (selectedClass.value === null || selectedCourse.value === null) {
    studentList.value = []
    return
  }

  try {
    studentList.value = await getClassStudents(selectedClass.value, selectedCourse.value)
  } catch (error) {
    console.error('加载班级学生列表失败:', error)
    studentList.value = []
  }
}

const renderWordCloud = async () => {
  wordCloudReady.value = false
  await nextTick()
  computeCloudLayout()
}

const loadWordCloud = async () => {
  if (selectedClass.value === null || selectedCourse.value === null) {
    wordCloudList.value = []
    cloudItemRefs.value = []
    cloudPositions.value = []
    wordCloudReady.value = false
    return
  }

  try {
    cloudItemRefs.value = []
    wordCloudList.value = await getDifficultKnowledge(selectedClass.value, selectedCourse.value)
    cloudPositions.value = []
    if (wordCloudList.value.length > 0) {
      await renderWordCloud()
    } else {
      wordCloudReady.value = false
    }
  } catch (error) {
    console.error('加载疑难知识点词云失败:', error)
    wordCloudList.value = []
    cloudItemRefs.value = []
    cloudPositions.value = []
    wordCloudReady.value = false
  }
}

const loadDashboardData = async () => {
  await Promise.all([loadStudents(), loadWordCloud(), loadDifficultChapters()])
}

const renderChapterChart = async () => {
  await nextTick()
  if (difficultChapterList.value.length === 0) return
  const el = chapterChartRef.value
  if (!el) return

  if (!chapterChartInstance) {
    chapterChartInstance = echarts.init(el)
  }
  chapterChartInstance.setOption({
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const item = params.data
        return `${item.name}<br/>错题知识点数：${item.count}<br/>占比：${(item.ratio * 100).toFixed(1)}%`
      },
    },
    legend: {
      orient: 'vertical',
      right: 8,
      bottom: 8,
      type: 'scroll',
      textStyle: { fontSize: 12 },
    },
    series: [
      {
        name: '疑难章节',
        type: 'pie',
        radius: ['42%', '70%'],
        center: ['38%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 6,
          borderColor: '#fff',
          borderWidth: 2,
        },
        label: {
          show: true,
          formatter: '{b}\n{d}%',
          fontSize: 11,
        },
        emphasis: {
          label: { show: true, fontWeight: 'bold' },
        },
        data: difficultChapterList.value.map((item) => ({
          name: item.name,
          value: item.count,
          ratio: item.ratio,
        })),
      },
    ],
  })
}

const loadDifficultChapters = async () => {
  if (selectedClass.value === null || selectedCourse.value === null) {
    difficultChapterList.value = []
    return
  }

  try {
    difficultChapterList.value = await getDifficultChapters(
      selectedClass.value,
      selectedCourse.value,
    )
    await renderChapterChart()
  } catch (error) {
    console.error('加载疑难章节分布失败:', error)
    difficultChapterList.value = []
  }
}

const setCloudItemRef = (
  el: Element | ComponentPublicInstance | null,
  idx: number,
) => {
  cloudItemRefs.value[idx] = el as HTMLElement | null
}

const cloudFontSize = (item: DifficultKnowledgePoint) => {
  const maxRatio = wordCloudList.value[0]?.ratio || 1
  return 14 + (item.ratio / maxRatio) * 18
}

const computeCloudLayout = () => {
  const container = cloudContainerRef.value
  const items = wordCloudList.value
  if (!container || items.length === 0) {
    wordCloudReady.value = false
    return
  }

  const width = container.clientWidth
  const height = container.clientHeight
  const halfWidth = Math.max(width / 2 - 18, 0)
  const halfHeight = Math.max(height / 2 - 18, 0)
  const maxRadius = Math.hypot(halfWidth, halfHeight)

  const boxes = items.map((item, idx) => {
    const el = cloudItemRefs.value[idx]
    return {
      width: el?.offsetWidth ?? item.name.length * cloudFontSize(item),
      height: el?.offsetHeight ?? cloudFontSize(item) * 1.5,
    }
  })

  const placed: Array<{ cx: number; cy: number; hw: number; hh: number }> = []
  const positions: Array<{ x: number; y: number }> = []

  const overlaps = (cx: number, cy: number, hw: number, hh: number) => {
    const gap = 8
    return placed.some((item) => {
      return (
        Math.abs(cx - item.cx) < hw + item.hw + gap &&
        Math.abs(cy - item.cy) < hh + item.hh + gap
      )
    })
  }

  const outOfBounds = (cx: number, cy: number, hw: number, hh: number) => {
    return Math.abs(cx) + hw > halfWidth || Math.abs(cy) + hh > halfHeight
  }

  boxes.forEach((box, idx) => {
    const hw = box.width / 2
    const hh = box.height / 2

    if (idx === 0) {
      placed.push({ cx: 0, cy: 0, hw, hh })
      positions.push({ x: 0, y: 0 })
      return
    }

    let candidateX = 0
    let candidateY = 0
    let found = false

    for (let step = 1; step <= 2400; step += 1) {
      const angle = step * 2.399963229728653
      const radius = Math.min(maxRadius, 6 + step * 2.2)
      const tx = Math.cos(angle) * radius
      const ty = Math.sin(angle) * radius

      if (outOfBounds(tx, ty, hw, hh)) {
        continue
      }

      candidateX = tx
      candidateY = ty

      if (!overlaps(tx, ty, hw, hh)) {
        found = true
        break
      }
    }

    placed.push({ cx: candidateX, cy: candidateY, hw, hh })
    positions.push({
      x: candidateX,
      y: candidateY,
    })

    if (!found) {
      console.warn(`词云项 "${items[idx]?.name}" 未找到完全无碰撞位置，已使用兜底位置`)
    }
  })

  cloudPositions.value = positions
  wordCloudReady.value = true
}

const wordCloudStyle = (item: DifficultKnowledgePoint, idx: number) => {
  const position = cloudPositions.value[idx] ?? { x: 0, y: 0 }
  return {
    fontSize: `${cloudFontSize(item)}px`,
    color: CLOUD_COLORS[idx % CLOUD_COLORS.length],
    '--cloud-x': `${position.x}px`,
    '--cloud-y': `${position.y}px`,
    zIndex: Math.max(1, 30 - idx),
  } as Record<string, string | number>
}

const openStudentDetail = (student: ClassStudent) => {
  currentStudent.value = student
  teacherSuggestion.value = ''
  stuEvaluationError.value = ''
  stuEvaluationMissing.value = []
  stuEvaluationNotes.value = ''
  stuEvaluationWeights.value = {}
  studentDialogVisible.value = true
  // 加载该学生在当前所选学科下的个人知识图谱
  if (selectedCourse.value !== null) {
    void loadStudentKnowledgeGraph(student.stu_id, selectedCourse.value)
  }
}

// 生成教师对单个学生的建议与评价（AI 专职 ReAct Agent，双维度评估）
const loadStuEvaluation = async () => {
  if (currentStudent.value === null || selectedCourse.value === null) return
  stuEvaluationLoading.value = true
  stuEvaluationError.value = ''
  stuEvaluationMissing.value = []
  stuEvaluationNotes.value = ''
  stuEvaluationWeights.value = {}
  teacherSuggestion.value = ''

  try {
    const data = await getStuEvaluation(currentStudent.value.stu_id, selectedCourse.value)
    if (data.status === 'ok' && data.evaluation) {
      stuEvaluationWeights.value = data.weights || {}
      stuEvaluationNotes.value = data.evaluation.teacher_notes || ''
      // 将结构化评价组装为可编辑文本，供教师审阅/修改后保存
      const lines: string[] = []
      lines.push(`【整体评价】${data.evaluation.overall_assessment || ''}`)
      if (data.evaluation.strengths?.length) {
        lines.push(`【优势】${data.evaluation.strengths.join('；')}`)
      }
      if (data.evaluation.weaknesses?.length) {
        lines.push(`【薄弱点】${data.evaluation.weaknesses.join('；')}`)
      }
      if (data.evaluation.suggestions?.length) {
        lines.push('【建议】')
        for (const s of data.evaluation.suggestions) {
          lines.push(`- ${s.suggestion}：${s.detail}`)
        }
      }
      if (data.evaluation.priority_focus?.length) {
        lines.push(`【优先改进】${data.evaluation.priority_focus.join('、')}`)
      }
      teacherSuggestion.value = lines.join('\n')
    } else if (data.status === 'insufficient') {
      stuEvaluationError.value =
        data.error_message || '当前数据不足，暂时无法给出建议与评价。'
      stuEvaluationMissing.value = data.missing_dimensions || []
    } else {
      stuEvaluationError.value =
        data.error_message || 'AI 建议与评价服务暂时不可用，请稍后重试。'
    }
  } catch (error) {
    console.error('生成教师建议与评价失败:', error)
    stuEvaluationError.value = '生成教师建议与评价失败，请稍后重试'
  } finally {
    stuEvaluationLoading.value = false
  }
}

// 保存教师对某学生的评价到 evaluation_analysis 表
const saveStuEvaluation = async () => {
  if (currentStudent.value === null || selectedCourse.value === null) return
  const content = teacherSuggestion.value.trim()
  if (!content) return
  stuEvaluationSaving.value = true
  try {
    const res = await saveStuEvaluation(currentStudent.value.stu_id, selectedCourse.value, content)
    if (res.success) {
      ElMessage.success(res.message || '评价已保存')
    } else {
      ElMessage.error(res.message || '保存评价失败')
    }
  } catch (error) {
    console.error('保存教师评价失败:', error)
    ElMessage.error('保存教师评价失败，请稍后重试')
  } finally {
    stuEvaluationSaving.value = false
  }
}

const getRatingColor = (level: string | null) => {
  if (level === 'A') return 'text-emerald-600'
  if (level === 'B') return 'text-sky-600'
  if (level === 'C') return 'text-amber-500'
  return 'text-slate-500'
}

const handleResize = () => {
  if (wordCloudList.value.length === 0) return
  window.requestAnimationFrame(() => {
    computeCloudLayout()
    chapterChartInstance?.resize()
  })
}

watch([selectedClass, selectedCourse], () => {
  void loadDashboardData()
})

onMounted(() => {
  void loadTeacherData()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chapterChartInstance?.dispose()
  chapterChartInstance = null
})
</script>

<style scoped>
.teacher-card {
  border-radius: 18px;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(15, 23, 42, 0.04);
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(15, 23, 42, 0.16);
  border-radius: 999px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(15, 23, 42, 0.26);
}

.word-cloud-panel {
  height: 360px;
  overflow: hidden;
  border-radius: 18px;
  background:
    radial-gradient(circle at top, rgba(14, 165, 233, 0.12), transparent 42%),
    radial-gradient(circle at bottom, rgba(249, 115, 22, 0.12), transparent 34%),
    linear-gradient(180deg, rgba(248, 250, 252, 0.98), rgba(241, 245, 249, 0.9));
}

.word-cloud-container {
  position: relative;
  height: 100%;
  width: 100%;
}

.word-cloud-item {
  position: absolute;
  left: 50%;
  top: 50%;
  white-space: nowrap;
  font-weight: 700;
  line-height: 1.1;
  user-select: none;
  opacity: 0;
  text-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
  transform: translate(-50%, -50%) translate(var(--cloud-x), var(--cloud-y));
  transition:
    transform 0.2s ease,
    opacity 0.2s ease,
    filter 0.2s ease;
}

.word-cloud-item--ready {
  opacity: 0.96;
}

.word-cloud-item:hover {
  filter: brightness(1.05);
  transform: translate(-50%, -50%) translate(var(--cloud-x), var(--cloud-y)) scale(1.08);
}

:deep(.student-detail-dialog) {
  border-radius: 16px;
  overflow: hidden;
}

:deep(.student-detail-dialog .el-dialog__body) {
  background: #f8fafc;
  padding: 20px;
}

/* 学生个人知识图谱详情面板 */
.student-detail-panel {
  position: absolute;
  right: 16px;
  top: 16px;
  width: 320px;
  max-height: calc(100% - 32px);
  background: #1a1a2e;
  border: 1px solid #333;
  border-radius: 12px;
  overflow-y: auto;
  z-index: 100;
}
.student-detail-panel .panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border-bottom: 1px solid #2a2a3e;
}
.student-detail-panel .panel-header h3 {
  margin: 0;
  font-size: 16px;
  color: #f4f4f4;
  flex: 1;
}
.student-detail-panel .close-btn { color: #94a3b8; }
.student-detail-panel .panel-body { padding: 16px; }
.student-detail-panel .description {
  font-size: 13px;
  color: #aaa;
  line-height: 1.6;
  margin: 0 0 16px;
}
.student-detail-panel .section { margin-bottom: 16px; }
.student-detail-panel .section h4 {
  font-size: 12px;
  color: #94a3b8;
  text-transform: uppercase;
  margin: 0 0 8px;
  letter-spacing: 0.05em;
}
.student-detail-panel .relation-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 0;
  font-size: 13px;
}
.student-detail-panel .rel-direction { color: #3b82f6; font-weight: bold; }
.student-detail-panel .rel-node { color: #f4f4f4; }
.student-detail-panel .rel-name { color: #94a3b8; font-size: 11px; margin-left: auto; }
.student-detail-panel .attr-item {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
}
.student-detail-panel .attr-key { color: #94a3b8; }
.student-detail-panel .attr-value { color: #f4f4f4; }
</style>
