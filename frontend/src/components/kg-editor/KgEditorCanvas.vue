<template>
  <div ref="chartRef" class="kg-editor-canvas" />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, shallowRef, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { GraphData as AppGraphData, GraphNode, GraphEdge } from '@/api/knowledge'
import { TYPE_COLORS } from '@/constants/knowledgeColors'

const props = defineProps<{
  data: AppGraphData | null
  toolMode: 'select' | 'add-node' | 'add-edge'
  visibleTypes: Set<string>
}>()

const emit = defineEmits<{
  'node-selected': [nodeData: NodeEditData | null]
  'node-double-click': [nodeData: GraphNode]
  'edge-selected': [edgeData: EdgeEditData | null]
  'canvas-click': [coords: { x: number; y: number }]
  'edge-created': [edge: any]
}>()

const chartRef = ref<HTMLElement>()
const chartInstance = shallowRef<echarts.ECharts>()

// ---- Exported data types for panel consumption ----

export interface NodeEditData {
  id: string
  name: string
  type: string
  description: string
}

export interface EdgeEditData {
  id: string
  source: string
  target: string
  sourceName: string
  targetName: string
  relationship_name: string
  description: string
}

// ---- Internal state ----

// Keep a local mutable copy of graph data for editing (add/remove/update)
let localNodes: GraphNode[] = []
let localEdges: GraphEdge[] = []

// ---- Data format conversion ----

function buildEChartsOption() {
  if (!props.data) return {}

  // Apply type filter
  const filteredNodes = localNodes.filter(
    n => props.visibleTypes.size === 0 || props.visibleTypes.has(n.type)
  )
  const activeNodeIds = new Set(filteredNodes.map(n => n.id))
  const filteredEdges = localEdges.filter(
    e => activeNodeIds.has(e.source) && activeNodeIds.has(e.target)
  )

  const nodes = filteredNodes.map(n => ({
    id: n.id,
    name: n.name,
    value: n.type,
    symbolSize: Math.max(20, Math.min(50, 10 + (n.degree || 0) * 3)),
    itemStyle: {
      color: TYPE_COLORS[n.type] || '#94A3B8',
      borderColor: '#fff',
      borderWidth: 1,
    },
    label: {
      show: true,
      position: 'bottom',
      color: '#333',
      fontSize: 11,
    },
    rawNode: n,
  }))

  const links = filteredEdges.map(e => ({
    source: e.source,
    target: e.target,
    value: e.relationship_name,
    rawEdge: e,
    lineStyle: {
      width: 1.5,
      color: '#94A3B8',
      opacity: 0.6,
      curveness: 0.1,
    },
  }))

  return {
    backgroundColor: '#fafafa',
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          const n = params.data
          return `<b>${n.name}</b><br/><span style="color:#999">${n.value}</span>`
        }
        if (params.dataType === 'edge') {
          return params.data.value || ''
        }
        return ''
      },
    },
    series: [{
      type: 'graph',
      layout: 'force',
      nodes,
      links,
      roam: true,
      draggable: true,
      label: {
        show: true,
        position: 'bottom',
        fontSize: 11,
        color: '#333',
      },
      force: {
        repulsion: 350,
        edgeLength: [80, 200],
        gravity: 0.1,
        friction: 0.6,
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 3, opacity: 0.8 },
      },
      blur: {
        opacity: 0.15,
        lineStyle: { opacity: 0.1 },
      },
      lineStyle: { color: '#94A3B8' },
      edgeLabel: {
        show: false,
        fontSize: 9,
        color: '#6b7280',
        formatter: (params: any) => params.data?.value || '',
      },
    }],
  }
}

// ---- Initialization ----

function initChart() {
  if (!chartRef.value) return
  chartInstance.value = echarts.init(chartRef.value)

  // Node click
  chartInstance.value.on('click', (params: any) => {
    if (params.dataType === 'node') {
      const rawNode = params.data?.rawNode as GraphNode | undefined
      if (rawNode) {
        emit('node-selected', {
          id: rawNode.id,
          name: rawNode.name,
          type: rawNode.type,
          description: rawNode.description,
        })
      }
    } else if (params.dataType === 'edge') {
      const edgeData = params.data
      if (edgeData) {
        const sourceName = localNodes.find(n => n.id === edgeData.source)?.name || edgeData.source
        const targetName = localNodes.find(n => n.id === edgeData.target)?.name || edgeData.target
        // Find the actual edge to get description
        const rawEdge = localEdges.find(
          e => e.source === edgeData.source && e.target === edgeData.target
        )
        emit('edge-selected', {
          id: `${edgeData.source}-${edgeData.target}`,
          source: edgeData.source,
          target: edgeData.target,
          sourceName,
          targetName,
          relationship_name: edgeData.value || rawEdge?.relationship_name || '',
          description: rawEdge?.description || '',
        })
      }
    }
  })

  chartInstance.value.on('dblclick', (params: any) => {
    if (params.dataType === 'node' && params.data?.rawNode) {
      emit('node-double-click', params.data.rawNode as GraphNode)
    }
  })

  // Canvas blank click
  chartInstance.value.getZr().on('click', (params: any) => {
    // Only fire if the click was on the canvas background (not on a node/edge)
    if (params.target === undefined) {
      const point = chartInstance.value?.convertFromPixel('series', [params.offsetX, params.offsetY])
      emit('canvas-click', point ? { x: point[0], y: point[1] } : { x: 0, y: 0 })
      // Deselect — emit null for both
      emit('node-selected', null)
      emit('edge-selected', null)
    }
  })

  updateChart()
}

