# TimeTrace — Agent Coding Spec

> 本文档是 AI Agent 在此代码库上工作时的**强制规范**。
> 使用 RFC 2119 关键词：MUST（必须）、MUST NOT（禁止）、SHOULD（应该）、FORBIDDEN（绝对禁止）。

---

## 1. 架构硬规则 (Architecture)

### 1.1 扁平结构 — MUST

后端严格遵循以下目录结构，MUST NOT 创建新的子目录层级：

```
backend/app/
├── main.py        # FastAPI app, lifespan, seed, migrations
├── config.py      # 所有配置（pydantic-settings）
├── database.py    # SQLAlchemy engine + session
├── models.py      # 所有 ORM 模型
├── schemas.py     # 所有 Pydantic schemas
├── deps.py        # 依赖：get_db, auth, 服务工厂
├── llm.py         # LLM 集成（ZhipuGLM + Mock）
├── nlp.py         # NLP 处理（Jieba）
├── auth.py        # 仅做 re-export，禁止添加新逻辑
├── services/      # 业务逻辑（每个文件一个 service）
└── routes/        # API 端点（每个文件一个 domain）
```

### 1.2 禁止的抽象 — FORBIDDEN

以下模式在此项目中 FORBIDDEN，因为此项目规模不需要这些抽象：

- FORBIDDEN: 创建 `Protocol` / `ABC` / `Interface` 抽象类
- FORBIDDEN: 创建 Repository Pattern（直接使用 SQLAlchemy Session）
- FORBIDDEN: 创建 DI Container / Service Locator
- FORBIDDEN: 创建新的 `__init__.py` 文件（仅允许 `services/` 和 `routes/`）
- FORBIDDEN: 创建 `core/`、`domain/`、`infrastructure/`、`application/` 等子目录
- FORBIDDEN: 模块内通过 re-export 间接引用（除 `auth.py`）

**理由**：此项目为通用事件情报平台，多源采集、后台处理，前端只展示精炼的事件时间线。不需要可替换实现。直接 > 间接。

### 1.3 文件职责边界 — MUST

| 文件 | 职责 | 禁止 |
|------|------|------|
| `models.py` | ORM 模型定义 | MUST NOT 放业务逻辑 |
| `schemas.py` | Pydantic 请求/响应模型 | MUST NOT 放 ORM 模型 |
| `deps.py` | FastAPI 依赖 + 服务工厂 + LLM/NLP 单例 | MUST NOT 放路由处理函数 |
| `services/*.py` | 业务逻辑 | MUST NOT 定义 API 路由 |
| `routes/*.py` | HTTP 端点 + 参数校验 | SHOULD NOT 包含复杂业务逻辑 |
| `llm.py` | LLM 调用封装 | MUST NOT 依赖 models/schemas |
| `nlp.py` | NLP 处理封装 | MUST NOT 依赖 models/schemas |

---

## 2. Import 规则

### 2.1 允许的 Import 路径 — MUST

```python
# routes/ 内的文件：
from ..deps import get_db, get_current_user, require_admin, get_*_service
from ..models import Article, Event, ...
from ..schemas import ArticleOut, PageResponse, ...
from ..database import SessionLocal        # 仅在 background tasks 中

# services/ 内的文件：
from ..models import Article, Event, ...   # 直接引用 models
from ..llm import ...                      # 通过构造函数接收，不直接 import
from ..nlp import ...                      # 通过构造函数接收，不直接 import

# main.py：
from .config import settings
from .database import SessionLocal, engine
from .models import Base, User
from .deps import hash_password
from .routes import users, articles, events, rss, admin
```

### 2.2 禁止的 Import — MUST NOT

- MUST NOT: `from ..core.*`（目录已删除）
- MUST NOT: `from ..domain.*`（目录已删除）
- MUST NOT: `from ..infrastructure.*`（目录已删除）
- MUST NOT: `from ..application.*`（目录已删除）
- MUST NOT: 在 `routes/` 中直接 import `services/` 的类（通过 `deps.py` 的工厂函数获取）
- MUST NOT: 在 `llm.py` 或 `nlp.py` 中 import `models.py` 或 `schemas.py`

---

## 3. Service 规则

### 3.1 构造函数签名 — MUST

所有 Service MUST 接受 `(db: Session, llm, nlp)` 作为前三个参数：

```python
class CrawlService:
    def __init__(self, db: Session, llm, nlp):
        self._db = db
        self._llm = llm
        self._nlp = nlp
```

SHOULD NOT 在 Service 内部创建新的数据库 Session。

### 3.2 数据库操作 — MUST

Service MUST 直接使用 SQLAlchemy Session，不经过 Repository 包装：

```python
# ✅ 正确
self._db.query(Article).filter(Article.id == article_id).first()

# ❌ 禁止
self._article_repo.find_by_id(article_id)
```

### 3.3 服务工厂 — MUST

新的 Service MUST 在 `deps.py` 中添加对应的工厂函数：

```python
def get_new_service(db: Session):
    from .services.new_service import NewService
    return NewService(db, get_llm(), get_nlp())
```

---

## 4. 路由规则

### 4.1 路由文件命名 — MUST

路由文件 MUST 以域名命名，放在 `routes/` 目录下：
- `users.py` → `/api/users/*`
- `articles.py` → `/api/articles/*`
- `events.py` → `/api/events/*`
- `rss.py` → `/api/rss/*`
- `admin.py` → `/api/admin/*`

### 4.2 新建路由文件时 — MUST

1. 在 `routes/` 下创建新文件
2. 定义 `router = APIRouter(prefix="/api/<domain>", tags=["<domain>"])`
3. 在 `main.py` 中 `from .routes import <domain>` 并 `app.include_router(<domain>.router)`

