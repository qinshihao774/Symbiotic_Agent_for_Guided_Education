<template>
  <BorderGlow class="practice-home-page" background-color="transparent">
    <div class="glass-card page-container">
      <h2 class="page-title">题目练习</h2>
      
      <div class="grid-container">
        <div 
          v-for="module in practiceModules" 
          :key="module.id" 
          class="module-card glass-card"
          :class="{ 'placeholder-card': module.isPlaceholder }"
          @click="navigateToPanel(module)"
        >
          <span class="module-name">{{ module.name }}</span>
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
import { fetchCourses, type Course } from '@/api/practice'

const router = useRouter()
const courses = ref<Course[]>([])
const loading = ref(true)

// 固定显示的 6 个模块（包含占位）
const practiceModules = ref([
  { id: 'placeholder-1', name: '学科1', isPlaceholder: true },
  { id: 'placeholder-2', name: '学科2', isPlaceholder: true },
  { id: 'exam', name: '作业与考试', isPlaceholder: true },
  { id: 'placeholder-3', name: '学科3', isPlaceholder: true },
  { id: 'placeholder-4', name: '学科4', isPlaceholder: true },
  { id: 'special', name: '专项练习', isPlaceholder: true }
])

onMounted(async () => {
  try {
    const data = await fetchCourses()
    courses.value = data || []
    
    // 将真实学科填充到占位符中 (前 4 个位置)
    let courseIndex = 0;
    for (let i = 0; i < practiceModules.value.length; i++) {
      if (practiceModules.value[i].id.startsWith('placeholder-') && courseIndex < courses.value.length) {
        practiceModules.value[i] = {
          id: courses.value[courseIndex].course_id.toString(),
          name: courses.value[courseIndex].course_name,
          isPlaceholder: false
        }
        courseIndex++;
      }
    }
  } catch (error) {
    console.error('Failed to fetch courses:', error)
    ElMessage.error('获取学科列表失败')
  } finally {
    loading.value = false
  }
})

const navigateToPanel = (module: any) => {
  if (module.isPlaceholder) {
    ElMessage.warning('功能开发中，敬请期待')
    return
  }
  
  // 直接跳转到题库页面
  router.push({
    path: '/student/practice/panel',
    query: { module: module.id }
  })
}
</script>

<style scoped>
.practice-home-page {
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
  padding: 24px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.5);
}

.page-title {
  margin: 0 0 24px 0;
  font-size: 1.2rem;
  font-weight: bold;
  color: #000;
  flex-shrink: 0;
}

.grid-container {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: repeat(2, 1fr);
  gap: 32px;
  padding: 0 20px 20px 20px;
}

.module-card {
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(0, 0, 0, 0.1);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.05);
}

.module-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
  background: rgba(255, 255, 255, 0.8);
  border-color: rgba(0, 0, 0, 0.2);
}

.module-name {
  font-size: 1.25rem;
  font-weight: 600;
  color: #333;
  text-align: center;
}
</style>