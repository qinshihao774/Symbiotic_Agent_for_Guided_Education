<template>
  <div class="kg-editor-toolbar">
    <!-- 工具模式 -->
    <div class="toolbar-section">
      <el-button-group>
        <el-button
          :type="toolMode === 'select' ? 'primary' : 'default'"
          size="small"
          @click="$emit('update:toolMode', 'select')"
        >
          <el-icon><Pointer /></el-icon> 选择
        </el-button>
        <el-button
          :type="toolMode === 'add-node' ? 'primary' : 'default'"
          size="small"
          @click="$emit('update:toolMode', 'add-node')"
        >
          <el-icon><Plus /></el-icon> 添加节点
        </el-button>
        <el-button
          :type="toolMode === 'add-edge' ? 'primary' : 'default'"
          size="small"
          @click="$emit('update:toolMode', 'add-edge')"
        >
          <el-icon><Connection /></el-icon> 添加边
        </el-button>
      </el-button-group>
    </div>

    <!-- 缩放控制 -->
    <div class="toolbar-section">
      <el-button size="small" @click="$emit('zoom-in')">
        <el-icon><ZoomIn /></el-icon>
      </el-button>
      <el-button size="small" @click="$emit('zoom-out')">
        <el-icon><ZoomOut /></el-icon>
      </el-button>
      <el-button size="small" @click="$emit('fit-view')">
        <el-icon><FullScreen /></el-icon>
      </el-button>
    </div>

    <!-- 实体类型筛选 -->
    <div v-if="graphStats" class="toolbar-section type-filter">
      <span class="filter-label">类型筛选：</span>
      <el-button size="small" text @click="selectAll">全选</el-button>
      <el-button size="small" text @click="clearAll">清空</el-button>
      <el-checkbox-group
        :model-value="Array.from(visibleTypes)"
        @update:model-value="onTypeChange"
        size="small"
      >
        <el-checkbox
          v-for="(count, t) in graphStats.node_types"
          :key="t"
          :label="t"
          :value="t"
        >
          <span class="type-dot" :style="{ backgroundColor: TYPE_COLORS[t] || '#94A3B8' }" />
          {{ t }} ({{ count }})
        </el-checkbox>
      </el-checkbox-group>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Pointer, Plus, Connection, ZoomIn, ZoomOut, FullScreen } from '@element-plus/icons-vue'
import { TYPE_COLORS } from '@/constants/knowledgeColors'
import type { GraphStats } from '@/api/knowledge'

const props = defineProps<{
  toolMode: 'select' | 'add-node' | 'add-edge'
  visibleTypes: Set<string>
  graphStats: GraphStats | null
}>()

const emit = defineEmits<{
  'update:toolMode': [mode: 'select' | 'add-node' | 'add-edge']
  'zoom-in': []
  'zoom-out': []
  'fit-view': []
  'update:visibleTypes': [types: Set<string>]
}>()

const allTypes = computed(() => {
  if (!props.graphStats) return [] as string[]
  return Object.keys(props.graphStats.node_types)
})

function onTypeChange(values: string[]) {
  emit('update:visibleTypes', new Set(values))
}

function selectAll() {
  emit('update:visibleTypes', new Set(allTypes.value))
}

function clearAll() {
  emit('update:visibleTypes', new Set())
}
</script>

<style scoped>
.kg-editor-toolbar {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 8px 12px;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
  flex-wrap: wrap;
}
.toolbar-section {
  display: flex;
  align-items: center;
  gap: 4px;
}
.type-filter {
  flex-wrap: wrap;
  gap: 2px 8px;
}
.filter-label {
  font-size: 13px;
  color: #6b7280;
  white-space: nowrap;
}
.type-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 2px;
  vertical-align: middle;
}
</style>
