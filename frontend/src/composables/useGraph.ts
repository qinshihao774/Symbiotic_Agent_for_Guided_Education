import { ref } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'

export function useGraph() {
  const store = useKnowledgeStore()
  const showLabels = ref(true)
  const searchResults = ref<Array<{ id: string; name: string; type: string }>>([])

  async function handleSearch(query: string) {
    if (!query.trim()) {
      searchResults.value = []
      return
    }
    const results = await store.searchNodesByQuery(query)
    searchResults.value = results ?? []
  }

  function focusNode(nodeId: string) {
    const node = store.graphData?.nodes.find(n => n.id === nodeId)
    if (node) store.selectNode(node)
  }

  function resetView() {
    store.selectNode(null)
  }

  return {
    showLabels,
    searchResults,
    handleSearch,
    focusNode,
    resetView,
  }
}
