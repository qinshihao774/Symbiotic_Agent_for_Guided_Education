import type { GraphNode, GraphData } from '@/api/knowledge'

/** 层级解析结果 */
export interface HierarchyResult {
  /** 顶层章节点（不被任何 Chapter 包含的 Chapter） */
  topLevelChapters: GraphNode[]
  /** chapterId → 子节 Chapter 节点列表 */
  chapterChildren: Map<string, GraphNode[]>
  /** chapterId → 归属的知识点节点列表 */
  chapterKnowledgePoints: Map<string, GraphNode[]>
  /** id → node 快速查找 */
  nodeMap: Map<string, GraphNode>
}

/**
 * 从图谱数据中解析章节层级结构。
 *
 * 规则：
 * - Chapter→Chapter 的"包含"边 = 章节父子关系
 * - Chapter→非Chapter 的"包含"边 = 知识点归属
 * - 不出现在任何 Chapter→Chapter 边 target 位置的 Chapter = 顶层章
 */
export function parseHierarchy(data: GraphData): HierarchyResult {
  const { nodes, edges } = data

  // 1. node 快速查找表
  const nodeMap = new Map<string, GraphNode>()
  for (const n of nodes) {
    nodeMap.set(n.id, n)
  }

  // 2. 分析"包含"边
  const chapterContainsTargets = new Set<string>()
  const chapterChildren = new Map<string, GraphNode[]>()
  const chapterKnowledgePoints = new Map<string, GraphNode[]>()

  for (const e of edges) {
    if (e.relationship_name !== '包含') continue

    const sourceNode = nodeMap.get(e.source)
    const targetNode = nodeMap.get(e.target)
    if (!sourceNode || !targetNode) continue

    const sourceIsChapter = sourceNode.type === 'Chapter'
    const targetIsChapter = targetNode.type === 'Chapter'

    if (sourceIsChapter && targetIsChapter) {
      // 章节父子关系
      chapterContainsTargets.add(e.target)
      const children = chapterChildren.get(e.source) || []
      children.push(targetNode)
      chapterChildren.set(e.source, children)
    } else if (sourceIsChapter && !targetIsChapter) {
      // 知识点归属
      const kps = chapterKnowledgePoints.get(e.source) || []
      kps.push(targetNode)
      chapterKnowledgePoints.set(e.source, kps)
    }
  }

  // 3. 找出顶层章（Chapter 节点中不出现在 chapterContainsTargets 中的）
  const topLevelChapters = nodes
    .filter(n => n.type === 'Chapter' && !chapterContainsTargets.has(n.id))
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))

  return { topLevelChapters, chapterChildren, chapterKnowledgePoints, nodeMap }
}

/**
 * 根据钻取路径过滤出当前层级应展示的 GraphData。
 */
export function getVisibleData(
  data: GraphData,
  drillPath: GraphNode[],
  hierarchy: HierarchyResult
): GraphData {
  const { topLevelChapters, chapterChildren, chapterKnowledgePoints } = hierarchy

  if (drillPath.length === 0) {
    // 顶层：只展示顶层章
    const visibleNodeIds = new Set(topLevelChapters.map(n => n.id))
    const visibleEdges = data.edges.filter(
      e => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
    )
    return {
      nodes: topLevelChapters,
      edges: visibleEdges,
      stats: {
        total_nodes: topLevelChapters.length,
        total_edges: visibleEdges.length,
        node_types: { Chapter: topLevelChapters.length },
      },
    }
  }

  const currentChapter = drillPath[drillPath.length - 1]
  const subSections = chapterChildren.get(currentChapter.id) || []
  const knowledgePoints = chapterKnowledgePoints.get(currentChapter.id) || []

  if (drillPath.length === 1) {
    // 子节层：展示该章的子节
    if (subSections.length > 0) {
      const visibleNodes = [currentChapter, ...subSections]
      const visibleNodeIds = new Set(visibleNodes.map(n => n.id))
      const visibleEdges = data.edges.filter(
        e => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
      )
      return {
        nodes: visibleNodes,
        edges: visibleEdges,
        stats: {
          total_nodes: visibleNodes.length,
          total_edges: visibleEdges.length,
          node_types: { Chapter: visibleNodes.length },
        },
      }
    } else {
      // 无子节，自动跳到知识点层
      const visibleNodes = [currentChapter, ...knowledgePoints]
      const visibleNodeIds = new Set(visibleNodes.map(n => n.id))
      const visibleEdges = data.edges.filter(
        e => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
      )
      const typeCounter: Record<string, number> = {}
      for (const n of visibleNodes) {
        typeCounter[n.type] = (typeCounter[n.type] || 0) + 1
      }
      return {
        nodes: visibleNodes,
        edges: visibleEdges,
        stats: {
          total_nodes: visibleNodes.length,
          total_edges: visibleEdges.length,
          node_types: typeCounter,
        },
      }
    }
  }

  // drillPath.length === 2: 知识点层
  const visibleNodes = [currentChapter, ...knowledgePoints]
  const visibleNodeIds = new Set(visibleNodes.map(n => n.id))
  const visibleEdges = data.edges.filter(
    e => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)
  )
  const typeCounter: Record<string, number> = {}
  for (const n of visibleNodes) {
    typeCounter[n.type] = (typeCounter[n.type] || 0) + 1
  }
  return {
    nodes: visibleNodes,
    edges: visibleEdges,
    stats: {
      total_nodes: visibleNodes.length,
      total_edges: visibleEdges.length,
      node_types: typeCounter,
    },
  }
}

/**
 * 判断节点是否应该触发钻取（Chapter 节点→钻取；非 Chapter→null 表示显示详情面板）
 */
export function tryDrillInto(
  node: GraphNode,
  drillPath: GraphNode[],
  hierarchy: HierarchyResult
): GraphNode[] | null {
  if (node.type === 'Chapter') {
    // 防止重复钻取同一个节点
    if (drillPath.length > 0 && drillPath[drillPath.length - 1].id === node.id) {
      return null
    }
    return [...drillPath, node]
  }
  return null // 非 Chapter → 外部处理为详情面板
}

