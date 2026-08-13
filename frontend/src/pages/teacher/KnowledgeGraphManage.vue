<template>
  <div class="kg-manage-page">
    <div class="page-header">
      <h2>知识图谱管理</h2>
      <span class="subtitle">管理所有已构建的知识图谱，点击学科行查看并编辑知识图谱</span>
    </div>

    <div class="kg-manage-layout">
      <!-- 左侧：学科列表 -->
      <div class="kg-manage-left">
        <el-table
          ref="tableRef"
          :data="store.graphList"
          v-loading="store.graphListLoading"
          stripe
          style="width: 100%"
          highlight-current-row
          @current-change="handleRowChange"
          :row-class-name="rowClassName"
        >
          <el-table-column prop="original_filename" label="文件名" min-width="160" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small">
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="node_count" label="节点" width="60" />
          <el-table-column prop="edge_count" label="边" width="60" />
          <el-table-column label="操作" width="70" fixed="right">
            <template #default="{ row }">
              <el-button
                type="danger"
                plain
                size="small"
                :disabled="row.status === 'pending'"
                @click.stop="handleDelete(row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 右侧：图谱编辑区 -->
      <div class="kg-manage-right" v-if="currentGraph">
        <KgEditorToolbar
          v-model:toolMode="toolMode"
          v-model:visibleTypes="visibleTypes"
          :graphStats="scopedGraphData?.stats ?? null"
          @zoom-in="canvasRef?.zoomIn()"
          @zoom-out="canvasRef?.zoomOut()"
          @fit-view="canvasRef?.fitView()"
        />
        <div v-if="graphData" class="scope-toolbar">
          <div class="scope-breadcrumb">
            <el-button size="small" text type="primary" @click="resetEditorScope">全部章节</el-button>
            <template v-for="(node, index) in editorPath" :key="node.id">
              <span class="scope-separator">/</span>
              <el-button size="small" text @click="setEditorPath(index + 1)">{{ node.name }}</el-button>
            </template>
            <template v-if="focusNodeId">
              <span class="scope-separator">/</span>
              <el-tag type="warning" closable @close="focusNodeId = null">局部：{{ focusNodeName }}</el-tag>
            </template>
          </div>
          <el-select
            v-model="searchNodeId"
            filterable
            clearable
            placeholder="搜索节点并局部编辑"
            size="small"
            class="scope-search"
            @change="focusSearchNode"
          >
            <el-option
              v-for="node in searchableNodes"
              :key="node.id"
              :label="`${node.name} · ${node.type}`"
              :value="node.id"
            />
          </el-select>
          <el-select
            v-model="selectedRelations"
            multiple
            collapse-tags
            clearable
            placeholder="关系类型（空为全部）"
            size="small"
            class="relation-filter"
          >
            <el-option v-for="relation in availableRelations" :key="relation" :label="relation" :value="relation" />
          </el-select>
          <span class="scope-count">
            当前 {{ scopedGraphData?.nodes.length || 0 }} 个节点 / {{ scopedGraphData?.edges.length || 0 }} 条边
          </span>
          <el-tooltip content="单击节点或边编辑；双击章节进入下一级；双击知识点查看局部关系">
            <el-tag type="info" plain>双击钻取</el-tag>
          </el-tooltip>
        </div>
        <div class="kg-editor-main">
          <div class="kg-editor-canvas-wrapper" v-loading="graphLoading">
            <KgEditorCanvas
              ref="canvasRef"
              :data="scopedGraphData"
              :toolMode="toolMode"
              :visibleTypes="visibleTypes"
              @node-selected="onNodeSelected"
              @node-double-click="onNodeDoubleClick"
              @edge-selected="onEdgeSelected"
              @canvas-click="onCanvasClick"
              @edge-created="onEdgeCreated"
            />
          </div>
          <KgEditorPanel
            :mode="panelMode"
            :isNew="isNewItem"
            :graphName="currentGraph.graph_name"
            :graphStats="scopedGraphData?.stats ?? null"
            :graphNodes="graphData?.nodes ?? []"
            :selectedNode="selectedNode"
            :selectedEdge="selectedEdge"
            @cancel-edit="onCancelEdit"
            @node-saved="onNodeSaved"
            @node-deleted="onNodeDeleted"
            @edge-saved="onEdgeSaved"
            @edge-deleted="onEdgeDeleted"
          />
        </div>
      </div>

      <!-- 右侧空状态 -->
      <div class="kg-manage-right kg-manage-empty" v-else>
        <el-empty description="请从左侧选择一个学科查看知识图谱" :image-size="80" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useKnowledgeStore } from '@/stores/knowledge'
