# TimeTrace 架构文档

## 项目概述

TimeTrace 是一个新闻事件追踪系统，核心功能是将碎片化的新闻聚合为有时间线的完整事件，支持 RSS 订阅爬取、智能聚合、事件追踪等功能。

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (React 19)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   Pages     │  │ Components  │  │   Stores    │                 │
│  │  (路由页面)  │  │  (UI组件)   │  │  (Zustand)  │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│                           ↓ Axios HTTP                              │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ REST API
┌─────────────────────────────────────────────────────────────────────┐
│                        Backend (FastAPI)                            │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    API Layer (api/)                          │   │
│  │  users.py │ articles.py │ events.py │ rss.py │ admin.py     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Application Layer (application/)                │   │
│  │  ┌───────────────┐  ┌───────────────────────────────────┐   │   │
│  │  │    dto/       │  │           services/               │   │   │
│  │  │  (DTO/Schemas)│  │ CrawlService │ ProcessService    │   │   │
│  │  │               │  │ AggregateService                  │   │   │
│  │  └───────────────┘  └───────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                Domain Layer (domain/)                        │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │                   interfaces/                        │    │   │
│  │  │  Repository │ LLMProvider │ NLPProcessor (Protocols)│    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │            Infrastructure Layer (infrastructure/)            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │  │    llm/     │  │    nlp/     │  │    persistence/     │  │   │
│  │  │ ZhipuLLM    │  │ JiebaProc   │  │ models/ repositories│  │   │
│  │  │ MockLLM     │  │             │  │   (ORM)  (Repo Impl)│  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Core (core/)                              │   │
│  │         config.py │ database.py │ container.py              │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    External Services                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │   智谱 GLM-4    │  │   RSS Feeds     │  │   People.cn     │    │
│  │ (LLM/Embedding) │  │   (新闻源)      │  │   (人民网)      │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 目录结构

```
TimeTrace-NewS/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── main.py            # 应用入口
│   │   ├── auth.py            # JWT 认证模块
│   │   ├── models.py          # 旧 ORM (保留兼容)
│   │   ├── schemas.py         # 旧 Schema (保留兼容)
│   │   │
│   │   ├── api/               # API 路由层
│   │   │   ├── users.py       # 用户认证/关注
│   │   │   ├── articles.py    # 文章 CRUD/人民网
│   │   │   ├── events.py      # 事件 CRUD/时间线
│   │   │   ├── rss.py         # RSS 源管理
│   │   │   └── admin.py       # 管理接口/后台任务
│   │   │
│   │   ├── application/       # 应用服务层
│   │   │   ├── dto/           # 数据传输对象
│   │   │   │   └── schemas.py
│   │   │   └── services/      # 业务逻辑编排
│   │   │       ├── crawl_service.py      # 爬虫服务
│   │   │       ├── process_service.py    # 文章处理服务
│   │   │       └── aggregate_service.py  # 事件聚合服务
│   │   │
│   │   ├── domain/            # 领域层
│   │   │   └── interfaces/    # 接口定义 (Protocol)
│   │   │       ├── repository.py      # 仓储接口
│   │   │       ├── llm_provider.py    # LLM 提供者接口
│   │   │       └── nlp_processor.py   # NLP 处理器接口
│   │   │
│   │   ├── infrastructure/    # 基础设施层
│   │   │   ├── llm/           # LLM 实现
│   │   │   │   ├── zhipu_provider.py   # 智谱 GLM
│   │   │   │   └── mock_provider.py    # Mock 实现
│   │   │   ├── nlp/           # NLP 实现
│   │   │   │   └── jieba_processor.py  # 结巴分词
│   │   │   ├── persistence/   # 持久化
│   │   │   │   ├── models/
│   │   │   │   │   └── orm.py          # ORM 模型
│   │   │   │   └── repositories/       # 仓储实现
│   │   │   │       ├── article_repo.py
│   │   │   │       ├── event_repo.py
│   │   │   │       ├── rss_repo.py
│   │   │   │       └── user_repo.py
│   │   │   └── tasks/         # 后台任务
│   │   │
│   │   └── core/              # 核心配置
│   │       ├── config.py      # 配置管理
│   │       ├── database.py    # 数据库连接
│   │       └── container.py   # DI 容器
│   │
│   ├── tests/                 # 测试
│   └── requirements.txt
│
├── web/                       # 前端应用
│   ├── src/
│   │   ├── main.tsx          # 入口
│   │   ├── App.tsx           # 路由配置
│   │   ├── api/
│   │   │   └── client.ts     # API 客户端
│   │   ├── components/       # UI 组件
│   │   │   ├── Layout.tsx
│   │   │   ├── Timeline.tsx
│   │   │   ├── EventCard.tsx
│   │   │   └── ...
│   │   ├── pages/            # 页面
│   │   │   ├── Home.tsx
│   │   │   ├── EventDetail.tsx
│   │   │   ├── Login.tsx
│   │   │   └── admin/
│   │   └── stores/
│   │       └── auth.ts       # Zustand 状态
│   └── package.json
│
└── timetrace.db              # SQLite 数据库
```

