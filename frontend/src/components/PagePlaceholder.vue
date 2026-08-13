<template>
  <div class="placeholder-container">
    <div class="placeholder-card">
      <div class="placeholder-icon">🚧</div>
      <h2 class="placeholder-title">{{ title }}</h2>
      <p class="placeholder-desc">{{ description }}</p>
      <el-tag type="info" size="small">功能开发中</el-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description: string
}>()
</script>

<style scoped>
.placeholder-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  padding: 40px;
}

.placeholder-card {
  text-align: center;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 16px;
  padding: 48px 40px;
  max-width: 420px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.05);
}

.placeholder-icon {
  font-size: 3rem;
  margin-bottom: 16px;
}

.placeholder-title {
  margin: 0 0 12px;
  font-size: 1.3rem;
  font-weight: 600;
  color: #333;
}

.placeholder-desc {
  margin: 0 0 20px;
  color: #999;
  font-size: 0.95rem;
  line-height: 1.6;
}
</style>