import {
  fetchGraphStats,
  fetchGraphData,
  type KgGraphInfo,
  type GraphData,
  type GraphNode,
} from '@/api/knowledge'
import { getVisibleData, parseHierarchy } from '@/utils/kgHierarchy'
import { rankNeighborIds } from '@/utils/kgProjection'
import KgEditorToolbar from '@/components/kg-editor/KgEditorToolbar.vue'
import KgEditorCanvas from '@/components/kg-editor/KgEditorCanvas.vue'
import KgEditorPanel from '@/components/kg-editor/KgEditorPanel.vue'
import type { NodeEditData, EdgeEditData } from '@/components/kg-editor/KgEditorCanvas.vue'

const store = useKnowledgeStore()

// ---- 学科选择状态 ----
const currentGraph = ref<KgGraphInfo | null>(null)
const graphData = ref<GraphData | null>(null)
const graphLoading = ref(false)

// ---- 编辑交互状态 ----
const toolMode = ref<'select' | 'add-node' | 'add-edge'>('select')
const visibleTypes = ref<Set<string>>(new Set())
const panelMode = ref<'overview' | 'node' | 'edge'>('overview')
const isNewItem = ref(false)
const selectedNode = ref<NodeEditData | null>(null)
const selectedEdge = ref<EdgeEditData | null>(null)
const editorPath = ref<GraphNode[]>([])
const focusNodeId = ref<string | null>(null)
const searchNodeId = ref<string | null>(null)
const selectedRelations = ref<string[]>([])

