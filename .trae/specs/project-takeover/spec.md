# 项目接管规范 (TimeTrace 新闻事件追踪系统)

## Why

需要全面接管并理解 TimeTrace 项目，这是一个中文新闻事件追踪系统，包含新闻采集、事件聚合、AI 摘要生成等核心功能。现有代码库已具备基础架构，但需要完整记录系统状态以便后续维护和开发。

## What Changes

本规范是项目接管的全面文档，记录系统的技术栈、架构设计、数据库结构、API 接口和核心算法，作为后续开发的基础参考。

## Impact

- 完整记录 TimeTrace 项目的技术架构
- 明确系统各组件的职责和边界
- 建立项目维护和扩展的基础文档

## 系统概述

TimeTrace 是一个新闻事件追踪系统，通过 RSS 源采集新闻，使用 NLP 技术（jieba 分词、TF-IDF）进行文本处理，通过相似度算法聚合相关报道，并利用 LLM（智谱 GLM-4-Flash）生成事件摘要和标题。

## 技术栈

| 层级 | 技术 | 版本/备注 |
|------|------|-----------|
| 后端框架 | FastAPI + SQLAlchemy | 异步支持，Python 3.13 |
| 数据库 | SQLite | 轻量级，文件数据库 |
| NLP | jieba + scikit-learn | 中文分词 + TF-IDF |
| LLM | 智谱 GLM-4-Flash | 免费额度充足 |
| 前端 | React 19 + TypeScript | Vite 构建 |
| 样式 | Tailwind CSS 4 | 最新版本 |
| 状态管理 | Zustand | 轻量持久化 |
| 认证 | JWT Bearer Token | 标准方案 |

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
│   │   │   ├── admin.py         # 管理后台统计
│   │   │   ├── articles.py      # 文章 CRUD
│   │   │   ├── events.py        # 事件 CRUD + 时间线
│   │   │   ├── rss.py           # RSS 源管理
│   │   │   └── users.py         # 注册/登录/关注
│   │   └── services/
│   │       ├── aggregator.py    # 事件聚合 (相似度匹配)
│   │       ├── crawler.py       # RSS 采集 (feedparser)
│   │       ├── llm_service.py   # LLM 调用 (智谱 GLM)
│   │       └── processor.py     # 文本处理 (jieba + TF-IDF)
│   ├── requirements.txt
│   ├── run.py
│   └── timetrace.db             # SQLite 数据库文件
├── web/
│   ├── src/
│   │   ├── App.tsx              # 主应用组件
│   │   ├── main.tsx             # 入口文件
│   │   ├── api/client.ts        # Axios 实例 + 拦截器
│   │   ├── stores/auth.ts       # Zustand auth store
│   │   ├── components/
│   │   │   ├── AdminLayout.tsx  # 管理后台布局
│   │   │   ├── EventCard.tsx    # 事件卡片组件
│   │   │   ├── Layout.tsx       # 公共布局（导航栏+侧边栏）
│   │   │   └── Timeline.tsx     # 时间线核心组件
│   │   └── pages/
│   │       ├── Home.tsx         # 首页 - 事件时间线流
│   │       ├── EventDetail.tsx  # 事件详情 - 完整时间线
│   │       ├── Login.tsx        # 登录页
│   │       ├── Profile.tsx      # 个人中心 + 关注列表
│   │       ├── Register.tsx     # 注册页
│   │       └── admin/
│   │           ├── Articles.tsx # 文章管理
│   │           ├── Dashboard.tsx # 数据概览
│   │           ├── EventManage.tsx # 事件管理
│   │           ├── Events.tsx   # 事件列表
│   │           └── Sources.tsx   # RSS 源管理
│   ├── package.json
│   └── vite.config.ts
├── .gitignore
├── PLAN.md                      # 实施计划文档
├── start-all.bat                # Windows 一键启动
└── start-all.sh                 # Unix 一键启动
```

## 数据库设计

### users 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| username | String(50) | 用户名，唯一 |
| email | String(100) | 邮箱，唯一 |
| password_hash | String(255) | 密码哈希 |
| role | String(20) | user/admin |
| avatar | String(255) | 头像 URL |
| created_at | DateTime | 创建时间 |

### rss_sources 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| name | String(100) | 源名称 |
| url | String(500) | RSS URL |
| category | String(50) | 分类 |
| is_active | Boolean | 是否激活 |
| last_crawled | DateTime | 最后采集时间 |
| created_at | DateTime | 创建时间 |

### articles 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| title | String(500) | 标题 |
| content | Text | 内容 |
| summary | Text | AI 摘要 |
| source_url | String(500) | 原始链接 |
| rss_source_id | Integer | 外键 |
| keywords | JSON | 关键词列表 |
| entities | JSON | 实体列表 |
| published_at | DateTime | 发布时间 |
| created_at | DateTime | 创建时间 |

### events 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| title | String(200) | 事件标题（AI生成） |
| summary | Text | 事件摘要（AI生成） |
| category | String(50) | 分类 |
| importance | Integer | 重要性 1-5 |
| status | String(20) | active/resolved |
| start_date | Date | 开始日期 |
| end_date | Date | 结束日期 |
| created_at | DateTime | 创建时间 |

### event_articles 表（关联表）
| 字段 | 类型 | 说明 |
|------|------|------|
| event_id | Integer | 外键 |
| article_id | Integer | 外键 |
| relevance_score | Float | 关联度分数 |

### user_follows 表（关注表）
| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | Integer | 外键 |
| event_id | Integer | 外键 |
| created_at | DateTime | 关注时间 |

## 事件聚合算法

```
评分公式: score = keyword_overlap * 0.4 + entity_overlap * 0.35 + title_similarity * 0.25
阈值: threshold = 0.25

