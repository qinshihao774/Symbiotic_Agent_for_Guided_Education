# 智教慧学

> 计算机科学学习智能助教助学平台 — 面向 408 考研 & 数据库原理

## 项目概述

智教慧学 是一个面向计算机科学学科的 AI 智能助教助学平台，通过"双引擎"架构（助学引擎 + 助教引擎）为学生提供个性化学习支持，为教师提供数据驱动的教学辅助。

- **学生侧**：知识图谱探索、GraphRAG 智能问答、个性化学习计划、做题记录归因分析、渐进式解题引导
- **教师侧**：学情分析报告、学生画像、风险预警、作业批改、教案推荐

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Element Plus + ECharts + Monaco Editor |
| 后端 | FastAPI + SQLAlchemy + Alembic + PostgreSQL |
| AI 引擎 | GraphRAG + GNN + 微调小模型（本地）+ 远程大模型 API |
| 向量数据库 | ChromaDB |
| 缓存/队列 | Redis |
| 部署 | Docker Compose |

## 项目结构

### Monorepo 总览

三个独立项目组成一个 Monorepo，通过 Docker Compose 统一编排：

- **frontend/** — Vue 3 前端应用
- **backend/** — FastAPI 后端服务（业务逻辑、数据库、认证）
- **ai/** — AI 引擎服务（GraphRAG、GNN、知识图谱构建、定时任务）

### frontend/ — Vue 3 前端

技术栈：Vue 3 + TypeScript + Element Plus + ECharts + Monaco Editor + Pinia

```
frontend/src/
├── api/              # 后端 API 调用封装（按模块一一对应后端路由）
│   ├── auth.ts
│   ├── knowledge.ts
│   ├── learning.ts
│   ├── practice.ts
│   ├── teacher.ts
│   └── ai.ts
├── assets/           # 静态资源
├── components/       # 通用 UI 组件（知识图谱可视化、Monaco Editor、AI 对话气泡）
├── composables/      # Vue 3 组合式函数（useAuth、useChat 等可复用逻辑）
├── layouts/          # 布局组件
│   ├── DefaultLayout.vue   # 学生侧布局（侧边栏 + 内容区）
│   └── TeacherLayout.vue   # 教师侧布局
├── pages/            # 页面组件
│   ├── auth/         # 登录、注册
│   ├── student/      # 仪表盘、图谱探索、练习、做题记录、AI 对话、学习计划
│   └── teacher/      # 课程管理、学生管理、学情报告、预警、批改
├── router/           # Vue Router 路由配置
├── stores/           # Pinia 全局状态管理（auth、knowledge、learning）
├── styles/           # 全局样式
├── utils/            # 工具函数（Axios 封装，含 JWT 注入和错误拦截）
├── App.vue
└── main.ts
```

### backend/ — FastAPI 后端

技术栈：FastAPI + SQLAlchemy + Alembic + PostgreSQL + JWT

采用**分层架构**（按技术层组织）：

```
backend/app/
├── api/              # HTTP 路由层
│   ├── auth.py           # 注册、登录、JWT 认证
│   ├── knowledge.py      # 知识图谱数据查询（供前端 ECharts 可视化）
│   ├── learning.py       # 学习计划、学习进度、学习历史
│   ├── practice.py       # 题目列表、做题提交、做题记录、归因分析、渐进式提示
│   ├── teacher.py        # 班级管理、学情分析、预警、学生画像、作业管理
│   └── ai_gateway.py     # 代理转发到 AI 引擎服务（注入 X-Service-Token）
├── services/         # 业务逻辑层（每个路由模块对应一个 service）
│   ├── auth_service.py
│   ├── knowledge_service.py
│   ├── learning_service.py
│   ├── practice_service.py
│   └── teacher_service.py
├── models/           # SQLAlchemy ORM 模型
│   ├── user.py
│   ├── knowledge.py
│   ├── question.py
│   ├── learning.py
│   └── teacher.py
├── schemas/          # Pydantic 请求/响应数据校验模型
│   ├── auth.py
│   ├── knowledge.py
│   ├── learning.py
│   ├── practice.py
│   └── teacher.py
├── core/             # 基础设施
│   ├── config.py         # 环境变量配置（Pydantic Settings）
│   ├── database.py       # 异步数据库连接与会话管理
│   ├── security.py       # JWT 生成/验证、密码哈希
│   └── deps.py           # FastAPI 依赖注入（当前用户解析等）
└── main.py           # FastAPI 应用入口
```

### ai/ — AI 引擎

技术栈：FastAPI + ChromaDB + PyTorch + PyG + APScheduler + Redis

承担**三类职责**：实时推理、异步批处理、定时任务。

```
ai/app/
├── api/              # HTTP 路由（由 backend 同步调用）
│   ├── rag.py            # GraphRAG 增强问答
│   ├── gnn.py            # GNN 题目推荐、教案推荐
│   └── kg.py             # 知识图谱抽取任务提交与状态查询
├── engines/          # 核心 AI 能力（纯逻辑，不依赖 HTTP/队列框架）
│   ├── graphrag/
│   │   ├── retriever.py      # 图检索（ChromaDB + 知识图谱结构遍历）
│   │   ├── generator.py      # LLM 生成（带来源标注）
│   │   └── prompts.py        # 提示词模板
│   ├── gnn/
│   │   ├── model.py          # GNN 模型定义
│   │   ├── trainer.py        # 模型训练
│   │   └── inference.py      # 推理（题目推荐 / 教案推荐）
│   └── llm/
│       ├── client.py         # 统一 LLM 客户端（chat/stream，含重试、超时）
│       └── profiles.py       # 模型端点配置（local_profile / remote_profile）
├── tasks/            # 异步任务 + 定时任务
│   ├── worker.py           # Redis 队列消费者
│   ├── scheduler.py        # 定时调度器（APScheduler）
│   ├── kg_extract.py       # 知识图谱抽取
│   ├── daily_profile.py    # 每日用户画像更新（凌晨 4:00）
│   └── daily_question.py   # 每日一题生成（凌晨 4:30）
├── schemas/          # 请求/响应 Pydantic 模型
│   ├── rag.py
│   ├── gnn.py
│   └── common.py
├── dependencies.py   # 公共依赖（服务间认证：X-Service-Token）
└── config.py         # AI 引擎配置
```

## 架构说明

### 系统通信模式

```
frontend  ←── HTTP ──→  backend  ←── HTTP(同步)/Redis(异步) ──→  ai
```

| 类型 | 协议 | 用途 |
|------|------|------|
| 实时查询 | HTTP REST | RAG 问答、GNN 推荐（秒级响应） |
| 异步任务 | Redis 队列 | 知识图谱抽取（长耗时批处理） |
| 定时任务 | APScheduler | 每日画像更新、每日一题生成 |

### 服务间认证

backend → AI 引擎的 HTTP 调用通过 `X-Service-Token` 请求头进行服务间认证：

```
backend (ai_gateway.py)          ai (dependencies.py)
      │                                │
      │  POST /rag/query               │
      │  X-Service-Token: <token>  ──→ │  verify_service_token()
      │                                │  token == settings.SERVICE_TOKEN?
      │                          ←──   │  通过 → 执行业务路由
      │                                │  拒绝 → 403 Forbidden
```

- 两个服务通过各自的 `.env` 配置同一个 token 值（`AI_SERVICE_TOKEN` / `SERVICE_TOKEN`）
- `/health` 端点不经过认证，供 Docker 健康检查使用
- 测试时可通过 FastAPI 的 `app.dependency_overrides` 跳过校验

### 双模型策略

| 模式 | 触发方式 | 模型 | 场景 |
|------|---------|------|------|
| 快速问答 | 用户在 UI 主动选择 | 本地微调小模型 | 基础概念问答，快速响应 |
| 深度解答 | 用户在 UI 主动选择 | GraphRAG + 远程大模型 | 需要知识检索、来源标注的复杂问题 |

### 数据存储

| 存储 | 技术 | 职责 | 管理者 |
|------|------|------|--------|
| 关系型数据库 | PostgreSQL | 用户、题目、做题记录、学习计划、班级、学情 | backend |
| 向量数据库 | ChromaDB | 知识图谱嵌入、文档向量（语义检索） | ai |
| 缓存/队列 | Redis | 会话缓存、异步任务队列、定时任务锁 | 两者共享 |

## 快速开始

### 环境要求

- Docker & Docker Compose
- Node.js 18+（本地前端开发）
- Python 3.11+（本地后端/AI 开发）

### 启动全部服务

```bash
# 1. 复制环境变量
cp .env.example .env

# 2. 启动所有服务
docker-compose up -d

# 3. 访问
# 前端:      http://localhost
# 后端 API:  http://localhost:8000/docs
# AI 引擎:   http://localhost:8001/docs
```

### 本地开发

```bash
# 前端
cd frontend
npm install
npm run dev            # http://localhost:5173

# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# AI 引擎
cd ai
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

### 数据库迁移

```bash
cd backend
alembic upgrade head                        # 执行迁移
alembic revision --autogenerate -m "描述"   # 生成迁移文件
```