function updateChart() {
  if (!chartInstance.value) return
  const option = buildEChartsOption()
  chartInstance.value.setOption(option, true) // true = notMerge, full replace
}

// ---- Watchers ----

watch(() => props.data, (newData) => {
  if (newData) {
    // Deep clone so we can mutate locally for editing
    localNodes = newData.nodes.map(n => ({ ...n }))
    localEdges = newData.edges.map(e => ({ ...e }))
    nextTick(() => updateChart())
  }
}, { deep: false })

watch(() => props.visibleTypes, () => {
  updateChart()
}, { deep: true })

// ---- Lifecycle ----

onMounted(() => {
  initChart()
  if (props.data) {
    localNodes = props.data.nodes.map(n => ({ ...n }))
    localEdges = props.data.edges.map(e => ({ ...e }))
    nextTick(() => updateChart())
  }
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (chartInstance.value) {
    chartInstance.value.dispose()
  }
  window.removeEventListener('resize', handleResize)
})

function handleResize() {
  chartInstance.value?.resize()
}

// ---- Expose methods for parent component ----

defineExpose({
  /** Zoom in */
  zoomIn: () => {
    if (!chartInstance.value) return
    const opt = chartInstance.value.getOption() as any
    if (opt?.series?.[0]) {
      const z = opt.series[0].zoom || 1
      chartInstance.value.setOption({ series: [{ zoom: z * 1.2 }] })
    }
  },
  /** Zoom out */
  zoomOut: () => {
    if (!chartInstance.value) return
    const opt = chartInstance.value.getOption() as any
    if (opt?.series?.[0]) {
      const z = opt.series[0].zoom || 1
      chartInstance.value.setOption({ series: [{ zoom: z / 1.2 }] })
    }
  },
  /** Fit the graph to the viewport */
  fitView: () => {
    if (!chartInstance.value) return
    chartInstance.value.setOption({ series: [{ zoom: 1, center: null }] })
  },

  /** Add a temporary node — ECharts will place it via force layout */
  addTempNode: (_x: number, _y: number, tempId: string): void => {
    const newNode: GraphNode = {
      id: tempId,
      name: '新节点',
      type: 'Concept',
      description: '',
      degree: 0,
    }
    localNodes.push(newNode)
    updateChart()
  },

  /** Remove a node or edge by ID */
  removeItemById: (id: string, type: 'node' | 'edge'): void => {
    if (type === 'node') {
      localNodes = localNodes.filter(n => n.id !== id)
      // Also remove connected edges
      localEdges = localEdges.filter(e => e.source !== id && e.target !== id)
    } else {
      // id is "source-target" format
      localEdges = localEdges.filter(e => `${e.source}-${e.target}` !== id)
    }
    updateChart()
  },

  /** Update node data locally */
  updateNodeData: (nodeId: string, fields: Partial<NodeEditData>): void => {
    const node = localNodes.find(n => n.id === nodeId)
    if (!node) return
    if (fields.name !== undefined) node.name = fields.name
    if (fields.type !== undefined) node.type = fields.type
    if (fields.description !== undefined) node.description = fields.description
    updateChart()
  },

  /** Update edge data locally */
  updateEdgeData: (edgeId: string, fields: {
    relationship_name?: string
    description?: string
  }): void => {
    const edge = localEdges.find(e => `${e.source}-${e.target}` === edgeId)
    if (!edge) return
    if (fields.relationship_name !== undefined) edge.relationship_name = fields.relationship_name
    if (fields.description !== undefined) edge.description = fields.description
    updateChart()
  },

  /** Get all edge IDs connected to a given node */
  getRelatedEdges: (nodeId: string): string[] => {
    return localEdges
      .filter(e => e.source === nodeId || e.target === nodeId)
      .map(e => `${e.source}-${e.target}`)
  },

  /** Get the raw ECharts instance */
  getGraph: () => chartInstance.value,

  /** Reset highlight — ECharts handles this via emphasis.blur */
  resetHighlight: () => {
    // ECharts emphasis/blur is automatic; nothing to reset manually
  },
})
</script>

<style scoped>
.kg-editor-canvas {
  width: 100%;
  height: 100%;
  min-height: 400px;
  background: #fafafa;
}
</style>