处理流程:
1. 新文章入库 → 提取关键词 + 实体
2. 与所有 active events 计算 score
3. score >= threshold → 关联到该事件
4. 无匹配 → 创建新事件
5. LLM 生成/更新事件标题和摘要
```

## API 接口概览

### 认证相关 (users.py)
- `POST /api/users/register` - 用户注册
- `POST /api/users/login` - 用户登录
- `GET /api/users/me` - 获取当前用户
- `POST /api/users/{user_id}/follow/{event_id}` - 关注事件
- `DELETE /api/users/{user_id}/unfollow/{event_id}` - 取消关注

### 文章相关 (articles.py)
- `GET /api/articles` - 获取文章列表
- `GET /api/articles/{id}` - 获取文章详情

### 事件相关 (events.py)
- `GET /api/events` - 获取事件列表
- `GET /api/events/{id}` - 获取事件详情
- `GET /api/events/{id}/timeline` - 获取事件时间线

### RSS 源管理 (rss.py)
- `GET /api/rss/sources` - 获取 RSS 源列表
- `POST /api/rss/sources` - 添加 RSS 源
- `PUT /api/rss/sources/{id}` - 更新 RSS 源
- `DELETE /api/rss/sources/{id}` - 删除 RSS 源
- `POST /api/rss/sources/{id}/crawl` - 手动触发采集

### 管理后台 (admin.py)
- `GET /api/admin/stats` - 获取统计数据
- `GET /api/admin/articles` - 管理文章列表
- `DELETE /api/admin/articles/{id}` - 删除文章
- `GET /api/admin/events` - 管理事件列表
- `PUT /api/admin/events/{id}` - 更新事件
- `DELETE /api/admin/events/{id}` - 删除事件
- `POST /api/admin/events/merge` - 合并事件

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

## 前端路由

| 路径 | 组件 | 说明 |
|------|------|------|
| / | Home | 首页，事件时间线流 |
| /event/:id | EventDetail | 事件详情页 |
| /login | Login | 登录页 |
| /register | Register | 注册页 |
| /profile | Profile | 个人中心 |
| /admin | Dashboard | 管理后台首页 |
| /admin/sources | Sources | RSS 源管理 |
| /admin/articles | Articles | 文章管理 |
| /admin/events | Events | 事件列表 |
| /admin/event-manage | EventManage | 事件管理 |

## 核心组件说明

### Timeline.tsx
时间线核心组件，用于展示事件的纵向时间线视图。

### EventCard.tsx
事件卡片组件，显示事件标题、摘要、时间、文章数、关注度等信息。

### Layout.tsx
公共布局组件，包含导航栏和侧边栏。

### AdminLayout.tsx
管理后台专用布局，包含管理员侧边栏导航。

## 环境配置

### 后端环境变量 (.env)
需要配置智谱 GLM API 密钥和其他环境变量。

### 前端配置 (vite.config.ts)
配置代理将 /api 请求转发到后端服务器。

## 项目状态

项目已实现基础功能，包括：
- ✅ 后端核心 (FastAPI + JWT 认证)
- ✅ 数据库模型和 CRUD API
- ✅ RSS 采集服务
- ✅ 文本处理服务 (jieba + TF-IDF)
- ✅ 事件聚合引擎
- ✅ LLM 集成 (智谱 GLM)
- ✅ 前端公共页面 (首页、详情、登录注册)
- ✅ 管理后台页面

待完善：
- 响应式适配（移动端）
- 过渡动画和加载状态
- 错误处理优化
