import request from '@/utils/request'

export interface GraphNode {
  id: string
  name: string
  type: string
  description: string
  degree: number
  mastery?: number
  progress?: number
}

export interface GraphEdge {
  source: string
  target: string
  relationship_name: string
  description?: string
}

export interface GraphStats {
  total_nodes: number
  total_edges: number
  node_types: Record<string, number>
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  stats: GraphStats
}

export interface SearchResult {
  results: Array<{
    id: string
    name: string
    type: string
    description: string
  }>
}

export interface KgGraphInfo {
  id: number
  graph_name: string
  original_filename: string
  course_id: number | null
  node_count: number
  edge_count: number
  chunk_count: number
  status: 'pending' | 'completed' | 'failed'
  created_at: string
}

export interface DeleteGraphStats {
  graph_id: number
  graph_name: string
  original_filename: string
  node_count: number
  edge_count: number
  chunk_count: number
  status: string
}

export async function fetchGraphStats(graphId: number): Promise<DeleteGraphStats> {
  return request.get(`/knowledge/graphs/${graphId}/stats`)
}

export async function fetchGraphList(): Promise<KgGraphInfo[]> {
  return request.get('/knowledge/graphs')
}

export async function fetchGraphData(graphName?: string): Promise<GraphData> {
  const params: Record<string, string> = {}
  if (graphName) params.graph_name = graphName
  return request.get('/kg/graph/data', { params })
}

export async function searchNodes(query: string, graphName?: string): Promise<SearchResult> {
  const params: Record<string, string> = { q: query }
  if (graphName) params.graph_name = graphName
  return request.get('/kg/graph/search', { params })
}

export async function deleteGraph(graphId: number): Promise<{ status: string; graph_id: number }> {
  return request.delete(`/knowledge/graphs/${graphId}`)
}

// ---- 知识图谱编辑 CRUD ----

export interface CreatedNode {
  node_id: string
  name: string
  type: string
  description: string
}

export interface UpdatedNode {
  node_id: string
  name: string
  type: string
  description: string
}

export interface DeleteNodeResult {
  deleted_node_id: string
  deleted_edge_count: number
}

export interface CreatedEdge {
  source_node_id: string
  target_node_id: string
  relationship_name: string
  description: string
}

export interface UpdatedEdge {
  source_node_id: string
  target_node_id: string
  relationship_name: string
  description: string
}

export interface DeleteEdgeResult {
  source_node_id: string
  target_node_id: string
}

export async function createNode(
  graphName: string,
  name: string,
  type: string,
  description: string,
): Promise<CreatedNode> {
  return request.post('/kg/graph/node', { graph_name: graphName, name, type, description })
}

export async function updateNode(
  graphName: string,
  nodeId: string,
  fields: Partial<{ name: string; type: string; description: string }>,
): Promise<UpdatedNode> {
  return request.put(`/kg/graph/node/${encodeURIComponent(nodeId)}`, {
    graph_name: graphName,
    ...fields,
  })
}

export async function deleteNode(
  graphName: string,
  nodeId: string,
): Promise<DeleteNodeResult> {
  return request.delete(`/kg/graph/node/${encodeURIComponent(nodeId)}`, {
    params: { graph_name: graphName },
  })
}

export async function createEdge(
  graphName: string,
  sourceId: string,
  targetId: string,
  relationshipName: string,
  description?: string,
): Promise<CreatedEdge> {
  return request.post('/kg/graph/edge', {
    graph_name: graphName,
    source_node_id: sourceId,
    target_node_id: targetId,
    relationship_name: relationshipName,
    description: description ?? '',
  })
}

export async function updateEdge(
  graphName: string,
  sourceId: string,
  targetId: string,
  fields: Partial<{ relationship_name: string; description: string }>,
): Promise<UpdatedEdge> {
  return request.put('/kg/graph/edge', {
    graph_name: graphName,
    source_node_id: sourceId,
    target_node_id: targetId,
    ...fields,
  })
}

export async function deleteEdge(
  graphName: string,
  sourceId: string,
  targetId: string,
): Promise<DeleteEdgeResult> {
  return request.delete('/kg/graph/edge', {
    params: {
      graph_name: graphName,
      source_node_id: sourceId,
      target_node_id: targetId,
    },
  })
}
