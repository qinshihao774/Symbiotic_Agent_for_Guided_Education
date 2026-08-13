import { ref } from 'vue'
import { fetchGraphData, type GraphData, type GraphEdge, type GraphNode } from '@/api/knowledge'
import type { KgHitNode } from '@/composables/useChat'

export interface SubgraphNode extends GraphNode {
  relation: 'upstream' | 'downstream' | 'both' | 'hit'
  hop: number
}

export interface SubgraphData {
  hitNode: SubgraphNode
  nodes: SubgraphNode[]
  edges: GraphEdge[]
}

const MAX_HOP_NODES = 8
const MAX_HOPS = 2

function bfsBidirectional(hitNodeId: string, allNodes: GraphNode[], allEdges: GraphEdge[]) {
  const nodeById = new Map(allNodes.map(node => [node.id, node]))
  const collectedEdges: GraphEdge[] = []
  const relationMap = new Map<string, { relation: Set<'upstream' | 'downstream'>; hop: number }>()
  relationMap.set(hitNodeId, { relation: new Set(['hit'] as any), hop: 0 })

  let currentIds = new Set([hitNodeId])
  const visited = new Set([hitNodeId])
  for (let hop = 1; hop <= MAX_HOPS; hop++) {
    const nextIds = new Set<string>()
    const candidates: { edge: GraphEdge; neighborId: string; dir: 'upstream' | 'downstream' }[] = []
    for (const currentId of currentIds) {
      for (const edge of allEdges) {
        if (edge.target === currentId && !visited.has(edge.source)) candidates.push({ edge, neighborId: edge.source, dir: 'upstream' })
        if (edge.source === currentId && !visited.has(edge.target)) candidates.push({ edge, neighborId: edge.target, dir: 'downstream' })
      }
    }
    candidates.sort((a, b) => (nodeById.get(b.neighborId)?.degree ?? 0) - (nodeById.get(a.neighborId)?.degree ?? 0))
    for (const { edge, neighborId, dir } of candidates.slice(0, MAX_HOP_NODES)) {
      if (visited.has(neighborId)) continue
      visited.add(neighborId)
      nextIds.add(neighborId)
      relationMap.set(neighborId, { relation: new Set([dir]), hop })
      if (!collectedEdges.some(item => item.source === edge.source && item.target === edge.target)) collectedEdges.push(edge)
    }
    currentIds = nextIds
    if (!currentIds.size) break
  }

  const nodes: SubgraphNode[] = []
  for (const [nodeId, info] of relationMap) {
    if (nodeId === hitNodeId) continue
    const node = nodeById.get(nodeId)
    if (!node) continue
    const relation = info.relation.has('upstream') && info.relation.has('downstream') ? 'both'
      : info.relation.has('upstream') ? 'upstream' : 'downstream'
    nodes.push({ ...node, relation, hop: info.hop })
  }
  return { nodes, edges: collectedEdges }
}

export function useSubgraph() {
  // Every knowledge hit owns an independent subgraph. This avoids the previous
  // overwrite/race caused by sharing one global graph-data store.
  const subgraphs = ref<Array<SubgraphData | null>>([])
  const subgraphLoading = ref<boolean[]>([])
  const subgraphErrors = ref<Array<string | null>>([])
  const graphCache = new Map<string, GraphData>()

  async function extractSubgraphs(hitNode: KgHitNode, index: number) {
    subgraphLoading.value[index] = true
    subgraphErrors.value[index] = null
    try {
      let graphData = graphCache.get(hitNode.graphName)
      if (!graphData) {
        graphData = await fetchGraphData(hitNode.graphName)
        graphCache.set(hitNode.graphName, graphData)
      }
      const rawHitNode = graphData.nodes.find(node => node.id === hitNode.nodeId)
        ?? graphData.nodes.find(node => node.name === hitNode.nodeName)
      if (!rawHitNode) {
        subgraphErrors.value[index] = `未找到知识点“${hitNode.nodeName}”的图谱数据`
        return
      }
      const { nodes, edges } = bfsBidirectional(rawHitNode.id, graphData.nodes, graphData.edges)
      subgraphs.value[index] = { hitNode: { ...rawHitNode, relation: 'hit', hop: 0 }, nodes, edges }
    } catch (error: any) {
      subgraphErrors.value[index] = error.message || '子图提取失败'
    } finally {
      subgraphLoading.value[index] = false
    }
  }

  function clearSubgraphs() {
    subgraphs.value = []
    subgraphLoading.value = []
    subgraphErrors.value = []
    graphCache.clear()
  }

  return { subgraphs, subgraphLoading, subgraphErrors, extractSubgraphs, clearSubgraphs }
}