### 4.3 API 认证 — MUST

```python
# 公开端点：不加认证依赖
def public_events(db: Session = Depends(get_db)):

# 需要登录：
def get_events(user=Depends(get_current_user), db: Session = Depends(get_db)):

# 需要管理员：
def admin_action(_admin=Depends(require_admin), db: Session = Depends(get_db)):
```

### 4.4 分页 — SHOULD

列表端点 SHOULD 使用 `PageResponse` 统一分页：

```python
@router.get("", response_model=PageResponse)
def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    # ...
    return PageResponse(items=..., total=total, page=page, page_size=page_size,
                        total_pages=(total + page_size - 1) // page_size)
```

### 4.5 Background Tasks — MUST

后台任务 MUST 创建独立 Session，并在 `finally` 中关闭：

```python
def _run():
    db = SessionLocal()
    try:
        service = get_*_service(db)
        service.do_work()
    finally:
        db.close()
```

---

## 5. 编码风格

### 5.1 命名 — MUST

| 类型 | 风格 | 示例 |
|------|------|------|
| 文件 | `snake_case` | `crawl.py`, `aggregate.py` |
| 类 | `PascalCase` | `CrawlService`, `ArticleOut` |
| 函数/变量 | `snake_case` | `get_db`, `article_count` |
| 常量 | `UPPER_SNAKE` | `STOP_WORDS`, `CORS_ORIGINS` |
| 私有方法 | `_prefix` | `_process_article`, `_find_best_match` |
| ORM 字段 | `snake_case` | `published_at`, `rss_source_id` |

### 5.2 错误处理 — MUST

```python
# API 层：使用 HTTPException
raise HTTPException(404, "Article not found")

# Service 层：使用 logging + 返回 dict
logger.warning(f"LLM call failed: {e}")
return {"success": False, "error": str(e)}

# 数据库迁移：静默忽略已存在的列
try:
    cursor.execute(sql)
except Exception:
    pass  # 列已存在
```

### 5.3 时间处理 — MUST

所有时间 MUST 使用 UTC：

```python
from datetime import datetime, timezone
datetime.now(timezone.utc)  # ✅
datetime.now()              # ❌ 禁止使用本地时间
```

### 5.4 中文注释 — SHOULD

此项目面向中文用户，代码注释和 docstring SHOULD 使用中文：

```python
def extract_keywords(self, text: str, topk: int = 10) -> list[str]:
    """提取关键词，返回去重后的词列表。"""
```

---

## 6. 数据库规则

### 6.1 模型定义 — MUST

所有 ORM 模型 MUST 定义在 `models.py` 中，MUST NOT 分散到其他文件。

### 6.2 Schema 定义 — MUST

所有 Pydantic schema MUST 定义在 `schemas.py` 中。

### 6.3 数据库迁移 — MUST

新增列 MUST 在 `main.py` 的 `run_migrations()` 中添加 ALTER TABLE：

```python
migrations = [
    ("ALTER TABLE articles ADD COLUMN new_field TEXT", "描述"),
]
```

### 6.4 种子数据 — MUST

种子数据 MUST 在 `main.py` 的 `seed_database()` 中处理。

---

## 7. 前端规则

### 7.1 目录结构 — MUST

```
web/src/
├── api/client.ts        # Axios 实例，MUST NOT 创建多个
├── stores/auth.ts       # Zustand 全局状态
├── components/          # 可复用 UI 组件
├── pages/               # 页面组件
└── App.tsx              # 路由配置
```

### 7.2 API 调用 — MUST

所有 API 调用 MUST 通过 `api/client.ts` 的 axios 实例：

```typescript
import api from '../api/client';
const res = await api.get('/api/events/public');
```

MUST NOT 使用裸 `fetch()` 或创建新的 axios 实例。

### 7.3 状态管理 — SHOULD

- 全局认证状态：Zustand (`stores/auth.ts`)
- 页面级数据：`useState` + `useEffect`
- SHOULD NOT 为每个功能创建新的 Zustand store

---

## 8. Git 规范

### 8.1 提交消息 — SHOULD

```
<type>: <简短描述>

type: feat | fix | refactor | docs | test | chore
```

示例：
- `feat: 添加新闻来源管理接口`
- `fix: 修复事件聚合相似度计算`
- `refactor: 扁平化后端架构`

### 8.2 禁止提交 — MUST NOT

- MUST NOT 提交 `.env` 文件
- MUST NOT 提交 `*.db` 数据库文件
- MUST NOT 提交 `__pycache__/` 或 `node_modules/`

---

## 9. 添加新功能 Checklist

当需要添加新功能时，Agent MUST 按以下顺序执行：

1. **Model** — 在 `models.py` 添加 ORM 模型或字段
2. **Migration** — 在 `main.py` 的 `run_migrations()` 添加 ALTER TABLE（如需新列）
3. **Schema** — 在 `schemas.py` 添加 Pydantic 请求/响应模型
4. **Service**（如需） — 在 `services/` 创建业务逻辑文件，在 `deps.py` 添加工厂函数
5. **Route** — 在 `routes/` 添加 API 端点，在 `main.py` 注册 router
6. **验证** — 启动服务器，测试新端点

---

## 10. Quick Reference

```
启动后端:  cd backend && python run.py
启动前端:  cd web && npm run dev
测试导入:  python -c "from app.main import app; print('OK')"
API 文档:  http://localhost:8000/docs
默认管理员: admin / admin123
数据库:    SQLite at backend/timetrace.db
```
