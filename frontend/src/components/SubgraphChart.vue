<template>
  <div ref="chartRef" class="subgraph-chart" />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, shallowRef } from 'vue'
import * as echarts from 'echarts'
import type { GraphNode, GraphEdge } from '@/api/knowledge'
import { TYPE_COLORS, HIT_NODE_COLOR } from '@/constants/knowledgeColors'
import type { SubgraphNode } from '@/composables/useSubgraph'

const props = withDefaults(defineProps<{
  nodes: SubgraphNode[]
  edges: GraphEdge[]
  hitNodeId: string
  roam?: boolean
  fullscreen?: boolean
}>(), {
  roam: false,
  fullscreen: false,
})

const emit = defineEmits<{
  nodeClick: [node: SubgraphNode]
}>()

const chartRef = ref<HTMLElement>()
const chartInstance = shallowRef<echarts.ECharts>()
let resizeObserver: ResizeObserver | null = null

// ECharts' force layout seeds node positions from the current canvas size.
// Never initialise it while the surrounding panel is collapsed or unmeasured,
// otherwise every node can receive (almost) the same x coordinate and remain
// trapped in a one-dimensional layout after a later resize.
const MIN_RENDER_WIDTH = 160
const MIN_RENDER_HEIGHT = 160

// Size scaling based on fullscreen mode
const sizeScale = props.fullscreen ? 1.5 : 1
const fontScale = props.fullscreen ? 1.2 : 1

// Colors for relation directions
const UPSTREAM_COLOR = '#7c3aed'   // purple
const DOWNSTREAM_COLOR = '#059669' // green
const BOTH_COLOR = '#0ea5e9'       // cyan

function getNodeColor(node: SubgraphNode): string {
  if (node.relation === 'hit') return HIT_NODE_COLOR
  if (node.relation === 'upstream') return UPSTREAM_COLOR
  if (node.relation === 'downstream') return DOWNSTREAM_COLOR
  if (node.relation === 'both') return BOTH_COLOR
  return TYPE_COLORS[node.type] || '#94A3B8'
}

function hasRenderableSize(element: HTMLElement): boolean {
  return element.clientWidth >= MIN_RENDER_WIDTH && element.clientHeight >= MIN_RENDER_HEIGHT
}

function initChart(): boolean {
  if (!chartRef.value || chartInstance.value || !hasRenderableSize(chartRef.value)) return false
  chartInstance.value = echarts.init(chartRef.value)

  chartInstance.value.on('click', (params: any) => {
    if (params.dataType === 'node' && params.data.rawNode) {
      emit('nodeClick', params.data.rawNode)
    }
  })

  updateChart()
  return true
}

function updateChart() {
  if (!chartInstance.value) return

  // Build node set including hit node
  const hitNodePlaceholder: SubgraphNode = {
    id: props.hitNodeId,
    name: props.hitNodeId,
    type: 'Concept',
    description: '',
    degree: 0,
    relation: 'hit',
    hop: 0,
  }

  const allNodes: SubgraphNode[] = [hitNodePlaceholder]
  const seen = new Set([props.hitNodeId])

  for (const n of props.nodes) {
    if (!seen.has(n.id)) {
      seen.add(n.id)
      allNodes.push(n)
    }
  }

  // Filter edges to only include nodes in our set
  const relevantEdges = props.edges.filter(
    e => seen.has(e.source) && seen.has(e.target)
  )

  const echartsNodes = allNodes.map(n => {
    const isHit = n.relation === 'hit'
    const hop = n.hop

    let symbolSize: number
    let opacity: number

    if (hop === 0) {
      symbolSize = 40 * sizeScale
      opacity = 1
    } else if (hop === 1) {
      symbolSize = 28 * sizeScale
      opacity = 1
    } else {
      symbolSize = 18 * sizeScale
      opacity = 0.6
    }

    const color = getNodeColor(n)
    const baseFontSize = hop === 0 ? 13 : hop === 1 ? 11 : 9

    return {
      id: n.id,
      name: n.name,
      symbolSize,
      itemStyle: {
        color,
        borderColor: isHit ? '#fff' : 'transparent',
        borderWidth: isHit ? 3 : 0,
        opacity,
        shadowBlur: isHit ? 12 : 0,
        shadowColor: isHit ? 'rgba(255, 140, 0, 0.6)' : 'transparent',
      },
      label: {
        show: true,
        position: 'bottom' as const,
        color: isHit ? HIT_NODE_COLOR : '#444',
        fontSize: baseFontSize * fontScale,
        fontWeight: isHit ? 'bold' : 'normal',
      },
      rawNode: n,
    }
  })

  const echartsLinks = relevantEdges.map(e => ({
    source: e.source,
    target: e.target,
    lineStyle: {
      width: props.fullscreen ? 2 : 1.5,
      color: '#94A3B8',
      opacity: 0.5,
      curveness: 0.1,
    },
    symbol: ['none', 'arrow'],
    symbolSize: props.fullscreen ? 10 : 8,
  }))

  const forceParams = props.fullscreen
    ? { initLayout: 'circular', repulsion: 600, edgeLength: 150, gravity: 0.08 }
    : { initLayout: 'circular', repulsion: 300, edgeLength: 100, gravity: 0.15 }

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item' as const,
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          const node = params.data.rawNode
          const relationLabel: Record<string, string> = {
            hit: '🎯 命中节点',
            upstream: '⬆ 前置知识',
            downstream: '⬇ 后继知识',
            both: '↔ 双向关联',
          }
          const rel = relationLabel[node.relation] || ''
          return `${node.name} (${node.type})<br/>${rel}`
        }
        return ''
      },
    },
    series: [{
      type: 'graph',
      layout: 'force',
      nodes: echartsNodes,
      links: echartsLinks,
      roam: props.roam,
      force: forceParams,
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 3 },
      },
    }],
  }

  chartInstance.value.setOption(option, true)
}

watch(() => [props.nodes, props.edges, props.hitNodeId, props.roam, props.fullscreen], () => {
  updateChart()
}, { deep: true })

onMounted(() => {
  if (chartRef.value) {
    resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry || !chartRef.value || !hasRenderableSize(chartRef.value)) return

      if (!chartInstance.value) {
        initChart()
        return
      }

      chartInstance.value.resize({
        width: entry.contentRect.width,
        height: entry.contentRect.height,
      })
    })
    resizeObserver.observe(chartRef.value)
    initChart()
  }
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  if (chartInstance.value) {
    chartInstance.value.dispose()
  }
})
</script>

<style scoped>
.subgraph-chart {
  width: 100%;
  height: 100%;
  min-height: 180px;
  background: transparent;
}
</style>
