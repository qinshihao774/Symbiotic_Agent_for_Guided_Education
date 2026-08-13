# 智教慧学：双检索架构（RAG & MCP+数据库）设计与实现方案

## 一、 架构可行性分析

**结论：完全可行，且当前系统已具备极好的底层基础。**

通过对项目现有代码（尤其是 `ai/app/engines/llm/client.py`、`mcp_client.py` 和 `orchestrator.py`）的分析，系统已经具备了标准的 Function Calling 解析能力和基础的 MCP 客户端机制。

### 1. 本地模型与远端模型的兼容性

- **远端大模型（如 DeepSeek、通义千问 API）**：天然支持标准的 OpenAI 格式 `tools` 参数，当前的 `client.py` 中已经完美实现了 `tool_calls` 的请求与流式解析。
- **本地大模型（如 Qwen3.5-9B）**：只要通过 vLLM 或 Ollama 提供兼容 OpenAI 的 API 接口，且选择具备 Function Calling 微调能力的模型（如 Qwen-Agent 或 Llama-3-Tool-Use），即可无缝复用当前架构，无需修改任何代码。

***

## 二、 核心架构设计

系统将并存两条数据检索链路，由 `AgentOrchestrator`（智能体编排器）根据用户意图自动路由：

### 1. 链路 A：GraphRAG - 模糊场景，应对“非结构化”数据查询

- **定位**：处理**模糊的、语义化的、概念性**的知识查询。
- **流程**：用户提问 -> 文本向量化 -> ChromaDB 语义检索 / 知识图谱子图提取 -> LLM 总结。
- **适用场景**：“什么是银行家算法？”、“解释一下 B+ 树的原理”、“学习计划”、“知识图谱总览”。

### 2. 链路 B：MCP + 数据库 - 精确业务，应对“结构化”数据的精准查询

- **定位**：处理**精确的、结构化的、事实性**的业务数据查询。
- **流程**：用户提问 -> LLM 决定调用数据库工具 -> MCP Server 执行预定义的 SQL/业务函数 -> PostgreSQL/AGE 返回精确数据 -> LLM 整合回答。
- **适用场景**：“帮我查一下我上周的错题记录”、“做教师学生的数据统计”，“数据分析-练习”。

### 总之：

RAG 的核心逻辑是“语义相似度匹配”。它不理解复杂的数学逻辑，但极其擅长理解人类语言的模糊表达。
具体特点：不擅长精准聚合、模糊与包容性高。

MCP + 数据库（实际上就是 Text-to-SQL 的标准化升级版）的核心逻辑是“精准执行”。它极度依赖大模型写代码的能力，而非单纯的文字理解。
具体特点：绝对的精准（零数据幻觉）、精确查询，无需搬运数据。

***

## 三、 MCP + 数据库 的具体实现步骤

要实现 MCP+数据库，我们需要将数据库能力“包装”成 MCP Server 提供的标准工具（Tools）。具体分为三步：

### 第一步：搭建 Database MCP Server (服务提供方)

在 `ai/` 项目下新增一个轻量级的 MCP Server，专门负责连接 PostgreSQL 数据库并暴露查询工具。

*建议路径*：`ai/app/mcp_server/db_server.py`

**核心逻辑**：

1. 引入 `mcp` 官方 Python SDK。
2. 建立与 PostgreSQL 的只读异步数据库连接。
3. 定义具体的业务查询工具（强烈建议封装业务接口，而不是让大模型直接写裸 SQL，以防安全风险）：
   - `@mcp.tool() async def get_student_wrong_questions(user_id: int, limit: int = 5): ...`
   - `@mcp.tool() async def query_class_average_score(class_id: int): ...`

### 第二步：扩展现有 MCP 客户端 (服务消费方)

目前的 `ai/app/agent/mcp_client.py` 仅支持连接单个外部搜索 MCP 服务（`MCP_SEARCH_URL`）。我们需要对其进行扩展，使其能够**同时连接多个 MCP Server**。

**改造点**：

