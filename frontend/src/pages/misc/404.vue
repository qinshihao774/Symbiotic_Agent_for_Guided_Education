<template>
  <div class="not-found-page">
    <div class="not-found-card">
      <h1 class="code">404</h1>
      <p class="message">页面未找到</p>
      <el-button type="primary" @click="$router.push('/')">返回首页</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.not-found-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #f0f2f5;
}

.not-found-card {
  text-align: center;
  padding: 60px 48px;
}

.code {
  font-size: 5rem;
  margin: 0;
  color: #dcdfe6;
}

.message {
  font-size: 1.1rem;
  color: #999;
  margin: 16px 0 32px;
}
</style>
