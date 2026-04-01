# TimeTrace 新闻事件追踪系统 - 实施计划

## 技术栈决策

| 层 | 技术 | 理由 |
|---|---|---|
| 后端 | FastAPI + SQLAlchemy + SQLite | 轻量、异步、零配置数据库 |
| NLP | jieba + TF-IDF | 中文分词成熟方案，离线运行 |
| LLM | 智谱 GLM-4-Flash | 国内直连、免费额度充足 |
| 前端 | React 19 + TypeScript + Vite + Tailwind CSS 4 | 统一应用，角色路由区分前台/后台 |
| 状态管理 | Zustand | 轻量持久化 |
| 认证 | JWT Bearer Token | 前后端标准方案 |

## 项目结构

```
TimeTrace-NewS/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口 + 生命周期
│   │   ├── config.py            # Pydantic Settings
│   │   ├── database.py          # SQLAlchemy engine + session
│   │   ├── models.py            # 所有 ORM 模型
│   │   ├── schemas.py           # Pydantic 请求/响应模型
│   │   ├── auth.py              # JWT 工具函数
│   │   ├── api/
│   │   │   ├── articles.py      # 文章 CRUD
│   │   │   ├── events.py        # 事件 CRUD + 时间线
│   │   │   ├── users.py         # 注册/登录/关注
│   │   │   ├── rss.py           # RSS 源管理
│   │   │   └── admin.py         # 管理后台统计
│   │   └── services/
│   │       ├── crawler.py       # RSS 采集 (feedparser)
│   │       ├── processor.py     # 文本处理 (jieba + TF-IDF)
│   │       ├── aggregator.py    # 事件聚合 (相似度匹配)
│   │       └── llm_service.py   # LLM 调用 (智谱 GLM)
│   ├── requirements.txt
│   └── run.py
├── web/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── api/client.ts        # Axios 实例 + 拦截器
│   │   ├── stores/
│   │   │   └── auth.ts          # Zustand auth store
│   │   ├── components/
│   │   │   ├── Layout.tsx       # 导航栏 + 侧边栏
│   │   │   ├── Timeline.tsx     # 时间线核心组件
│   │   │   ├── EventCard.tsx    # 事件卡片
│   │   │   ├── ArticleCard.tsx  # 文章卡片
│   │   │   └── AdminLayout.tsx  # 管理后台布局
│   │   └── pages/
│   │       ├── Home.tsx         # 首页 - 事件时间线流
│   │       ├── EventDetail.tsx  # 事件详情 - 完整时间线
│   │       ├── Login.tsx        # 登录
│   │       ├── Register.tsx     # 注册
│   │       ├── Profile.tsx      # 个人中心 + 关注列表
│   │       └── admin/
│   │           ├── Dashboard.tsx  # 数据概览
│   │           ├── Sources.tsx    # RSS 源管理
│   │           ├── Articles.tsx   # 文章管理
│   │           └── Events.tsx     # 事件管理
│   ├── package.json
│   └── vite.config.ts
└── start-all.bat                # 一键启动
```

## 数据库设计

```
users:          id, username, email, password_hash, role(user/admin), avatar, created_at
rss_sources:    id, name, url, category, is_active, last_crawled, created_at
articles:       id, title, content, summary, source_url, rss_source_id,
                keywords(JSON), entities(JSON), published_at, created_at
events:         id, title, summary, category, importance(1-5),
                status(active/resolved), start_date, end_date, created_at
event_articles: event_id, article_id, relevance_score
user_follows:   user_id, event_id, created_at
```

## 事件聚合算法

```
score = keyword_overlap * 0.4 + entity_overlap * 0.35 + title_similarity * 0.25
threshold = 0.25

1. 新文章入库 → 提取关键词 + 实体
2. 与所有 active events 计算 score
3. score >= threshold → 关联到该事件
4. 无匹配 → 创建新事件
5. LLM 生成/更新事件标题和摘要
```

## 分5个阶段构建

### Phase 1: 后端核心 (Backend Core)
- FastAPI 项目初始化 + 配置系统
- SQLAlchemy 模型 + 数据库迁移
- JWT 认证 (注册/登录/鉴权中间件)
- 基础 CRUD API (articles, events, users, rss)
- 启动脚本

### Phase 2: 新闻处理管道 (Processing Pipeline)
- RSS 采集服务 (feedparser, 定时任务)
- 文本处理 (jieba 分词 + TF-IDF 关键词 + NER)
- 事件聚合引擎 (相似度匹配)
- LLM 集成 (智谱 GLM 摘要/标题/分类)
- 后台定时调度

### Phase 3: 前端公共页面 (Public Frontend)
- Vite + React + Tailwind 项目搭建
- 首页时间线 (事件卡片流 + 无限滚动)
- 事件详情页 (纵向时间线 + 文章列表)
- 登录/注册页面
- 用户中心 + 关注管理
- API 集成 + 状态管理

### Phase 4: 管理后台 (Admin Panel)
- 管理员布局 (侧边栏导航)
- 数据概览仪表盘 (统计图表)
- RSS 源管理 (增删改查 + 手动采集)
- 文章管理 (列表/筛选/删除)
- 事件管理 (合并/编辑/删除)

### Phase 5: 打磨集成 (Polish)
- 响应式适配 (移动端)
- 过渡动画 + 加载状态
- 错误处理 + 用户友好提示
- 一键启动脚本
- 全流程测试调试

## 核心页面交互设计

**首页**: 纵向时间线，每个节点是一个事件卡片（标题+摘要+时间+文章数+关注度），点击展开进入详情

**事件详情页**: 左侧纵向时间线（按日期排列的文章节点），右侧事件概要面板（LLM生成的标题/摘要/关键词/趋势）

**管理后台**: 左侧固定侧边栏，右侧数据表格 + 操作按钮

## 预装 RSS 源
- 36氪 (https://36kr.com/feed)
- 虎嗅 (https://www.huxiu.com/rss/0.xml)
- 爱范儿 (https://www.ifanr.com/feed)
- 少数派 (https://sspai.com/feed)
- 知乎日报 (https://daily.zhihu.com/rss)
- IT之家 (https://www.ithome.com/rss/)

## 默认凭证
- 管理员: admin / admin123 (首次启动提示修改)
- APP_SECRET: 首次启动自动生成并持久化
