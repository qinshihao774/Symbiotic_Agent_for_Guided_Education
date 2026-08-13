<template>
  <div ref="chartRef" class="kg-chart" />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import ForceGraph3D from '3d-force-graph'
import * as THREE from 'three'
import SpriteText from 'three-spritetext'
import type { GraphData, GraphNode } from '@/api/knowledge'
import { useKnowledgeStore } from '@/stores/knowledge'

const props = defineProps<{
  data: GraphData
  showLabels: boolean
  activeTypes: Set<string>
  expandedNodeIds: Set<string>
  anchorNodeIds?: Set<string>
  highlightedNodeIds?: Set<string>
  nodeFxMap?: Record<string, {fx?: number; fy?: number}>
}>()

const emit = defineEmits<{
  nodeClick: [node: GraphNode]
  nodeDblClick: [node: GraphNode]
}>()

const chartRef = ref<HTMLElement>()
let graph: any = null
let clickTimer: ReturnType<typeof setTimeout> | null = null
let resizeObserver: ResizeObserver | null = null

// 点击聚焦状态
const focusedNode = ref<GraphNode | null>(null)
const focusedNeighbors = ref<Set<string>>(new Set())
const hoverNode = ref<GraphNode | null>(null) // 新增悬停状态

// Cognee 风格颜色映射
const TYPE_COLORS: Record<string, string> = {
  Concept: '#7C3AED',
  Algorithm: '#F59E0B',
  DataStructure: '#10B981',
  Protocol: '#3B82F6',
  Principle: '#EC4899',
  Term: '#94A3B8',
  Technology: '#06B6D4',
  Model: '#F97316',
}

function getColor(type: string): string {
  return TYPE_COLORS[type] || '#94A3B8'
}

function updateGraphData() {
  if (!graph) return

  const filteredNodes = props.data.nodes.filter(
    n => props.activeTypes.size === 0 || props.activeTypes.has(n.type)
  )
  const activeNodeIds = new Set(filteredNodes.map(n => n.id))
  const filteredEdges = props.data.edges.filter(
    e => activeNodeIds.has(e.source) && activeNodeIds.has(e.target)
  )

  // 【关键修复】参照旧逻辑数据处理，必须进行深拷贝，彻底解除 Vue 3 Proxy 响应式追踪。
  // 否则 3d-force-graph 底层引擎修改节点坐标时会引发严重性能问题或崩溃导致黑屏。
  const gData = {
    nodes: JSON.parse(JSON.stringify(filteredNodes)),
    links: JSON.parse(JSON.stringify(filteredEdges)).map((e: any) => ({
      ...e,
      source: e.source,
      target: e.target
    }))
  }

  graph.graphData(gData)
}