---

## 技术栈

### 后端

| 类别 | 技术 | 用途 |
|------|------|------|
| Web 框架 | FastAPI | REST API 服务 |
| ORM | SQLAlchemy | 数据库操作 |
| 数据库 | SQLite | 数据存储 |
| LLM | 智谱 GLM-4 | 文本摘要/Embedding |
| NLP | jieba | 中文分词/关键词提取 |
| 认证 | JWT | 用户身份验证 |
| 配置 | pydantic-settings | 环境变量管理 |

### 前端

| 类别 | 技术 | 用途 |
|------|------|------|
| 框架 | React 19 | UI 构建 |
| 语言 | TypeScript | 类型安全 |
| 构建 | Vite | 开发/打包 |
| 路由 | react-router-dom | 页面导航 |
| 状态 | Zustand | 全局状态管理 |
| 样式 | Tailwind CSS | 样式框架 |
| HTTP | Axios | API 请求 |
| 图标 | lucide-react | 图标库 |

---

## 核心模块

### 1. 依赖注入容器 (`core/container.py`)

简易 DI 容器，管理所有服务的创建和依赖：

```python
container = Container()

# 获取服务实例
crawl_svc = container.get_crawl_service(db)
process_svc = container.get_process_service(db)
aggregate_svc = container.get_aggregate_service(db)
```

### 2. 领域接口 (`domain/interfaces/`)

使用 Python Protocol 定义抽象接口：

```python
class LLMProvider(Protocol):
    def is_available(self) -> bool: ...
    def get_embedding(self, text: str) -> list[float] | None: ...
    def generate_summary(self, text: str) -> str | None: ...

class NLPProcessor(Protocol):
    def extract_keywords(self, text: str) -> list[str]: ...
    def extract_entities(self, text: str) -> list[dict]: ...
```

### 3. 应用服务 (`application/services/`)

#### CrawlService - 爬虫服务
- `crawl_source(source_id)` - 爬取单个源
- `crawl_all()` - 爬取所有活跃源

#### ProcessService - 处理服务
- `process_unprocessed()` - 处理未处理文章
- `generate_embeddings()` - 生成 Embedding

#### AggregateService - 聚合服务
- `aggregate_all()` - 执行完整聚合流程
- 核心算法：Embedding 余弦相似度 + 关键词/实体 fallback

### 4. 事件聚合算法

```
1. 自动关闭超时事件 (auto_close_days)
2. 获取未关联文章
3. 获取活跃事件窗口
4. 对每篇文章：
   a. 提取关键词/实体
   b. 生成 Embedding (如可用)
   c. 计算与现有事件的相似度
      - 有 Embedding: 余弦相似度 (threshold=0.55)
      - 无 Embedding: 关键词(0.4) + 实体(0.35) + 标题(0.25)
   d. 匹配成功 → 关联到事件
   e. 匹配失败 → 创建新事件
5. 增强：LLM 生成事件标题/摘要
```

---

## 数据模型

