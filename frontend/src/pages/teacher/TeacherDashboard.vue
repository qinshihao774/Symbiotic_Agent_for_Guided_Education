<template>
  <div class="teacher-dashboard-page">
    <h2 class="page-title">班级学情仪表盘</h2>
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>班级平均分</template>
          <div class="stat-value">82.5</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>学生人数</template>
          <div class="stat-value">48</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>知识点掌握</template>
          <div class="stat-value">76%</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>待预警学生</template>
          <div class="stat-value warn">3</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.teacher-dashboard-page { padding: 20px; }
.page-title { margin: 0 0 20px; font-size: 1.2rem; font-weight: 600; color: #333; }
.stat-value { font-size: 2rem; font-weight: 700; color: #409eff; text-align: center; padding: 12px 0; }
.stat-value.warn { color: #f56c6c; }
</style>
