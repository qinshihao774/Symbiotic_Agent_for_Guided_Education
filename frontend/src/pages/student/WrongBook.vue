<template>
  <BorderGlow class="wrong-book-page" background-color="transparent">
    <div class="content">WrongBook</div>
  </BorderGlow>
</template>

<script setup lang="ts">
import BorderGlow from '@/components/BorderGlow.vue'
</script>

<style scoped>
.wrong-book-page {
  color: #eceef0;
  min-height: calc(100vh - 40px);
  margin: 20px;
}
.content {
  padding: 20px;
}
</style>
