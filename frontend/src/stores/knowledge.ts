import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  fetchGraphData,
  searchNodes,
  fetchGraphList,
  deleteGraph,
  type GraphData,
  type GraphNode,
  type KgGraphInfo,
} from '@/api/knowledge'

export type GraphErrorType =
  | { type: 'network'; message: string }
  | { type: 'not_found'; message: string }
  | { type: 'server'; message: string }

export const useKnowledgeStore = defineStore('knowledge', () => {
  // 图谱数据
  const graphData = ref<GraphData | null>(null)
  const loading = ref(false)
  const error = ref<GraphErrorType | null>(null)
  const selectedNode = ref<GraphNode | null>(null)
  const searchQuery = ref('')
  const activeTypes = ref<Set<string>>(new Set())

  // 图谱列表
  const graphList = ref<KgGraphInfo[]>([])
  const graphListLoading = ref(false)
  const currentGraphId = ref<number | null>(null)
  const currentGraphName = ref<string | null>(null)

  const isEmpty = computed(() => !loading.value && !error.value && !graphData.value)
  const nodeCount = computed(() => graphData.value?.stats.total_nodes ?? 0)
  const edgeCount = computed(() => graphData.value?.stats.total_edges ?? 0)

  async function loadGraphList() {
    graphListLoading.value = true
    try {
      graphList.value = await fetchGraphList()
    } catch {
      graphList.value = []
    } finally {
      graphListLoading.value = false
    }
  }

  async function loadGraphData(graphName?: string) {
    // Cache guard: skip re-fetch if the same graph is already loaded
    if (graphName === currentGraphName.value && graphData.value && !error.value) {
      return
    }
    loading.value = true
    error.value = null
    // Avoid searching a previous graph after a failed graph switch.
    graphData.value = null
    selectedNode.value = null
    try {
      const data = await fetchGraphData(graphName)
      if (!data.nodes || data.nodes.length === 0) {
        graphData.value = null
        error.value = { type: 'not_found', message: '该图谱还没有图谱数据' }
      } else {
        graphData.value = data
      }
      currentGraphName.value = graphName || null
    } catch (e: any) {
      currentGraphName.value = null
      if (e.message?.includes?.('Network') || e.code === 'ERR_NETWORK') {
        error.value = { type: 'network', message: '无法连接服务器' }
      } else {
        error.value = { type: 'server', message: e?.message || '服务端错误' }
      }
    } finally {
      loading.value = false
    }
  }

  async function searchNodesByQuery(query: string) {
    searchQuery.value = query
    if (!query.trim()) return
    try {
      const result = await searchNodes(query, currentGraphName.value || undefined)
      return result.results
    } catch {
      return []
    }
  }

  async function deleteKgGraph(graphId: number, graphName: string) {
    try {
      await deleteGraph(graphId)
      graphList.value = graphList.value.filter(g => g.id !== graphId)
      if (currentGraphId.value === graphId) {
        currentGraphId.value = null
        currentGraphName.value = null
        graphData.value = null
        // 如果有其他图谱，自动切换到第一个
        if (graphList.value.length > 0) {
          const first = graphList.value[0]
          currentGraphId.value = first.id
          currentGraphName.value = first.graph_name
          loadGraphData(first.graph_name)
        }
      }
    } catch (e: any) {
      console.error('Failed to delete graph:', e)
    }
  }

  function selectNode(node: GraphNode | null) {
    selectedNode.value = node
  }

  function toggleType(type: string) {
    const set = new Set(activeTypes.value)
    if (set.has(type)) set.delete(type)
    else set.add(type)
    activeTypes.value = set
  }

  return {
    graphData, loading, error, selectedNode, searchQuery, activeTypes,
    graphList, graphListLoading, currentGraphId, currentGraphName,
    isEmpty, nodeCount, edgeCount,
    loadGraphList, loadGraphData, searchNodesByQuery, deleteKgGraph, selectNode, toggleType,
  }
})
