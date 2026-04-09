# TimeTrace-NewS 🗞️

> **新闻事件追踪与时间线分析平台** — 将碎片化的新闻自动聚合为有时间线的完整事件故事

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6.svg)](https://typescriptlang.org)
[![Tests](https://img.shields.io/badge/Tests-54%20passed-brightgreen.svg)]()

---

## ✨ 核心特性

- **🔀 多源聚合** — RSS 订阅自动采集，智能去重与相似度检测
- **🧠 三级管线** — 蒸馏 (Distiller) → 推演 (Reasoner) → 审计 (Auditor) LLM 驱动处理流水线
- **📅 事件时间线** — 自动标注"起因 → 经过 → 结果 → 后续"四阶段，呈现完整事件脉络
- **📊 可信度评估** — 多维度信源评级（A/B/C 层级），来源声誉评分
- **⚡ 实时管线可视化** — 管线状态面板、审计日志、处理进度追踪
- **🔐 安全设计** — JWT 认证、RBAC 权限、敏感信息隔离、CORS 严格配置

---

## 📸 系统架构

```
┌──────────────────────────────────────────────────────┐
│                   Frontend (React 19)                 │
│    Pages · Components · Zustand Store · Axios HTTP    │
└──────────────────────┬───────────────────────────────┘
                       ↓ REST API
┌──────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                    │
│                                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │  API Routes                                      │ │
│  │  users · articles · events · rss · admin         │ │
│  └───────────────────┬─────────────────────────────┘ │
│                      ↓                                │
│  ┌─────────────────────────────────────────────────┐ │
│  │  三级管线 Pipeline                               │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐        │ │
│  │  │ Distiller│→│ Reasoner │→│ Auditor  │        │ │
│  │  │ 事实蒸馏  │ │ 事件推演  │ │ 伦理审计  │        │ │
│  │  └──────────┘ └──────────┘ └──────────┘        │ │
│  └───────────────────┬─────────────────────────────┘ │
│                      ↓                                │
│  ┌─────────────────────────────────────────────────┐ │
│  │  LLM · NLP · SQLite + Migrations                │ │
│  └─────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- npm 9+

### 1. 克隆项目

```bash
git clone https://github.com/your-username/TimeTrace-NewS.git
cd TimeTrace-NewS
```

### 2. 后端配置

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp ../.env.example ../.env
# 编辑 .env 文件，至少设置 ADMIN_PASSWORD
```

### 3. 前端配置

```bash
cd web

# 安装依赖
npm install
```

### 4. 启动服务

**方式一：一键启动 (Windows)**
```bash
start-all.bat
```

**方式二：分别启动**
```bash
# 终端 1 — 后端 (http://localhost:8000)
cd backend && python run.py

# 终端 2 — 前端 (http://localhost:3001)
cd web && npm run dev
```

### 5. 访问

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:3001 |
| API 文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/api/health |

---

## 📁 项目结构

```
TimeTrace-NewS/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 应用入口 + lifespan
│   │   ├── config.py        # Pydantic Settings 配置
│   │   ├── database.py      # SQLAlchemy 引擎与会话
│   │   ├── models.py        # ORM 模型
│   │   ├── schemas.py       # Pydantic 序列化模型
│   │   ├── deps.py          # 依赖注入（认证、DB、服务工厂）
│   │   ├── auth.py          # 认证工具（向后兼容重导出）
│   │   ├── routes/          # API 路由
│   │   │   ├── users.py     # 用户注册/登录/关注
│   │   │   ├── articles.py  # 文章 CRUD
│   │   │   ├── events.py    # 事件列表/详情/时间线
│   │   │   ├── rss.py       # RSS 源管理
│   │   │   └── admin.py     # 管理后台（管线/LLM编排/统计）
│   │   ├── services/        # 业务服务
│   │   │   ├── crawl.py     # RSS 采集服务
│   │   │   ├── process.py   # 文章处理（NLP + 去重）
│   │   │   ├── aggregate.py # 事件聚合（嵌入 + 语义匹配）
│   │   │   ├── timeline.py  # 时间线构建
│   │   │   └── pipeline.py  # 三级管线编排（线程安全）
│   │   ├── llm.py           # LLM 抽象层（OpenAI 兼容 + Mock）
│   │   └── nlp.py           # NLP 处理器（Jieba 分词）
│   ├── tests/               # 测试套件（54 个测试）
│   │   ├── test_api.py      # API 集成测试
│   │   └── test_pipeline.py # 管线单元测试
│   └── requirements.txt
├── web/                     # React 前端
│   ├── src/
│   │   ├── App.tsx          # 路由配置
│   │   ├── types.ts         # 共享类型定义
│   │   ├── api/             # API 客户端（Axios + 401 拦截）
│   │   ├── stores/          # Zustand 状态管理
│   │   ├── pages/           # 页面组件
│   │   │   ├── Home.tsx     # 首页（事件流 + 分类筛选）
│   │   │   ├── EventDetail.tsx # 事件详情 + 时间线
│   │   │   ├── Profile.tsx  # 个人中心
│   │   │   └── admin/       # 管理后台
│   │   │       ├── Dashboard.tsx
│   │   │       ├── PipelineViz.tsx  # 管线可视化
│   │   │       ├── PipelineLog.tsx  # 审计日志
│   │   │       ├── Settings.tsx     # LLM 编排配置
│   │   │       ├── EventManage.tsx  # 事件合并/文章分配
│   │   │       ├── Articles.tsx
│   │   │       ├── Events.tsx
│   │   │       └── Sources.tsx
│   │   └── components/      # 共享 UI 组件
│   └── package.json
├── .env.example             # 环境变量模板
├── .gitignore
├── ARCHITECTURE.md          # 架构文档
├── PLAN.md                  # 重构方案
└── start-all.bat            # 一键启动脚本
```

---

## 🧪 测试

```bash
cd backend

# 运行全部测试（54 个）
python -m pytest tests/ -v

# 运行 API 集成测试
python -m pytest tests/test_api.py -v

# 运行管线单元测试
python -m pytest tests/test_pipeline.py -v
```

---

## ⚙️ 配置项

所有配置通过环境变量或 `.env` 文件设置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ADMIN_PASSWORD` | *(必设)* | 管理员密码，未设置时自动生成随机密码 |
| `DATABASE_URL` | `sqlite:///./timetrace.db` | 数据库连接字符串 |
| `JWT_EXPIRE_HOURS` | `24` | JWT Token 过期时间 |
| `DEBUG` | `false` | 调试模式 |
| `LLM_API_KEY` | *(空)* | LLM API 密钥 |
| `LLM_API_BASE` | `https://open.bigmodel.cn/api/paas/v4` | LLM API 地址 |
| `LLM_MODEL` | *(空)* | LLM 模型名称 |
| `CORS_ORIGINS` | `http://localhost:3001` | 允许的前端来源 |

> 💡 未配置 LLM 时系统自动使用 MockLLM，所有管线逻辑仍可正常运行和测试。

---

## 🔧 技术亮点

| 领域 | 实现 |
|------|------|
| **后端框架** | FastAPI + Pydantic v2 Settings + SQLAlchemy ORM |
| **认证** | JWT + bcrypt + RBAC（admin/user） |
| **三级管线** | Distiller → Reasoner → Auditor，线程安全，支持 LLM 编排 |
| **NLP** | Jieba 分词 + TF-IDF + 嵌入向量语义匹配 |
| **前端框架** | React 19 + TypeScript + Vite |
| **状态管理** | Zustand + persist（单数据源） |
| **API 通信** | Axios + 401 防抖拦截 + Token 自动刷新 |
| **数据库** | SQLite + 原生迁移 + 批量查询优化（消除 N+1） |
| **测试** | pytest + TestClient（54 个集成/单元测试） |

---

## 📄 License

MIT License