1. 修改 `MCPClient.connect()` 方法，支持传入一个 MCP URL 列表，或者抽象出一个 `MCPConnectionManager`。
2. 启动时，同时连接外部的 Search MCP Server 和内部的 Database MCP Server。
3. 将两者暴露的工具统一注册到现有的 `ToolRegistry` 中。

### 第三步：Agent Orchestrator 提示词升级 (调度方)

更新 `ai/app/agent/orchestrator.py` 中的 `AGENT_SYSTEM_PROMPT`，指导大模型如何在这两套架构之间做选择：

```text
你拥有两类信息检索工具：
1. 【知识查询工具】（如 RAG）：用于回答计算机专业知识、概念定义。
2. 【数据库查询工具】（如 get_student_records）：用于查询具体的做题记录、成绩、系统状态。
请根据用户问题的性质，精准选择对应的工具。
```

***

## 四、 安全与最佳实践考量

1. **防 SQL 注入（核心安全）**
   - **不要**提供一个名为 `execute_sql(query: str)` 的工具让 LLM 自己拼写 SQL。由于 LLM 存在幻觉，可能会执行 `DROP TABLE` 或跨租户查询。
   - **应该**提供参数化的业务工具（如 `query_user_score(user_id: int)`），由后端代码负责校验 `user_id` 的合法性。
2. **连接生命周期**
   - Database MCP Server 同样可以通过 stdio（标准输入输出）或 streamable HTTP（SSE）与 AI 引擎通信。推荐在内部网络使用 HTTP 模式。
3. **隔离性**
   - 将业务数据查询（MCP+DB）和 知识库查询（RAG）解耦，如果以后更换数据库类型，只需修改 MCP Server 的实现，AI 引擎和前端完全无感。

***

## 五、在数据库表结构尚未敲定的“空壳”阶段

**现在正是设计和搭建 MCP (Model Context Protocol) 服务的最佳时机**。

因为一个优秀的数据库 MCP 服务，不仅能执行特定的业务查询，更重要的是它能具备\*\*“数据库自省（Introspection）”\*\*能力。这意味着即使同事未来随时修改表结构，大模型也能通过 MCP 动态感知到最新的表和字段，而不需要你频繁修改代码。

基于项目现状（FastAPI + Asyncpg + Python），梳理了 **PostgreSQL MCP 服务的实现思路与技术细节**。

### 一、 核心架构设计

在你的项目中，`ai/app/agent/mcp_client.py` 使用了 `streamable_http`（流式 HTTP）来连接外部搜索服务。为了保持架构一致性，我们即将搭建的 Database MCP Server 也应采用 **HTTP (SSE) 通信模式**，而不是简单的标准输入输出（Stdio）。

- **部署位置**：建议作为独立服务运行，或者挂载在 `backend` / `ai` 现有的 FastAPI 实例上。考虑到数据库通常归属于业务后端，建议在 `backend/` 下新建一个轻量级的 MCP Server 模块。
- **通信链路**：`AI Engine (MCP Client)` <— HTTP/SSE —> `Backend (MCP Server)` <— asyncpg —> `PostgreSQL`

### 二、 MCP 工具 (Tools) 接口设计

为了应对“表结构未定”和未来的“动态查询”需求，MCP 服务需要向大模型暴露以下三个层次的 Tool：

#### 1. 结构探索层（当前阶段最需要）

大模型在写 SQL 前，必须先知道库里有什么。

- **`list_tables`**: 查询 `information_schema.tables`，返回当前数据库中所有的表名和表注释。
- **`get_table_schema(table_name: str)`**: 查询指定表的所有字段名、数据类型、是否可空、主外键关系。

#### 2. 动态查询层（过渡阶段使用）

在业务 API 还没写好时，允许大模型直接查库。

- **`execute_readonly_sql(sql: str)`**: 允许大模型直接下发 SQL 语句进行查询。
  - *技术细节*：为了防止大模型产生幻觉执行 `DROP TABLE`，必须在连接层强制设置为**只读事务**，或者分配一个只有 `SELECT` 权限的 PostgreSQL 用户。

