<template>
  <div class="kg-editor-panel">
    <!-- 概览模式 -->
    <template v-if="mode === 'overview'">
      <div class="panel-header">
        <h3>图谱概览</h3>
      </div>
      <div class="panel-body" v-if="graphStats">
        <div class="stat-item">
          <span class="stat-label">节点数</span>
          <span class="stat-value">{{ graphStats.total_nodes }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">边数</span>
          <span class="stat-value">{{ graphStats.total_edges }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">实体类型</span>
          <span class="stat-value">{{ Object.keys(graphStats.node_types).length }}</span>
        </div>
        <div class="hint-text">点击节点或边查看详情并编辑</div>
      </div>
      <div class="panel-body" v-else>
        <el-empty description="请先选择一个学科" :image-size="60" />
      </div>
    </template>

    <!-- 节点编辑模式 -->
    <template v-else-if="mode === 'node'">
      <div class="panel-header">
        <h3>{{ isNew ? '新增节点' : '编辑节点' }}</h3>
        <el-button text size="small" @click="$emit('cancel-edit')">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
      <div class="panel-body">
        <el-form label-position="top" size="small">
          <el-form-item label="名称">
            <el-input v-model="nodeForm.name" placeholder="输入节点名称" />
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="nodeForm.type" placeholder="选择实体类型">
              <el-option
                v-for="t in entityTypes"
                :key="t"
                :label="t"
                :value="t"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="描述">
            <el-input
              v-model="nodeForm.description"
              type="textarea"
              :rows="4"
              placeholder="输入节点描述"
            />
          </el-form-item>
        </el-form>
        <div class="panel-actions">
          <el-button type="primary" size="small" @click="handleSaveNode" :loading="saving">
            保存
          </el-button>
          <el-button
            v-if="!isNew"
            type="danger"
            plain
            size="small"
            @click="handleDeleteNode"
            :loading="deleting"
          >
            删除
          </el-button>
          <el-button size="small" @click="$emit('cancel-edit')">取消</el-button>
        </div>
      </div>
    </template>

    <!-- 边编辑模式 -->
    <template v-else-if="mode === 'edge'">
      <div class="panel-header">
        <h3>{{ isNew ? '新增关系' : '编辑关系' }}</h3>
        <el-button text size="small" @click="$emit('cancel-edit')">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
      <div class="panel-body">
        <el-form label-position="top" size="small">
          <el-form-item label="起始节点">
            <el-select
              v-if="isNew"
              v-model="edgeForm.source"
              filterable
              placeholder="搜索并选择起始节点"
              style="width: 100%"
              @change="syncEdgeNodeNames"
            >
              <el-option
                v-for="node in graphNodes"
                :key="node.id"
                :label="`${node.name} · ${node.type}`"
                :value="node.id"
              />
            </el-select>
            <el-input v-else :model-value="edgeForm.sourceName" disabled />
          </el-form-item>
          <el-form-item label="目标节点">
            <el-select
              v-if="isNew"
              v-model="edgeForm.target"
              filterable
              placeholder="搜索并选择目标节点"
              style="width: 100%"
              @change="syncEdgeNodeNames"
            >
              <el-option
                v-for="node in graphNodes"
                :key="node.id"
                :label="`${node.name} · ${node.type}`"
                :value="node.id"
                :disabled="node.id === edgeForm.source"
              />
            </el-select>
            <el-input v-else :model-value="edgeForm.targetName" disabled />
          </el-form-item>
          <el-form-item label="关系名称">
            <el-input v-model="edgeForm.relationship_name" placeholder="输入关系名称" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input
              v-model="edgeForm.description"
              type="textarea"
              :rows="3"
              placeholder="输入关系描述"
            />
          </el-form-item>
        </el-form>
        <div class="panel-actions">
          <el-button type="primary" size="small" @click="handleSaveEdge" :loading="saving">
            保存
          </el-button>
          <el-button
            v-if="!isNew"
            type="danger"
            plain
            size="small"
            @click="handleDeleteEdge"
            :loading="deleting"
          >
            删除
          </el-button>
          <el-button size="small" @click="$emit('cancel-edit')">取消</el-button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close } from '@element-plus/icons-vue'
import type { GraphNode, GraphStats } from '@/api/knowledge'
import {
  createNode, updateNode, deleteNode,
  createEdge, updateEdge, deleteEdge,
} from '@/api/knowledge'
import type { NodeEditData, EdgeEditData } from './KgEditorCanvas.vue'

// EntityType 枚举值列表（与 ai/app/kg_pipeline/models.py 的 EntityType 对应）
const entityTypes = [
  'Chapter', 'Concept', 'Algorithm', 'DataStructure', 'Protocol',
  'Principle', 'Term', 'Technology', 'Model', 'Operation',
  'Method', 'Process', 'Function', 'Standard', 'Tool',
]

const props = defineProps<{
  mode: 'overview' | 'node' | 'edge'
  isNew: boolean
  graphName: string
  graphStats: GraphStats | null
  graphNodes: GraphNode[]
  selectedNode: NodeEditData | null
  selectedEdge: EdgeEditData | null
}>()

const emit = defineEmits<{
  'cancel-edit': []
  'node-saved': [data: NodeEditData]
  'node-deleted': [nodeId: string]
  'edge-saved': [data: EdgeEditData]
  'edge-deleted': [source: string, target: string]
}>()

const saving = ref(false)
const deleting = ref(false)

// ---- 节点表单 ----

const nodeForm = reactive({
  name: '',
  type: 'Concept',
  description: '',
})

// ---- 边表单 ----

const edgeForm = reactive({
  source: '',
  target: '',
  sourceName: '',
  targetName: '',
  relationship_name: '',
  description: '',
})

// ---- 同步选中数据到表单 ----

watch(() => props.selectedNode, (node) => {
  if (node) {
    nodeForm.name = node.name
    nodeForm.type = node.type
    nodeForm.description = node.description
  }
}, { immediate: true })

watch(() => props.selectedEdge, (edge) => {
  if (edge) {
    edgeForm.source = edge.source
    edgeForm.target = edge.target
    edgeForm.sourceName = edge.sourceName
    edgeForm.targetName = edge.targetName
    edgeForm.relationship_name = edge.relationship_name
    edgeForm.description = edge.description
  }
}, { immediate: true })

function syncEdgeNodeNames() {
  edgeForm.sourceName = props.graphNodes.find(node => node.id === edgeForm.source)?.name || ''
  edgeForm.targetName = props.graphNodes.find(node => node.id === edgeForm.target)?.name || ''
}

// ---- 保存节点 ----

async function handleSaveNode() {
  if (!nodeForm.name.trim()) {
    ElMessage.warning('节点名称不能为空')
    return
  }
  saving.value = true
  try {
    if (props.isNew) {
      const result = await createNode(
        props.graphName, nodeForm.name, nodeForm.type, nodeForm.description,
      )
      ElMessage.success('节点创建成功')
      emit('node-saved', {
        id: result.node_id,
        name: result.name,
        type: result.type,
        description: result.description,
      })
    } else if (props.selectedNode) {
      const result = await updateNode(
        props.graphName, props.selectedNode.id,
        { name: nodeForm.name, type: nodeForm.type, description: nodeForm.description },
      )
      ElMessage.success('节点更新成功')
      emit('node-saved', {
        id: result.node_id,
        name: result.name,
        type: result.type,
        description: result.description,
      })
    }
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '操作失败'
    ElMessage.error(msg)
    // 回滚由父组件处理
    emit('cancel-edit')
  } finally {
    saving.value = false
  }
}

// ---- 删除节点 ----

async function handleDeleteNode() {
  if (!props.selectedNode) return
  try {
    await ElMessageBox.confirm(
      `确认删除节点 "${props.selectedNode.name}"？\n该节点的所有关联边也将被删除，此操作不可恢复。`,
      '确认删除',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return // 用户取消
  }

  deleting.value = true
  try {
    await deleteNode(props.graphName, props.selectedNode.id)
    ElMessage.success('节点删除成功')
    emit('node-deleted', props.selectedNode.id)
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '删除失败'
    ElMessage.error(msg)
  } finally {
    deleting.value = false
  }
}

// ---- 保存边 ----

async function handleSaveEdge() {
  if (!edgeForm.relationship_name.trim()) {
    ElMessage.warning('关系名称不能为空')
    return
  }
  saving.value = true
  try {
    if (props.isNew) {
      const result = await createEdge(
        props.graphName, edgeForm.source, edgeForm.target,
        edgeForm.relationship_name, edgeForm.description,
      )
      ElMessage.success('关系创建成功')
      emit('edge-saved', {
        id: `${result.source_node_id}-${result.target_node_id}`,
        source: result.source_node_id,
        target: result.target_node_id,
        sourceName: edgeForm.sourceName,
        targetName: edgeForm.targetName,
        relationship_name: result.relationship_name,
        description: result.description,
      })
    } else if (props.selectedEdge) {
      const result = await updateEdge(
        props.graphName, props.selectedEdge.source, props.selectedEdge.target,
        { relationship_name: edgeForm.relationship_name, description: edgeForm.description },
      )
      ElMessage.success('关系更新成功')
      emit('edge-saved', {
        id: `${result.source_node_id}-${result.target_node_id}`,
        source: result.source_node_id,
        target: result.target_node_id,
        sourceName: edgeForm.sourceName,
        targetName: edgeForm.targetName,
        relationship_name: result.relationship_name,
        description: result.description,
      })
    }
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '操作失败'
    if (e?.response?.status === 409) {
      ElMessage.warning('该关系已存在')
    } else {
      ElMessage.error(msg)
    }
    emit('cancel-edit')
  } finally {
    saving.value = false
  }
}

// ---- 删除边 ----

async function handleDeleteEdge() {
  if (!props.selectedEdge) return
  try {
    await ElMessageBox.confirm(
      `确认删除关系 "${props.selectedEdge.relationship_name}"（${props.selectedEdge.sourceName} → ${props.selectedEdge.targetName}）？\n此操作不可恢复。`,
      '确认删除',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  deleting.value = true
  try {
    await deleteEdge(props.graphName, props.selectedEdge.source, props.selectedEdge.target)
    ElMessage.success('关系删除成功')
    emit('edge-deleted', props.selectedEdge.source, props.selectedEdge.target)
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '删除失败'
    ElMessage.error(msg)
  } finally {
    deleting.value = false
  }
}
</script>

<style scoped>
.kg-editor-panel {
  width: 320px;
  min-width: 320px;
  border-left: 1px solid #e5e7eb;
  background: #fff;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb;
}
.panel-header h3 {
  margin: 0;
  font-size: 15px;
  color: #1f2937;
}
.panel-body {
  padding: 16px;
  flex: 1;
}
.stat-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f3f4f6;
}
.stat-label {
  color: #6b7280;
  font-size: 13px;
}
.stat-value {
  color: #1f2937;
  font-size: 13px;
  font-weight: 600;
}
.hint-text {
  margin-top: 16px;
  font-size: 12px;
  color: #9ca3af;
  text-align: center;
}
.panel-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}
</style>