function initChart() {
  if (!chartRef.value) return

  const ForceGraph3DClass = (ForceGraph3D as any).default || ForceGraph3D

  // @ts-ignore
  graph = ForceGraph3DClass()(chartRef.value)
    .backgroundColor('rgba(0,0,0,0)') // 透明背景以融合当前卡片样式
    .showNavInfo(false) // 隐藏底部提示文字
    
  if (chartRef.value.clientWidth && chartRef.value.clientHeight) {
    graph.width(chartRef.value.clientWidth).height(chartRef.value.clientHeight)
  }

  graph.nodeThreeObject((node: any) => {
      const group = new THREE.Group()

      const isFocused = focusedNode.value && (node.id === focusedNode.value.id || focusedNeighbors.value.has(node.id))
      const isDimmed = focusedNode.value && !isFocused
      const isHovered = hoverNode.value?.id === node.id

      // 决定颜色 (实体化处理，不再使用透明度)
      const baseColorStr = isFocused ? '#FF8C00' : getColor(node.type)

      // 绘制主球体（普通实体球体，掌握度通过球体中央的百分比数字展示）
      const radius = Math.max(4, Math.min(10, 3 + (node.degree || 0) * 0.5))
      const currentRadius = isHovered ? radius * 1.2 : radius
      const geometry = new THREE.SphereGeometry(currentRadius, 32, 32)

      // 掌握度（0~1），默认 0
      const mastery = Math.max(0, Math.min(1, node.mastery || 0))

      // 普通材质：暗淡状态下整体压暗
      const material = new THREE.MeshPhongMaterial({
        color: baseColorStr,
        emissive: baseColorStr,
        emissiveIntensity: isFocused || isHovered ? 0.6 : (isDimmed ? 0.05 : 0.15),
        shininess: 30,
      })
      const sphere = new THREE.Mesh(geometry, material)
      group.add(sphere)

      // 在球体中央显示掌握度百分比数字
      try {
        const SpriteTextClass = (SpriteText as any).default || SpriteText
        const pctSprite = new SpriteTextClass(`${Math.round(mastery * 100)}%`)
        pctSprite.color = '#FFFFFF'
        pctSprite.textHeight = isFocused || isHovered ? 5 : 4
        pctSprite.position.set(0, 0, 0) // 放在球体中心
        pctSprite.material.depthWrite = false // 防止文字遮挡
        pctSprite.material.depthTest = false // 始终绘制在球体之上，保证百分比数字可见
        pctSprite.material.opacity = isDimmed ? 0.5 : 1
        group.add(pctSprite)
      } catch (e) {
        console.error('SpriteText percent render error:', e)
      }

      // 绘制名称文字标签（放在球体下方）
      if (props.showLabels) {
        try {
          const SpriteTextClass = (SpriteText as any).default || SpriteText
          const sprite = new SpriteTextClass(String(node.name || ''))
          // 文字颜色统一全部换成白色
          sprite.color = '#FFFFFF'
          sprite.textHeight = isFocused || isHovered ? 6 : (isDimmed ? 3 : 3.5)
          sprite.position.y = - (currentRadius + sprite.textHeight + 2) // 将文字放在球体下方
          sprite.material.depthWrite = false // 防止文字遮挡
          sprite.material.opacity = isDimmed ? 0.5 : 1 // 暗淡时文字半透明以区分层级，但保持纯白
          group.add(sprite)
        } catch (e) {
          console.error('SpriteText render error:', e)
        }
      }

      return group
    })
    .linkColor((link: any) => {
      const srcId = typeof link.source === 'object' ? link.source.id : link.source
      const tgtId = typeof link.target === 'object' ? link.target.id : link.target
      
      // 两端都点亮（高亮）则边高亮
      if (focusedNode.value) {
        const isSrcBright = srcId === focusedNode.value.id || focusedNeighbors.value.has(srcId)
        const isTgtBright = tgtId === focusedNode.value.id || focusedNeighbors.value.has(tgtId)
        if (isSrcBright && isTgtBright) {
          return '#FFB84D' // 高亮边（稍微亮一点的橙色）
        }
        return 'rgba(255,255,255,0.06)' // 暗淡边 (提升可见度)
      }
      return 'rgba(255,255,255,0.15)' // 正常边
    })
    .linkOpacity((link: any) => {
      const srcId = typeof link.source === 'object' ? link.source.id : link.source
      const tgtId = typeof link.target === 'object' ? link.target.id : link.target
      if (focusedNode.value) {
        const isSrcBright = srcId === focusedNode.value.id || focusedNeighbors.value.has(srcId)
        const isTgtBright = tgtId === focusedNode.value.id || focusedNeighbors.value.has(tgtId)
        if (isSrcBright && isTgtBright) return 0.8
        return 0.15 // 提升透明度，防止看不见
      }
      return 0.3
    })
    .linkWidth((link: any) => {
      const srcId = typeof link.source === 'object' ? link.source.id : link.source
      const tgtId = typeof link.target === 'object' ? link.target.id : link.target
      if (focusedNode.value) {
        const isSrcBright = srcId === focusedNode.value.id || focusedNeighbors.value.has(srcId)
        const isTgtBright = tgtId === focusedNode.value.id || focusedNeighbors.value.has(tgtId)
        if (isSrcBright && isTgtBright) return 2.5
        return 0.2
      }
      return 0.8
    })
    // ==========================================
    // 新增：灵动效果 - 连线上的流动光点粒子
    // ==========================================
    .linkDirectionalParticles((link: any) => {
      const srcId = typeof link.source === 'object' ? link.source.id : link.source
      const tgtId = typeof link.target === 'object' ? link.target.id : link.target
      if (focusedNode.value) {
        const isSrcBright = srcId === focusedNode.value.id || focusedNeighbors.value.has(srcId)
        const isTgtBright = tgtId === focusedNode.value.id || focusedNeighbors.value.has(tgtId)
        if (isSrcBright && isTgtBright) return 4 // 高亮边粒子更多
        return 0 // 暗淡边不要粒子
      }
      return 2 // 正常状态下每条边2个粒子流
    })
    .linkDirectionalParticleWidth((link: any) => {
      const srcId = typeof link.source === 'object' ? link.source.id : link.source
      const tgtId = typeof link.target === 'object' ? link.target.id : link.target
      if (focusedNode.value) {
        const isSrcBright = srcId === focusedNode.value.id || focusedNeighbors.value.has(srcId)
        const isTgtBright = tgtId === focusedNode.value.id || focusedNeighbors.value.has(tgtId)
        if (isSrcBright && isTgtBright) return 3 // 高亮边粒子更大
        return 0
      }
      return 1.5 // 正常粒子大小
    })
    .linkDirectionalParticleSpeed(0.004) // 粒子流动速度
    .linkDirectionalParticleColor(() => '#FFFFFF') // 粒子颜色为纯白发光
    // ==========================================
    .onNodeHover((node: any) => {
      if (chartRef.value) {
        chartRef.value.style.cursor = node ? 'pointer' : 'default'
      }
      if (hoverNode.value?.id !== node?.id) {
        hoverNode.value = node || null
        // 触发节点重绘以显示悬停光晕
        graph.nodeThreeObject(graph.nodeThreeObject())
      }
    })
    .onNodeClick((node: any) => {
      // 模拟单击与双击
      if (clickTimer) {
        clearTimeout(clickTimer)
        clickTimer = null
        emit('nodeDblClick', node)
      } else {
        clickTimer = setTimeout(() => {
          clickTimer = null
          
          // 聚焦逻辑
          if (focusedNode.value?.id === node.id) {
            // 取消聚焦
            focusedNode.value = null
            focusedNeighbors.value.clear()
          } else {
            focusedNode.value = node
            const neighbors = new Set<string>()
            props.data.edges.forEach(e => {
              if (e.source === node.id) neighbors.add(e.target)
              if (e.target === node.id) neighbors.add(e.source)
            })
            focusedNeighbors.value = neighbors
          }
          
          // 触发重新着色
          graph.nodeThreeObject(graph.nodeThreeObject())
               .linkColor(graph.linkColor())
               .linkOpacity(graph.linkOpacity())
               .linkWidth(graph.linkWidth())

          emit('nodeClick', node)
          
          // 3D相机移动到该节点
          if (focusedNode.value) {
            const distance = 200
            const x = node.x || 0, y = node.y || 0, z = node.z || 0
            const hyp = Math.hypot(x, y, z) || 1
            const distRatio = 1 + distance / hyp
            graph.cameraPosition(
              { x: x * distRatio, y: y * distRatio, z: z * distRatio }, 
              node, 
              1500 
            )
          }
        }, 300)
      }
    })
    
  updateGraphData()
}

