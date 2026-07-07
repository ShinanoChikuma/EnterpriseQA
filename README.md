# EnterpriseQA

基于 RAG（Retrieval-Augmented Generation）的企业内部知识库智能问答系统。

## 架构

```
┌─────────────────────────────────────────────────┐
│                   Frontend                      │
│          Vue 3 + Vite + Element Plus            │
│         Pinia (state) · Axios (HTTP)            │
│         ECharts (analytics charts)              │
└──────────────────────┬──────────────────────────┘
                       │ REST API (/api/*)
┌──────────────────────▼──────────────────────────┐
│                   Backend                       │
│           Flask + SQLAlchemy + JWT              │
│  ┌──────────────┐  ┌────────────────────────┐   │
│  │  Auth & RBAC │  │  Knowledge Base CRUD   │   │
│  │  JWT + MD5   │  │  Document Parser       │   │
│  │  admin/user  │  │  (10+ formats)         │   │
│  └──────────────┘  └────────────────────────┘   │
│  ┌──────────────────────────────────────────┐   │
│  │           RAG Engine (LlamaIndex)        │   │
│  │  ┌──────────┐  ┌──────────┐  ┌───────┐  │   │
│  │  │ Chunking │  │Embedding │  │  LLM  │  │   │
│  │  │ 500/50   │  │DeepSeek  │  │DeepSeek│  │   │
│  │  │ overlap  │  │Embedding │  │ Chat  │  │   │
│  │  └──────────┘  └──────────┘  └───────┘  │   │
│  └──────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│                 Storage                         │
│  MySQL (metadata)  │  Vector Index (local FS)   │
│    users, docs,    │    kb_{id}/                │
│    chat_history,   │    SimpleVectorStore       │
│    kb metadata     │    (cosine similarity)     │
└─────────────────────────────────────────────────┘
```

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3, Vite, Element Plus, Pinia, Vue Router, Axios, ECharts |
| 后端 | Python Flask, SQLAlchemy, PyMySQL, PyJWT |
| RAG | LlamaIndex (CustomLLM + BaseEmbedding) |
| LLM | DeepSeek Chat API |
| Embedding | DeepSeek Embedding API |
| 数据库 | MySQL 8.x |
| 向量存储 | LlamaIndex SimpleVectorStore（本地持久化） |

## 核心原理

### 文档入库流程

1. **解析** — 根据文件类型选择解析器：PDF/DOCX/EPUB/HTML 用 LlamaIndex `SimpleDirectoryReader`，DOC 用 Word COM / LibreOffice 回退，CSV/XLSX/RTF 用自定义解析器
2. **切分** — `SentenceSplitter` 按 chunk_size=500、overlap=50 切分为节点
3. **向量化** — 批量调用 DeepSeek Embedding API 生成 embedding
4. **索引** — 节点写入 `VectorStoreIndex`，按 `kb_id` 独立持久化到 `vector_data/kb_{id}/`

### 问答流程

1. **Query** 送入对应知识库的 Retriever（top_k=4，余弦相似度）
2. 检索到的节点拼接为上下文，注入 System Prompt
3. 组装 `[system: context, user: question]` 调用 DeepSeek Chat
4. 返回答案 + 来源文档列表

### API 鉴权

JWT Bearer Token，登录接口返回 token，前端存入 localStorage，Axios 拦截器自动注入 `Authorization` 头。`admin_required` 装饰器保护管理接口。

## 项目结构

```
├── client/                  # Vue 3 前端
│   └── src/
│       ├── api/             # Axios 请求层（按模块拆分）
│       ├── views/           # 页面组件
│       ├── components/      # 通用组件
│       ├── stores/          # Pinia 状态管理
│       └── router/          # Vue Router 路由
└── server/                  # Flask 后端
    ├── routes/              # 路由层（蓝图）
    ├── models/              # SQLAlchemy 数据模型
    ├── services/            # 业务逻辑层
    │   └── llama/           # DeepSeek LLM/Embedding 适配器 + IndexManager
    └── utils/               # JWT、响应封装等工具
```

## 快速开始

```bash
# 后端
cd server
pip install -r requirements.txt
# 配置环境变量: MYSQL_HOST MYSQL_PORT MYSQL_USER MYSQL_PASSWORD MYSQL_DATABASE
python app.py

# 前端
cd client
npm install
npm run dev
```