#### 3. 业务封装层（表结构敲定后扩展）

等同事建好表后，封装更安全的参数化查询工具，替代裸写 SQL。

- **`get_student_wrong_questions(user_id: int, subject: str)`**: 传入参数，由 MCP Server 内部拼接 SQL 并返回结果。

### 三、 技术实现细节与伪代码思路

使用官方的 `mcp` Python SDK，结合 `FastAPI` 和 `asyncpg`，核心实现思路如下：

#### 1. 依赖与初始化

你需要安装官方 SDK：`pip install mcp`
创建一个 Server 实例：

```python
from mcp.server.fastapi import FastAPIServerTransport
from mcp.server import Server

# 创建 MCP Server 实例
mcp_db_server = Server("chuma-postgres-mcp")
```

#### 2. 注册探索工具 (Schema Discovery)

利用 `@mcp_db_server.tool()` 装饰器将 Python 函数暴露给大模型：

```python
@mcp_db_server.tool()
async def get_table_schema(table_name: str) -> str:
    """获取指定数据库表的结构信息（包含列名和类型）"""
    # 1. 使用 asyncpg 连接数据库
    # 2. 执行 SELECT column_name, data_type FROM information_schema.columns ...
    # 3. 将结果格式化为 Markdown 或 JSON 字符串返回给大模型
    pass
```

#### 3. 注册查询工具与安全限制 (Read-Only Query)

```python
@mcp_db_server.tool()
async def execute_sql_query(query: str) -> str:
    """执行只读 SQL 查询并返回结果，最多返回 100 条"""
    # 【安全细节 1】检查是否包含恶意关键字
    if any(keyword in query.upper() for keyword in ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER"]):
        return "Error: 仅允许执行 SELECT 查询。"
    
    # 【安全细节 2】使用 asyncpg 执行，强制追加 LIMIT 防止内存溢出
    # 【安全细节 3】将 asyncpg 的 Record 对象转换为 JSON 返回
    pass
```

#### 4. 挂载到 FastAPI 路由

通过 FastAPI 暴露 SSE 接口，让 `ai/app/agent/mcp_client.py` 可以连上来：

```python
from fastapi import FastAPI
from mcp.server.fastapi import FastAPIServerTransport

app = FastAPI()
transport = FastAPIServerTransport(mcp_db_server)

# 暴露给 AI 引擎的 MCP 接口
@app.get("/mcp/messages")
async def mcp_messages():
    return await transport.handle_sse()

@app.post("/mcp/messages")
async def mcp_post(request: Request):
    return await transport.handle_post(request)
```

### 四、 系统安全性与容错（核心考量）

由于大模型生成的内容具有不可控性，搭建此 MCP 服务时必须兜底：

1. **返回行数限制 (Row Limit)**：大模型可能会写出 `SELECT * FROM users`，如果表里有 10 万条数据，返回给大模型会导致上下文瞬间爆掉（Token 超限）。在执行查询时，必须在代码底层强制切片或追加 `LIMIT 100`。
2. **超时控制 (Timeout)**：如果大模型写了一个极其复杂的连表查询导致慢 SQL，MCP 服务必须配置查询超时（例如 `timeout=5.0` 秒），避免阻塞整个 FastAPI 进程。
3. **只读用户 (Read-Only Role)**：最高级别的安全不是靠正则过滤 SQL，而是去 PostgreSQL 里 `CREATE USER mcp_reader WITH PASSWORD 'xxx';`，并只赋予 `GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_reader;`。让 `.env` 里的 MCP 连接使用这个账号。

***

**总结**：
即使现在数据库是空的，我们完全可以先写出 **Server 骨架** 和 **Schema 探索工具 (`list_tables`,** **`get_schema`)**。
一旦你的同事用 Alembic 把表建好了，大模型立马就能通过这两个工具自己去“看”表结构，甚至直接通过 `execute_sql_query` 开始查数据了。