const editorHierarchy = computed(() => graphData.value ? parseHierarchy(graphData.value) : null)
const availableRelations = computed(() => Array.from(new Set(
  (graphData.value?.edges || []).map(edge => edge.relationship_name),
)).sort((left, right) => left.localeCompare(right, 'zh-CN')))
const searchableNodes = computed(() => (graphData.value?.nodes || [])
  .slice()
  .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN')))
const focusNodeName = computed(() => graphData.value?.nodes.find(
  node => node.id === focusNodeId.value,
)?.name || '')

function withStats(data: GraphData): GraphData {
  const nodeTypes: Record<string, number> = {}
  for (const node of data.nodes) nodeTypes[node.type] = (nodeTypes[node.type] || 0) + 1
  return {
    nodes: data.nodes,
    edges: data.edges,
    stats: {
      total_nodes: data.nodes.length,
      total_edges: data.edges.length,
      node_types: nodeTypes,
    },
  }
}

const scopedGraphData = computed<GraphData | null>(() => {
  if (!graphData.value || !editorHierarchy.value) return graphData.value
  const relationAllowed = (relation: string) => (
    selectedRelations.value.length === 0 || selectedRelations.value.includes(relation)
  )

  if (focusNodeId.value) {
    const incidentEdges = graphData.value.edges.filter(edge => (
      relationAllowed(edge.relationship_name)
      && (edge.source === focusNodeId.value || edge.target === focusNodeId.value)
    ))
    const neighbors = incidentEdges.map(edge => (
      edge.source === focusNodeId.value ? edge.target : edge.source
    ))
    const rankedNeighbors = rankNeighborIds(
      focusNodeId.value,
      neighbors,
      graphData.value,
      15,
    )
    const nodeIds = new Set([focusNodeId.value, ...rankedNeighbors])
    return withStats({
      nodes: graphData.value.nodes.filter(node => nodeIds.has(node.id)),
      edges: incidentEdges.filter(edge => nodeIds.has(edge.source) && nodeIds.has(edge.target)),
      stats: graphData.value.stats,
    })
  }

  const base = getVisibleData(graphData.value, editorPath.value, editorHierarchy.value)
  return withStats({
    ...base,
    edges: base.edges.filter(edge => relationAllowed(edge.relationship_name)),
  })
})

// ---- Canvas ref ----
const canvasRef = ref<InstanceType<typeof KgEditorCanvas>>()

// ---- Table ref ----
const tableRef = ref()

// ---- beforeunload 提示 ----

function handleBeforeUnload(e: BeforeUnloadEvent) {
  if (isNewItem.value) {
    e.preventDefault()
  }
}

// ---- 初始化 ----

onMounted(() => {
  store.loadGraphList()
  window.addEventListener('keydown', handleKeydown)
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

// ---- 学科行点击 ----

async function handleRowChange(row: KgGraphInfo | null) {
  // Null row means deselection — clear graph view
  if (!row) {
    currentGraph.value = null
    graphData.value = null
    return
  }

  if (row.status !== 'completed') {
    // Only allow viewing completed graphs; reset table highlight for rejected rows
    ElMessage.info('该图谱正在构建中，暂不可查看')
    tableRef.value?.setCurrentRow(null)
    return
  }

  // 检查是否有未保存的编辑
  if (isNewItem.value) {
    try {
      await ElMessageBox.confirm(
        '当前有未保存的修改，是否放弃？',
        '提示',
        { confirmButtonText: '放弃', cancelButtonText: '留下', type: 'warning' },
      )
    } catch {
      return
    }
  }

  currentGraph.value = row
  await loadGraph(row.graph_name)
}

async function loadGraph(graphName: string) {
  graphLoading.value = true
  panelMode.value = 'overview'
  selectedNode.value = null
  selectedEdge.value = null
  isNewItem.value = false
  toolMode.value = 'select'
  editorPath.value = []
  focusNodeId.value = null
  searchNodeId.value = null

  try {
    const data = await fetchGraphData(graphName)
    if (!data.nodes || data.nodes.length === 0) {
      graphData.value = null
      ElMessage.info('该图谱暂无数据')
    } else {
      graphData.value = data
      // 由章节作用域控制密度，类型筛选默认不再隐藏知识点。
      visibleTypes.value = new Set(Object.keys(data.stats.node_types))
      selectedRelations.value = ['包含', '依赖', '前提'].filter(
        relation => data.edges.some(edge => edge.relationship_name === relation),
      )
    }
  } catch {
    graphData.value = null
    ElMessage.error('加载图谱数据失败')
  } finally {
    graphLoading.value = false
  }
}

// ---- 表格行高亮 ----

function rowClassName({ row }: { row: KgGraphInfo }) {
  return currentGraph.value?.id === row.id ? 'current-row' : ''
}

// ---- 选中事件 ----

function onNodeSelected(node: NodeEditData | null) {
  selectedNode.value = node
  selectedEdge.value = null
  isNewItem.value = false
  panelMode.value = node ? 'node' : 'overview'
}

function findChapterPath(chapterId: string): GraphNode[] {
  const hierarchy = editorHierarchy.value
  if (!hierarchy) return []
  const top = hierarchy.topLevelChapters.find(node => node.id === chapterId)
  if (top) return [top]
  for (const parent of hierarchy.topLevelChapters) {
    const child = (hierarchy.chapterChildren.get(parent.id) || []).find(
      node => node.id === chapterId,
    )
    if (child) return [parent, child]
  }
  const node = hierarchy.nodeMap.get(chapterId)
  return node ? [node] : []
}

function onNodeDoubleClick(node: GraphNode) {
  if (node.type === 'Chapter') {
    editorPath.value = findChapterPath(node.id)
    focusNodeId.value = null
  } else {
    focusNodeId.value = node.id
  }
  selectedNode.value = null
  selectedEdge.value = null
  panelMode.value = 'overview'
}

function resetEditorScope() {
  editorPath.value = []
  focusNodeId.value = null
  searchNodeId.value = null
}

function setEditorPath(length: number) {
  editorPath.value = editorPath.value.slice(0, length)
  focusNodeId.value = null
}

function focusSearchNode(nodeId?: string) {
  focusNodeId.value = nodeId || null
  if (nodeId) {
    const node = graphData.value?.nodes.find(item => item.id === nodeId)
    if (node?.type === 'Chapter') {
      editorPath.value = findChapterPath(node.id)
      focusNodeId.value = null
    }
  }
}

watch(editorPath, () => {
  focusNodeId.value = null
  selectedNode.value = null
  selectedEdge.value = null
  panelMode.value = 'overview'
}, { deep: true })

function onEdgeSelected(edge: EdgeEditData | null) {
  selectedEdge.value = edge
  selectedNode.value = null
  isNewItem.value = false
  panelMode.value = edge ? 'edge' : 'overview'
}

function onCanvasClick(coords: { x: number; y: number }) {
  // In add-edge mode, show the edge creation panel directly
  if (toolMode.value === 'add-edge') {
    selectedEdge.value = {
      id: '',
      source: '',
      target: '',
      sourceName: '',
      targetName: '',
      relationship_name: '相关',
      description: '',
    }
    selectedNode.value = null
    isNewItem.value = true
    panelMode.value = 'edge'
    toolMode.value = 'select'
    return
  }

  if (toolMode.value === 'add-node') {
    // 添加节点模式：在点击位置创建临时节点
    const tempId = `temp_${Date.now()}`
    canvasRef.value?.addTempNode(coords.x, coords.y, tempId)
    selectedNode.value = { id: tempId, name: '新节点', type: 'Concept', description: '' }
    selectedEdge.value = null
    isNewItem.value = true
    panelMode.value = 'node'
    return
  }
  // 选择模式：取消选中
  selectedNode.value = null
  selectedEdge.value = null
  isNewItem.value = false
  panelMode.value = 'overview'
}

function onEdgeCreated(_edgeData: any) {
  // ECharts 版本：不再通过拖拽连线创建边
  // 改为在面板中手动选择源/目标节点
  // 此事件保留但不再由 ECharts 触发
}

function onCancelEdit() {
  // 如果是新增的临时节点/边，从画布移除
  if (isNewItem.value && selectedNode.value?.id.startsWith('temp_')) {
    canvasRef.value?.removeItemById(selectedNode.value.id, 'node')
  }
  if (isNewItem.value && selectedEdge.value) {
    canvasRef.value?.removeItemById(selectedEdge.value.id, 'edge')
  }
  selectedNode.value = null
  selectedEdge.value = null
  isNewItem.value = false
  panelMode.value = 'overview'
  toolMode.value = 'select'
  canvasRef.value?.resetHighlight()
}

// ---- 保存/删除回调 ----

function onNodeSaved(data: NodeEditData) {
  if (isNewItem.value && selectedNode.value?.id.startsWith('temp_')) {
    // 新增节点：后端已分配真实 ID，需要重新加载图谱数据
    if (currentGraph.value) {
      loadGraph(currentGraph.value.graph_name)
    }
  } else if (selectedNode.value) {
    // 编辑节点：更新画布上的数据
    canvasRef.value?.updateNodeData(selectedNode.value.id, data)
    const sourceNode = graphData.value?.nodes.find(node => node.id === selectedNode.value?.id)
    if (sourceNode) {
      sourceNode.name = data.name
      sourceNode.type = data.type
      sourceNode.description = data.description
    }
  }
  selectedNode.value = data
  isNewItem.value = false
  toolMode.value = 'select'
}

function onNodeDeleted(nodeId: string) {
  // 移除关联边
  const relatedEdges = canvasRef.value?.getRelatedEdges(nodeId) || []
  relatedEdges.forEach(edgeId => {
    canvasRef.value?.removeItemById(edgeId, 'edge')
  })
  // 移除节点
  canvasRef.value?.removeItemById(nodeId, 'node')
  if (graphData.value) {
    graphData.value = withStats({
      nodes: graphData.value.nodes.filter(node => node.id !== nodeId),
      edges: graphData.value.edges.filter(edge => edge.source !== nodeId && edge.target !== nodeId),
      stats: graphData.value.stats,
    })
  }
  selectedNode.value = null
  panelMode.value = 'overview'
  canvasRef.value?.resetHighlight()
}

function onEdgeSaved(data: EdgeEditData) {
  if (isNewItem.value) {
    // 新增边：重新加载图谱数据
    if (currentGraph.value) {
      loadGraph(currentGraph.value.graph_name)
    }
  } else if (selectedEdge.value) {
    canvasRef.value?.updateEdgeData(selectedEdge.value.id, {
      relationship_name: data.relationship_name,
      description: data.description,
    })
    const sourceEdge = graphData.value?.edges.find(edge => (
      edge.source === selectedEdge.value?.source && edge.target === selectedEdge.value?.target
    ))
    if (sourceEdge) {
      sourceEdge.relationship_name = data.relationship_name
      sourceEdge.description = data.description
    }
  }
  selectedEdge.value = data
  isNewItem.value = false
  toolMode.value = 'select'
}

function onEdgeDeleted(source: string, target: string) {
  const edgeId = `${source}-${target}`
  canvasRef.value?.removeItemById(edgeId, 'edge')
  if (graphData.value) {
    graphData.value = withStats({
      nodes: graphData.value.nodes,
      edges: graphData.value.edges.filter(edge => edge.source !== source || edge.target !== target),
      stats: graphData.value.stats,
    })
  }
  selectedEdge.value = null
  panelMode.value = 'overview'
  canvasRef.value?.resetHighlight()
}

// ---- 删除图谱（保留原有功能） ----

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  switch (status) {
    case 'completed': return 'success'
    case 'pending': return 'warning'
    case 'failed': return 'danger'
    default: return 'info'
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'completed': return '已完成'
    case 'pending': return '构建中'
    case 'failed': return '失败'
    default: return status
  }
}

async function handleDelete(row: KgGraphInfo) {
  try {
    const stats = await fetchGraphStats(row.id)
    await ElMessageBox.confirm(
      `确认删除以下教材的全部数据？\n\n` +
      `教材：${stats.original_filename}\n` +
      `├─ 知识图谱节点：${stats.node_count} 个\n` +
      `├─ 知识图谱边：  ${stats.edge_count} 条\n` +
      `├─ 文档切片：    ${stats.chunk_count} 条\n` +
      `└─ 此操作不可恢复`,
      '确认删除',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' },
    )
    await store.deleteKgGraph(row.id, row.graph_name)
    if (currentGraph.value?.id === row.id) {
      currentGraph.value = null
      graphData.value = null
    }
    ElMessage.success(`已删除 "${row.original_filename}"`)
  } catch (e: any) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(`删除失败: ${e?.message || e}`)
  }
}

// ---- 快捷键 ----

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Delete' || e.key === 'Backspace') {
    // 避免在输入框中触发
    if ((e.target as HTMLElement)?.tagName === 'INPUT' || (e.target as HTMLElement)?.tagName === 'TEXTAREA') return
    if (selectedNode.value && !isNewItem.value) {
      handleDeleteNode()
    } else if (selectedEdge.value && !isNewItem.value) {
      handleDeleteEdge()
    }
  }
  if (e.key === 'Escape') {
    onCancelEdit()
  }
}

