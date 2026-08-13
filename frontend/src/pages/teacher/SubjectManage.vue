<template>
  <div class="teacher-page h-full flex items-center justify-center p-8">
    <div class="w-full max-w-5xl grid grid-cols-2 gap-12">
      
      <!-- 题库 CRUD 模块 -->
      <div 
        class="subject-card group flex flex-col items-center justify-center gap-6 p-12 aspect-square rounded-3xl bg-white/60 backdrop-blur-xl border border-white/50 shadow-lg cursor-pointer transition-all hover:-translate-y-2 hover:shadow-2xl"
        @click="openQuestionBank"
      >
        <div class="p-6 rounded-full bg-blue-50 text-blue-500 group-hover:scale-110 transition-transform">
          <el-icon :size="64"><DocumentAdd /></el-icon>
        </div>
        <div class="text-center">
          <h2 class="text-2xl font-bold text-gray-800 mb-2">题库管理</h2>
          <p class="text-sm text-gray-500 max-w-[250px]">
            点击进入上传新题界面，可用于题库更新。确保答案正确后可扩充题库、删除、查题目等。
          </p>
        </div>
      </div>

      <!-- 编辑学科知识图谱模块 -->
      <div 
        class="subject-card group flex flex-col items-center justify-center gap-6 p-12 aspect-square rounded-3xl bg-white/60 backdrop-blur-xl border border-white/50 shadow-lg cursor-pointer transition-all hover:-translate-y-2 hover:shadow-2xl"
        @click="openKnowledgeGraphEdit"
      >
        <div class="p-6 rounded-full bg-green-50 text-green-500 group-hover:scale-110 transition-transform">
          <el-icon :size="64"><Connection /></el-icon>
        </div>
        <div class="text-center">
          <h2 class="text-2xl font-bold text-gray-800 mb-2">学科知识图谱管理</h2>
          <p class="text-sm text-gray-500 max-w-[250px]">
            点击进入学科知识图谱界面，进行节点与连线的创建、编辑、删除等操作。
          </p>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { DocumentAdd, Connection } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()

const openQuestionBank = () => {
  ElMessage.info('正在进入题库维护模块...')
  // TODO: 跳转到具体的题库 CRUD 页面
}

const openKnowledgeGraphEdit = () => {
  // 跳转到学科知识图谱管理页面
  router.push('/teacher/kg-manage')
}
</script>

<style scoped>
.subject-card {
  position: relative;
  overflow: hidden;
}
.subject-card::before {
  content: "";
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  border-radius: inherit;
  opacity: 0;
  transition: opacity 0.3s ease;
  background: radial-gradient(
    circle at center,
    rgba(255, 255, 255, 0.8),
    transparent 70%
  );
  z-index: 1;
  pointer-events: none;
}
.subject-card:hover::before {
  opacity: 1;
}
.subject-card > * {
  position: relative;
  z-index: 2;
}
</style>