watch(
  () => [props.data, props.activeTypes, props.showLabels],
  () => {
    nextTick(() => {
      updateGraphData()
      if (graph) {
        graph.nodeThreeObject(graph.nodeThreeObject())
      }
    })
  },
  { deep: true }
)

onMounted(() => {
  initChart()
  
  if (chartRef.value) {
    resizeObserver = new ResizeObserver((entries) => {
      if (graph && entries.length > 0) {
        const { width, height } = entries[0].contentRect
        if (width > 0 && height > 0) {
          graph.width(width)
          graph.height(height)
        }
      }
    })
    resizeObserver.observe(chartRef.value)
  }
})

onUnmounted(() => {
  if (clickTimer) clearTimeout(clickTimer)
  if (resizeObserver) resizeObserver.disconnect()
  if (graph) {
    graph._destructor()
  }
})

// 为兼容原组件的方法
function getNodePositions(): Map<string, {x: number; y: number}> {
  return new Map() // 3D 图不再需要 2D 位置
}

defineExpose({
  zoomIn: () => { if(graph) { const p = graph.cameraPosition(); graph.cameraPosition({z: p.z - 100}, null, 500) } },
  zoomOut: () => { if(graph) { const p = graph.cameraPosition(); graph.cameraPosition({z: p.z + 100}, null, 500) } },
  resetView: () => { 
    focusedNode.value = null; 
    focusedNeighbors.value.clear(); 
    if(graph) {
      graph.nodeThreeObject(graph.nodeThreeObject())
           .linkColor(graph.linkColor())
           .linkOpacity(graph.linkOpacity())
           .linkWidth(graph.linkWidth())
      graph.zoomToFit(500);
    }
  },
  getNodePositions,
})
</script>

<style scoped>
.kg-chart {
  width: 100%;
  height: 100%;
  min-height: 500px;
  background: #000; /* 为了3D效果，保留纯黑背景以突显立体感 */
  border-radius: 8px;
  overflow: hidden;
}
</style>