async function handleDeleteNode() {
  if (!selectedNode.value || !currentGraph.value) return
  try {
    await ElMessageBox.confirm(
      `确认删除节点 "${selectedNode.value.name}"？\n该节点的所有关联边也将被删除，此操作不可恢复。`,
      '确认删除',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch { return }

  try {
    const { deleteNode } = await import('@/api/knowledge')
    await deleteNode(currentGraph.value.graph_name, selectedNode.value.id)
    onNodeDeleted(selectedNode.value.id)
    ElMessage.success('节点删除成功')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

async function handleDeleteEdge() {
  if (!selectedEdge.value || !currentGraph.value) return
  try {
    await ElMessageBox.confirm(
      `确认删除关系 "${selectedEdge.value.relationship_name}"？\n此操作不可恢复。`,
      '确认删除',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch { return }

  try {
    const { deleteEdge } = await import('@/api/knowledge')
    await deleteEdge(currentGraph.value.graph_name, selectedEdge.value.source, selectedEdge.value.target)
    onEdgeDeleted(selectedEdge.value.source, selectedEdge.value.target)
    ElMessage.success('关系删除成功')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}
</script>

<style scoped>
.kg-manage-page {
  padding: 24px;
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
}
.page-header {
  margin-bottom: 16px;
  flex-shrink: 0;
}
.page-header h2 {
  margin: 0 0 4px 0;
  font-size: 20px;
  color: #1f2937;
}
.subtitle {
  font-size: 13px;
  color: #9ca3af;
}
.kg-manage-layout {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}
.kg-manage-left {
  width: 420px;
  min-width: 420px;
  flex-shrink: 0;
  overflow-y: auto;
}
.kg-manage-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}
.kg-manage-empty {
  align-items: center;
  justify-content: center;
}
.kg-editor-main {
  display: flex;
  flex: 1;
  min-height: 0;
}
.scope-toolbar {
  min-height: 42px;
  padding: 6px 12px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
}
.scope-breadcrumb {
  display: flex;
  align-items: center;
  min-width: 180px;
}
.scope-separator {
  color: #94a3b8;
}
.scope-search {
  width: 230px;
}
.relation-filter {
  width: 210px;
}
.scope-count {
  color: #64748b;
  font-size: 12px;
  white-space: nowrap;
}
.kg-editor-canvas-wrapper {
  flex: 1;
  min-height: 0;
  position: relative;
}
</style>
