# Cognee Agent 记忆系统源码分析报告

> 基于 Cognee v1.2.2 源码深度分析
> 分析日期: 2026-07-08

---

## 目录

1. [系统概述](#一系统概述)
2. [核心架构](#二核心架构)
3. [remember() 完整流程](#三remember-完整流程)
4. [recall() 完整流程](#四recall-完整流程)
5. [三层存储架构](#五三层存储架构)
6. [数据流转链路](#六数据流转链路)
7. [forget() 流程](#七forget-流程)
8. [visualize_graph() 流程](#八visualize_graph-流程)
9. [核心设计亮点](#九核心设计亮点)
10. [配置与部署](#十配置与部署)

---

## 一、系统概述

Cognee 是一个**Agent 记忆系统**，将非结构化文本转化为结构化的知识图谱，支持语义搜索、图遍历和会话记忆。

### 核心 API

| API | 功能 | 存储类型 |
|-----|------|----------|
| `remember()` | 存储文本到知识图谱 | 永久存储 (Graph + Vector + Relational) |
| `remember(..., session_id=...)` | 存储到会话缓存 | 短期缓存 (SQLite Session) |
| `recall()` | 语义搜索与问答 | 向量搜索 + 图遍历 + LLM 生成 |
| `forget()` | 删除数据集 | 清理所有存储层 |
| `visualize_graph()` | 可视化知识图谱 | 生成交互式 HTML |

### 系统定位

```
┌─────────────────────────────────────────────────────────────────┐
│                     COGNEE AGENT 记忆系统                        │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   用户输入   │───→│   处理层    │───→│   存储层    │        │
│  │  (文本/文件) │    │ (Pipeline) │    │ (三层存储) │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│                              │                    │              │
│                              ▼                    ▼              │
│                       ┌─────────────┐    ┌─────────────┐       │
│                       │   查询层    │←───│   反馈层    │       │
│                       │ (检索/生成) │    │ (优化权重) │       │
│                       └─────────────┘    └─────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、核心架构

### 2.1 项目结构

```
cognee/
├── api/v1/                    # 对外 API
│   ├── remember/remember.py   # 存储入口
│   ├── recall/recall.py       # 查询入口
│   ├── add/add.py             # 数据添加
│   ├── cognify/cognify.py     # 知识化处理
│   └── visualize/visualize.py # 可视化
├── modules/
│   ├── pipelines/             # 管道执行
│   ├── chunking/              # 文本分块
│   ├── graph/                 # 图提取
│   ├── search/                # 搜索方法
│   └── retrieval/             # 检索器
├── infrastructure/
│   ├── databases/
│   │   ├── vector/            # 向量数据库
│   │   ├── graph/             # 图数据库
│   │   ├── relational/        # 关系数据库
│   │   └── unified/           # 统一存储引擎
│   ├── llm/                   # LLM 接口
│   └── engine/models/         # 数据模型
└── tasks/
    ├── storage/               # 存储任务
    └── graph/                 # 图处理任务
```

### 2.2 统一存储引擎 (UnifiedStoreEngine)

```python
class UnifiedStoreEngine:
    """Facade that wraps graph and vector engines with capability flags."""
    
    def __init__(self, graph_engine, vector_engine, capabilities):
        self._graph = graph_engine      # GraphDBInterface
        self._vector = vector_engine  # VectorDBInterface
        self._capabilities = capabilities  # EngineCapability flags
```

**能力标志**:
- `GRAPH`: 支持图操作
- `VECTOR`: 支持向量操作
- `HYBRID_WRITE`: 支持原子图+向量写入
- `HYBRID_SEARCH`: 支持组合图+向量查询

---

## 三、remember() 完整流程

### 3.1 调用链

```
remember(text)
    └── _remember_inner()
            ├── session_id? → SessionManager (SQLite 缓存)
            └── _run()
                    └── add()
                            └── pipeline_executor_func()
                                    └── run_pipeline()
                                            ├── setup_and_check_environment()
                                            ├── classify_documents
                                            ├── extract_chunks_from_documents
                                            ├── extract_graph_and_summarize
                                            └── add_data_points
```

### 3.2 Pipeline 详细流程

```mermaid
flowchart TD
    A[用户调用<br/>remember(text)] --> B[_remember_inner]
    B --> C{session_id?}
    C -->|有| D[SessionManager<br/>SQLite 快速缓存]
    C -->|无| E[_run 永久存储]
    
    E --> F[add 添加数据]
    F --> G[Pipeline Executor]
    
    G --> H[Step 1: classify_documents<br/>文档分类]
    H --> I[识别文档类型]
    
    I --> J[Step 2: extract_chunks<br/>文本分块]
    J --> K[TextChunker 按 token 切分]
    K --> L[DocumentChunk 对象]
    
    L --> M[Step 3: extract_graph<br/>图提取 + 摘要]
    M --> N[LLM 提取实体 & 关系]
    N --> O[KnowledgeGraph 片段]
    
    O --> P[Step 4: add_data_points<br/>数据存储]
    
    P --> Q[get_graph_from_model<br/>递归提取图结构]
    Q --> R[nodes: 实体节点<br/>edges: 关系边]
    
    R --> S[去重处理]
    
    S --> T[关系数据库 SQLite<br/>upsert_nodes / upsert_edges]
    S --> W[图数据库 Ladybug<br/>add_nodes / add_edges]
    S --> Y[向量数据库 LanceDB<br/>index_data_points]
```

### 3.3 关键步骤详解

#### Step 1: classify_documents

**文件**: `cognee/modules/pipelines/operations/classify_documents.py`

```python
async def classify_documents(data_documents: list[DataPoint]) -> list[DataPoint]:
    # 根据文件扩展名/内容识别文档类型
    # 返回 Document 子类实例 (PDFDocument, TextDocument, etc.)
```

#### Step 2: extract_chunks_from_documents

**文件**: `cognee/modules/chunking/TextChunker.py`

```python
class TextChunker:
    def chunk(self, text: str, max_chunk_size: int = 512) -> list[DocumentChunk]:
        # 使用 tokenizer 计算 token 数量
        # 按句子/段落切分，确保每块不超过 max_chunk_size tokens
        # 返回 DocumentChunk 列表
```

**DocumentChunk 模型**:
```python
class DocumentChunk(DataPoint):
    text: str                    # 文本内容
    is_part_of: Document         # 所属文档
    metadata: {"index_fields": ["text"]}  # 标记需要嵌入的字段
```

#### Step 3: extract_graph_and_summarize

**文件**: `cognee/tasks/graph/extract_graph_from_data.py`

```python
async def extract_graph_from_data(chunk: DocumentChunk) -> KnowledgeGraph:
    # 1. LLM 提取实体: "TCP/IP", "应用层", "运输层", "网际层", "链路层"
    # 2. LLM 提取关系: "TCP/IP 包含 应用层", "TCP/IP 包含 运输层", ...
    # 3. 返回 KnowledgeGraph(nodes, edges)
```

#### Step 4: add_data_points (核心存储)

**文件**: `cognee/tasks/storage/add_data_points.py`

```python
async def add_data_points(data_points, custom_edges=None, embed_triplets=False):
    # 1. 从 DataPoint 提取图结构
    results = await asyncio.gather(*[
        get_graph_from_model(data_point, added_nodes, added_edges, visited_properties)
        for data_point in data_points
    ])
    
    # 2. 去重
    nodes, edges = deduplicate_nodes_and_edges(nodes, edges)
    
    # 3. 获取统一引擎
    unified = await get_unified_engine()
    graph_engine = unified.graph
    vector_engine = unified.vector
    
    # 4. 写入关系数据库 (事务性)
    async with get_async_session() as session:
        await upsert_nodes(nodes, tenant_id, user_id, dataset_id, data_id, session)
        await upsert_edges(edges, tenant_id, user_id, dataset_id, data_id, session)
        await session.commit()
    
    # 5. 写入图数据库
    await graph_engine.add_nodes(nodes)
    await graph_engine.add_edges(edges)
    
    # 6. 写入向量数据库
    await index_data_points(nodes, vector_engine=vector_engine)
    await index_graph_edges(edges, vector_engine=vector_engine)
    
    # 7. 可选: 三元组嵌入
    if embed_triplets:
        triplets = create_triplets_from_graph(nodes, edges)
        await index_data_points(triplets, vector_engine=vector_engine)
```

---

## 四、recall() 完整流程

### 4.1 调用链

```
recall(query_text)
    └── Scope Resolution
            └── Query Router (auto_route)
                    └── Source Runners (并行)
                            ├── Session Search
                            └── Graph Search
                                    └── authorized_search
                                            └── get_search_type_retriever_instance
                                                    └── get_retriever_output
                                                            ├── get_retrieved_objects
                                                            ├── get_context_from_objects
                                                            └── get_completion_from_context
```

### 4.2 查询路由详解

**文件**: `cognee/api/v1/recall/query_router.py`

```python
class QueryRouter:
    """使用加权正则启发式分类查询"""
    
    ROUTING_RULES = [
        (r"^MATCH |^RETURN |--\(", SearchType.CYPHER, 10.0),
        (r'"exact phrase"', SearchType.CHUNKS_LEXICAL, 8.0),
        (r"summarize|summary|overview", SearchType.GRAPH_SUMMARY_COMPLETION, 5.0),
        (r"why|explain|step by step", SearchType.GRAPH_COMPLETION_COT, 4.0),
        (r"how is .* related to", SearchType.GRAPH_COMPLETION_CONTEXT_EXTENSION, 5.0),
        (r"when|before|after|timeline", SearchType.TEMPORAL, 3.0),
    ]
```

### 4.3 SearchType 枚举

**文件**: `cognee/modules/search/types/SearchType.py`

| SearchType | 用途 | Retriever |
|-----------|------|-----------|
| `SUMMARIES` | 文档摘要搜索 | SummariesRetriever |
| `CHUNKS` | 文本块向量搜索 | ChunksRetriever |
| `RAG_COMPLETION` | RAG 问答 | CompletionRetriever |
| `HYBRID_COMPLETION` | 混合搜索 | HybridRetriever |
| `GRAPH_COMPLETION` | 图遍历问答 | GraphCompletionRetriever |
| `CYPHER` | Cypher 查询 | CypherSearchRetriever |
| `CHUNKS_LEXICAL` | 精确短语匹配 | BM25ChunksRetriever |
| `CODING_RULES` | 代码规则搜索 | CodingRulesRetriever |

### 4.4 检索器详解

#### ChunksRetriever (向量搜索)

**文件**: `cognee/modules/retrieval/chunks_retriever.py`

```python
async def get_retrieved_objects(self, query: str):
    unified = await get_unified_engine()
    vector_engine = unified.vector
    
    # 1. 嵌入查询文本
    query_vector = await embedding_engine.embed_text([query])
    
    # 2. 向量搜索 DocumentChunk_text 集合
    found_chunks = await vector_engine.search(
        "DocumentChunk_text",   # collection name
        query_vector,
        limit=self.top_k,
        include_payload=True,
    )
    
    return found_chunks
```

#### GraphCompletionRetriever (图搜索)

**文件**: `cognee/modules/retrieval/graph_completion_retriever.py`

```python
async def get_retrieved_objects(self, query: str):
    # 1. 暴力三元组搜索
    triplets = await brute_force_triplet_search(query)
    
    # 2. 节点边向量搜索
    node_distances, edge_distances = await node_edge_vector_search(query)
    
    # 3. 获取记忆片段
    memory_fragment = await get_memory_fragment(
        properties_to_project=["id", "description", "name", "type", "text"],
        relevant_ids_to_filter=relevant_node_ids,
        neighborhood_depth=2,
    )
    
    # 4. 映射向量距离到图节点/边
    await memory_fragment.map_vector_distances_to_graph_nodes(node_distances)
    await memory_fragment.map_vector_distances_to_graph_edges(edge_distances)
    
    # 5. 计算 top-k 三元组重要性
    top_triplets = await memory_fragment.calculate_top_triplet_importances(k=top_k)
    
    return top_triplets
```

#### HybridRetriever (混合搜索)

**文件**: `cognee/modules/retrieval/hybrid_retriever.py`

```python
async def get_retrieved_objects(self, query: str):
    # 三通道并行检索
    chunk_objects, (entities, facts) = await asyncio.gather(
        retrieve_hybrid_chunks(query),        # 文本块通道
        self._retrieve_entities_and_facts(query)  # 实体+事实通道
    )
    
    # Truth Subspace (可选)
    # 加载数据集质心，对齐查询向量
    
    return chunk_objects + entities + facts
```

### 4.5 结果生成流程

```
get_retriever_output()
    ├── Phase 1: get_retrieved_objects()
    │       ├── 向量搜索 (embed + search)
    │       └── 图投影 (neighborhood extraction)
    │
    ├── Phase 2: get_context_from_objects()
    │       └── 提取 payload["text"]
    │       └── 解析边为文本描述
    │
    └── Phase 3: get_completion_from_context()
            └── LLM 生成回答 (基于检索到的上下文)
```

---

## 五、三层存储架构

### 5.1 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                    UnifiedStoreEngine                            │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Graph DB   │  │  Vector DB  │  │    Relational DB        │  │
│  │  (图数据库)  │  │ (向量数据库) │  │    (关系数据库)         │  │
│  │             │  │             │  │                         │  │
│  │  Ladybug    │  │  LanceDB    │  │  SQLite (默认)          │  │
│  │  Neo4j      │  │  PGVector   │  │  PostgreSQL             │  │
│  │  PostgreSQL  │  │  Neptune    │  │                         │  │
│  │  Neptune    │  │             │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 关系数据库 (SQLite/PostgreSQL)

**核心表结构**:

```sql
-- 节点表
CREATE TABLE nodes (
    id UUID PRIMARY KEY,
    slug UUID NOT NULL,
    user_id UUID NOT NULL,
    data_id UUID NOT NULL,
    dataset_id UUID NOT NULL,
    pipeline_run_id UUID,
    label TEXT,
    type TEXT NOT NULL,
    indexed_fields JSON NOT NULL,
    attributes JSON
);

-- 边表
CREATE TABLE edges (
    id UUID PRIMARY KEY,
    slug UUID NOT NULL,
    user_id UUID NOT NULL,
    data_id UUID NOT NULL,
    dataset_id UUID NOT NULL,
    source_node_id UUID NOT NULL,
    destination_node_id UUID NOT NULL,
    relationship_name TEXT NOT NULL,
    label TEXT,
    attributes JSON
);

-- 数据表
CREATE TABLE data (
    id UUID PRIMARY KEY,
    name TEXT,
    raw_data_location TEXT,
    mime_type TEXT,
    extension TEXT,
    ...
);

-- 数据集表
CREATE TABLE datasets (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id UUID NOT NULL,
    ...
);
```

**作用**:
- 事务层: 所有写入先记录到关系数据库
- 元数据: 文档信息、数据集、用户权限
- 回滚: 基于 pipeline_run_id 回滚
- 去重: upsert 使用 on_conflict_do_nothing

### 5.3 图数据库 (Ladybug/Kuzu)

**默认实现**: LadybugAdapter (基于 Kuzu)

**核心操作**:
```python
# 节点操作
await graph_engine.add_nodes(nodes)
await graph_engine.add_edges(edges)

# 遍历操作
await graph_engine.get_neighbors(node_id)
await graph_engine.get_neighborhood(node_id, depth=2)

# Cypher 查询
await graph_engine.query("MATCH (n)-[r]->(m) RETURN n, r, m")
```

**存储内容**:
- 实体节点 (Entity): id, name, type, properties
- 关系边 (Edge): source, target, relationship, properties
- 支持图遍历、邻居查询、路径查找

### 5.4 向量数据库 (LanceDB)

**默认实现**: LanceDBAdapter

**核心操作**:
```python
# 创建向量索引
await vector_engine.create_vector_index(type_name, field_name)

# 索引数据点
await vector_engine.index_data_points(type_name, field_name, batch)

# 语义搜索
results = await vector_engine.search(
    collection_name="DocumentChunk_text",
    query_vector=query_embedding,
    limit=10,
)
```

**存储集合**:

| Collection | 内容 | 用途 |
|-----------|------|------|
| `DocumentChunk_text` | 文本块嵌入 | 相似文本搜索 |
| `Entity_name` | 实体名称嵌入 | 实体识别 |
| `EntityType_name` | 实体类型嵌入 | 类型分类 |
| `EdgeType_relationship_name` | 关系类型嵌入 | 关系搜索 |
| `TextSummary_text` | 摘要文本嵌入 | 摘要搜索 |

### 5.5 三种存储的关系

```
                    DataPoint (通用模型)
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │ Relational  │ │   Graph     │ │   Vector    │
    │    DB       │ │     DB      │ │     DB      │
    │             │ │             │ │             │
    │ 元数据事务层 │ │  结构遍历层  │ │  语义搜索层  │
    │             │ │             │ │             │
    │ • 数据一致性 │ │ • 邻居查询   │ │ • 相似性搜索 │
    │ • 回滚支持   │ │ • 路径查找   │ │ • 向量距离   │
    │ • 去重机制   │ │ • 子图提取   │ │ • 批量索引   │
    └─────────────┘ └─────────────┘ └─────────────┘
```

---

## 六、数据流转链路

### 6.1 完整数据生命周期

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         数据生命周期 (Data Lifecycle)                        │
└─────────────────────────────────────────────────────────────────────────────┘

  用户输入文本
       │
       ▼
  ┌────────────────────────────────────────┐
  │  1. INGESTION 数据摄取                  │
  │     classify() → identify()            │
  │     保存到 Relational DB (metadata)      │
  └────────────────────────────────────────┘
       │
       ▼
  ┌────────────────────────────────────────┐
  │  2. CHUNKING 文本分块                   │
  │     TextChunker 按 token 切分            │
  │     生成 DocumentChunk[]               │
  │     metadata: {"index_fields": ["text"]} │
  └────────────────────────────────────────┘
       │
       ▼
  ┌────────────────────────────────────────┐
  │  3. GRAPH EXTRACTION 图提取             │
  │     LLM 提取: entities + relationships │
  │     integrate_chunk_graphs()           │
  │     DocumentChunk.contains = [图数据]  │
  └────────────────────────────────────────┘
       │
       ▼
  ┌────────────────────────────────────────┐
  │  4. STORAGE 存储 (三层同时写入)           │
  │                                        │
  │  ┌─────────────┐ ┌─────────────┐      │
  │  │ Relational DB │ │   Graph DB  │      │
  │  │  (事务层)     │ │  (结构层)    │      │
  │  │ upsert_nodes  │ │ add_nodes   │      │
  │  │ upsert_edges  │ │ add_edges   │      │
  │  └─────────────┘ └─────────────┘      │
  │         │                │             │
  │         ▼                ▼             │
  │  ┌─────────────────────────────────┐   │
  │  │         Vector DB (语义层)       │   │
  │  │  index_data_points()            │   │
  │  │  index_graph_edges()            │   │
  │  │                                 │   │
  │  │  DocumentChunk → Embedding     │   │
  │  │  Entity        → Embedding     │   │
  │  │  EdgeType      → Embedding     │   │
  │  └─────────────────────────────────┘   │
  └────────────────────────────────────────┘
       │
       ▼
  ┌────────────────────────────────────────┐
  │  5. QUERY 查询                          │
  │                                        │
  │  查询文本 → Embedding → Vector Search   │
  │       │                                │
  │       ▼                                │
  │  Graph Projection (节点 + 边)          │
  │       │                                │
  │       ▼                                │
  │  Context → LLM → 生成回答             │
  └────────────────────────────────────────┘
       │
       ▼
  ┌────────────────────────────────────────┐
  │  6. FEEDBACK 反馈优化                   │
  │     improve() 自动优化                  │
  │     feedback_weight 调整重要性          │
  │     session 缓存学习                    │
  └────────────────────────────────────────┘
```

### 6.2 核心数据模型: DataPoint

**文件**: `cognee/infrastructure/engine/models/DataPoint.py`

```python
class DataPoint(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    created_at: int
    updated_at: int
    metadata: MetaData = {"index_fields": []}  # 指定哪些字段需要嵌入
    type: str
    belongs_to_set: list[DataPoint] | list[str] | None = None
    source_pipeline: str | None = None
    source_task: str | None = None
    
    # 关键设计:
    # - metadata["index_fields"]: 声明需要生成嵌入的字段
    # - identity_fields: 用于去重的字段，生成确定性 ID
    # - belongs_to_set: 数据集归属标记
```

---

## 七、forget() 流程

```
forget(dataset)
    └── 删除 Relational DB 中的 dataset 记录
            └── 删除 Graph DB 中的相关节点和边
                    └── 删除 Vector DB 中的相关嵌入向量
                            └── 删除 Session Cache 中的会话缓存
                                    └── 清理文件系统中的本地存储文件
```

**文件**: `cognee/api/v1/forget/forget.py`

---

## 八、visualize_graph() 流程

```
visualize_graph(output_path)
    └── 从 Graph DB 读取所有 nodes 和 edges
            └── get_graph_data() 获取图数据
                    └── 生成 D3.js 交互式 HTML
                            └── 节点颜色编码 (实体类型)
                            └── 边标签和权重
                            └── 悬停显示详细属性
                                    └── 保存到 .html 文件
```

**文件**: `cognee/api/v1/visualize/visualize.py`

---

## 九、核心设计亮点

### 9.1 设计模式

| 设计 | 说明 | 实现 |
|------|------|------|
| **Facade 模式** | UnifiedStoreEngine 统一协调 | `infrastructure/databases/unified/` |
| **Adapter 模式** | 多种后端可插拔 | Graph DB: Ladybug/Neo4j/PostgreSQL/Neptune |
| **Pipeline 模式** | 流水线处理 | `modules/pipelines/operations/pipeline.py` |
| **Strategy 模式** | 多种检索策略 | SearchType 枚举 + Retriever 工厂 |
| **Observer 模式** | 反馈权重调整 | `improve()` 自动优化 |

### 9.2 关键特性

| 特性 | 说明 |
|------|------|
| **三层一致性** | 关系DB作为事务层，图DB存储结构，向量DB存储语义 |
| **可插拔架构** | 图数据库和向量数据库都支持多种后端 |
| **回滚机制** | 基于 pipeline_run_id 的回滚，确保失败可清理 |
| **并发控制** | Semaphore 控制并发写入，批量处理提高性能 |
| **多租户隔离** | dataset_id + user_id 隔离数据 |
| **混合搜索** | 向量相似性 + 图遍历 + LLM 生成 |
| **自我优化** | Feedback 权重调整，Session 缓存学习 |
| **离线优先** | 支持本地部署，无需云端依赖 |

### 9.3 与 LangChain/LlamaIndex 对比

| 特性 | Cognee | LangChain | LlamaIndex |
|------|--------|-----------|------------|
| 知识图谱 | ✅ 原生支持 | ❌ 需集成 | ⚠️ 有限支持 |
| 向量搜索 | ✅ 内置 | ✅ 内置 | ✅ 内置 |
| 图遍历 | ✅ 原生 | ❌ 需集成 | ⚠️ 有限 |
| 会话记忆 | ✅ 双层 | ⚠️ 需配置 | ⚠️ 需配置 |
| 自我优化 | ✅ 自动 | ❌ 手动 | ❌ 手动 |
| 可视化 | ✅ 内置 | ❌ 需第三方 | ❌ 需第三方 |

---

## 十、配置与部署

### 10.1 环境变量配置

```bash
# LLM 配置
LLM_PROVIDER="custom"
LLM_MODEL="deepseek/deepseek-v4-flash"
LLM_ENDPOINT="https://api.deepseek.com/"
LLM_API_KEY="sk-..."

# Embedding 配置
EMBEDDING_PROVIDER="openai_compatible"
EMBEDDING_MODEL="bge-m3"
EMBEDDING_ENDPOINT="http://192.168.30.76:8211/v1/embeddings"
EMBEDDING_API_KEY="sk-..."
EMBEDDING_DIMENSIONS=1024

# 数据库配置 (可选)
# 默认使用 SQLite
# COGNEE_DATABASE_URL="sqlite+aiosqlite:///path/to/db"

# 系统目录
# COGNEE_SYSTEM_ROOT="/path/to/cognee_system"
# COGNEE_DATA_ROOT="/path/to/cognee_data"
```

### 10.2 关键文件索引

| 组件 | 文件路径 |
|------|----------|
| **Vector DB Interface** | `infrastructure/databases/vector/vector_db_interface.py` |
| **Vector DB Factory** | `infrastructure/databases/vector/create_vector_engine.py` |
| **Graph DB Interface** | `infrastructure/databases/graph/graph_db_interface.py` |
| **Graph DB Factory** | `infrastructure/databases/graph/get_graph_engine.py` |
| **Relational DB** | `infrastructure/databases/relational/sqlalchemy/SqlAlchemyAdapter.py` |
| **Unified Engine** | `infrastructure/databases/unified/get_unified_engine.py` |
| **DataPoint Model** | `infrastructure/engine/models/DataPoint.py` |
| **Graph Extraction** | `modules/graph/utils/get_graph_from_model.py` |
| **Add Data Points** | `tasks/storage/add_data_points.py` |
| **Index Data Points** | `tasks/storage/index_data_points.py` |
| **Upsert Nodes** | `modules/graph/methods/upsert_nodes.py` |
| **Upsert Edges** | `modules/graph/methods/upsert_edges.py` |
| **Cognify Pipeline** | `api/v1/cognify/cognify.py` |
| **Text Chunker** | `modules/chunking/TextChunker.py` |
| **DocumentChunk Model** | `modules/chunking/models/DocumentChunk.py` |
| **Graph Extraction Task** | `tasks/graph/extract_graph_from_data.py` |
| **Recall** | `api/v1/recall/recall.py` |
| **Query Router** | `api/v1/recall/query_router.py` |
| **Remember** | `api/v1/remember/remember.py` |
| **Forget** | `api/v1/forget/forget.py` |
| **Visualize** | `api/v1/visualize/visualize.py` |

---

## 附录: main.py 执行追踪

```python
# 你的 main.py 执行流程:

remember("TCP/IP是一个四层的体系结构...")
    │
    ├──→ 文本分块 → "TCP/IP是一个四层的体系结构..."
    ├──→ LLM 提取实体: [TCP/IP, 应用层, 运输层, 网际层, 链路层]
    ├──→ LLM 提取关系: [TCP/IP 包含 应用层, TCP/IP 包含 运输层, ...]
    ├──→ 存储到 SQLite (nodes/edges 表)
    ├──→ 存储到 Ladybug 图数据库 (图结构)
    ├──→ 存储到 LanceDB 向量数据库 (5个实体的嵌入向量)
    └──→ 完成

remember("用户不太理解TCP/IP的具体架构.", session_id="chat_test")
    │
    ├──→ 存储到 Session Cache (SQLite 快速缓存)
    └──→ 同时触发 cognify 同步到图数据库

recall("What is TCP/IP?")
    │
    ├──→ Query Router: 分类为 GRAPH_COMPLETION
    ├──→ 嵌入查询: "What is TCP/IP?" → 向量
    ├──→ Vector Search: 搜索 Entity_name, DocumentChunk_text
    ├──→ Graph Projection: 找到 TCP/IP 节点及其邻居
    ├──→ 构建上下文: 包含 TCP/IP 的实体和关系
    ├──→ LLM 生成回答
    └──→ 返回结果

recall("What is User Short of?", session_id="chat_test")
    │
    ├──→ 先查 Session Cache: 找到 "用户不太理解TCP/IP的具体架构"
    ├──→ 返回 session 结果
    └──→ 如果 session 没有，再查 graph

visualize_graph("graph_visualization.html")
    │
    ├──→ 从 Ladybug 读取所有 nodes 和 edges
    ├──→ 生成 D3.js 交互式 HTML
    └──→ 保存到文件
```

---

> **报告生成完毕**
> 
> 本报告基于 Cognee v1.2.2 源码分析，涵盖了 remember、recall、forget、visualize 等核心 API 的完整内部流程，以及三层存储架构的详细设计。