### 核心实体

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    User     │     │  RssSource  │     │   Article   │
├─────────────┤     ├─────────────┤     ├─────────────┤
│ id          │     │ id          │     │ id          │
│ username    │     │ name        │     │ title       │
│ email       │     │ url         │     │ content     │
│ password_hash│    │ category    │     │ summary     │
│ role        │     │ is_active   │     │ source_url  │
│ avatar      │     │ last_crawled│     │ keywords[]  │
└─────────────┘     │ credibility │     │ entities[]  │
      │             └─────────────┘     │ embedding[] │
      │                   │             │ published_at│
      ▼                   ▼             │ credibility│
┌─────────────┐     ┌─────────────┐     └─────────────┘
│  UserFollow │     │   Article   │           │
├─────────────┤     │ (rss_source)│           │
│ user_id     │     └─────────────┘           │
│ event_id    │                               │
└─────────────┘                               ▼
      │             ┌─────────────┐     ┌─────────────┐
      │             │    Event    │◄────│EventArticle │
      │             ├─────────────┤     ├─────────────┤
      └────────────►│ id          │     │ event_id    │
                    │ title       │     │ article_id  │
                    │ summary     │     │ relevance   │
                    │ category    │     └─────────────┘
                    │ importance  │
                    │ status      │
                    │ embedding[] │
                    │ start_date  │
                    │ end_date    │
                    └─────────────┘
```

---

## API 端点

### 公开接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/info` | 系统信息 |
| POST | `/api/users/register` | 用户注册 |
| POST | `/api/users/login` | 用户登录 |
| GET | `/api/events/public` | 公开事件列表 |
| GET | `/api/events/{id}/public` | 公开事件详情 |
| GET | `/api/articles/people-daily/*` | 人民网新闻 |

### 认证接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/users/me` | 当前用户 |
| POST | `/api/users/follow/{id}` | 关注事件 |
| DELETE | `/api/users/follow/{id}` | 取消关注 |
| GET | `/api/users/follows` | 关注列表 |
| GET | `/api/users/recommendations` | 推荐事件 |

### 管理接口 (需 admin 权限)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/admin/stats` | 系统统计 |
| POST | `/api/admin/aggregate` | 触发聚合 |
| POST | `/api/admin/reembed` | 重新生成 Embedding |
| POST | `/api/rss/crawl` | 触发爬虫 |
| POST | `/api/admin/people/fetch` | 抓取人民网历史新闻 |

---

## 配置项

| 环境变量 | 默认值 | 描述 |
|----------|--------|------|
| `DATABASE_URL` | `sqlite:///./timetrace.db` | 数据库连接 |
| `LLM_API_KEY` | `""` | 智谱 API Key |
| `LLM_MODEL` | `glm-4-flash` | LLM 模型 |
| `EMBEDDING_MODEL` | `embedding-3` | Embedding 模型 |
| `EMBEDDING_THRESHOLD` | `0.55` | 相似度阈值 |
| `EVENT_TIME_WINDOW_DAYS` | `30` | 事件时间窗口 |
| `EVENT_AUTO_CLOSE_DAYS` | `14` | 自动关闭天数 |
| `CRAWL_INTERVAL_MINUTES` | `30` | 爬虫间隔 |
| `ADMIN_USERNAME` | `admin` | 管理员用户名 |
| `ADMIN_PASSWORD` | `admin123` | 管理员密码 |
| `CORS_ORIGINS` | `http://localhost:5173` | CORS 白名单 |

---

## 开发指南

### 启动后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
python run.py
```

### 启动前端

```bash
cd web
npm install
npm run dev
```

### 运行测试

```bash
cd backend
pytest
```

---

## 扩展点

### 添加新的 LLM 提供者

1. 实现 `LLMProvider` Protocol
2. 在 `container.py` 中添加选择逻辑

```python
class OpenAIProvider:
    def is_available(self) -> bool: ...
    def get_embedding(self, text: str) -> list[float] | None: ...
```

### 添加新的数据源

1. 创建爬虫服务或扩展 `CrawlService`
2. 添加对应的 API 端点
3. 文章自动进入聚合流程

### 添加新的 NLP 处理器

1. 实现 `NLPProcessor` Protocol
2. 在 `container.py` 中注册
