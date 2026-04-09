# TimeTrace 重构方案 — 事件生命周期时间线

## 核心理念

**不是新闻阅读器，是事件情报平台。**

用户看到的不是"最新新闻列表"，而是"这件事的起因、经过、结果"。

关键：**后端做好数据处理，前端展示精炼信息。**

---

## 一、产品定义

### 用户视角
- 打开首页 → 看到正在进行的重要事件，按时间排列
- 点击事件 → 看到"起因 → 经过 → 结果"的完整故事线
- 不关心数据从哪来，只关心事件本身
- 搜索 → 找到相关事件

### 数据流
```
多源采集 → 去重 → 可信度评估 → 聚合为事件 → 阶段标注 → LLM精炼摘要
                                                                    ↓
                                                             前端展示时间线
```

---

## 二、后端算法设计

### 2.1 核心问题

传统聚合只做"相似文章归为一类"。我们需要做的是：
1. **匹配**: 新文章关联到已有事件
2. **阶段标注**: 这篇文章在事件中是什么角色（起因/发展/结果）
3. **精炼**: 定期用 LLM 生成事件叙述

### 2.2 算法流水线

```
每篇新文章进入系统:
    │
    ├─ Stage 1: 特征提取（无 LLM，纯计算）
    │   ├─ jieba 关键词 + 命名实体
    │   └─ embedding 向量（Zhipu embedding API，成本极低）
    │
    ├─ Stage 2: 匹配已有事件（无 LLM，向量+关键词）
    │   ├─ cosine similarity > 0.55 → 自动关联
    │   ├─ cosine 0.40~0.55 且 keyword overlap > 0.3 → 自动关联
    │   ├─ cosine 0.30~0.40 → 【调用 LLM 验证】(约10%的边界case)
    │   └─ < 0.30 → 创建新事件，phase="trigger"
    │
    ├─ Stage 3: 阶段标注（规则驱动，无 LLM）
    │   ├─ 事件首批1-2篇 → "trigger"(起因)
    │   ├─ 包含结果关键词(宣布/决定/通过/判决/达成/...) → "outcome"(结果)
    │   ├─ 已关闭事件重新激活 → "followup"(后续)
    │   └─ 其他 → "development"(发展)
    │
    └─ Stage 4: 事件精炼（选择性 LLM，严格控制频率）
        ├─ 触发条件（满足任一）:
        │   a. 事件新增 ≥5 篇文章
        │   b. 事件首次出现 outcome 阶段
        │   c. 事件创建 ≥24 小时且有 ≥3 篇文章
        │
        └─ LLM 调用内容:
            ├─ 重新生成事件标题（取最简洁的概括）
            └─ 生成3-5句叙述性摘要（起因+经过+结果）
```

### 2.3 成本控制策略

| 环节 | 每篇文章成本 | 频率 |
|------|------------|------|
| 关键词/实体提取 | 0（jieba 本地） | 100% |
| Embedding 生成 | ~¥0.001 | 100% |
| 相似度计算 | 0（余弦，纯计算） | 100% |
| 阶段标注 | 0（规则引擎） | 100% |
| LLM 验证匹配 | ~¥0.01 | ~10%（边界case） |
| LLM 生成摘要 | ~¥0.02 | ~5%（批量时触发） |

**结论**: 100篇文章约 ¥0.3-0.5，成本可控。

### 2.4 阶段标注规则详解

```python
# 结果关键词库（命中即判定为 outcome）
OUTCOME_KEYWORDS = {
    # 决策类
    "宣布", "决定", "通过", "批准", "签署", "发布", "出台",
    # 终结类
    "结果", "判决", "裁定", "闭幕", "落幕", "终止", "结束",
    # 达成类
    "达成", "共识", "协议", "和解", "妥协",
    # 状态变化
    "破案", "获救", "脱险", "遇难", "去世", "身亡",
    # 定论类
    "最终", "定论", "证实", "确认", "澄清",
}

# 后续发展关键词（已关闭事件重新激活时）
FOLLOWUP_KEYWORDS = {
    "后续", "最新进展", "新进展", "回应", "反转", "更新",
}

def determine_phase(event, article, existing_articles_count):
    title = article.title or ""

    # 已关闭事件的后续报道
    if event.status == "resolved":
        return "followup"

    # 结果关键词检测
    if any(kw in title for kw in OUTCOME_KEYWORDS):
        return "outcome"

    # 事件初期 = 起因
    if existing_articles_count <= 1:
        return "trigger"

    # 默认 = 发展
    return "development"
```

---

## 三、数据模型变更

### 3.1 新增字段

```python
# models.py 变更

# EventArticle 增加 phase 字段
class EventArticle(Base):
    # ...existing fields...
    phase = Column(String(20), default="development")
    # 值: "trigger" | "development" | "outcome" | "followup"

# Event 增加精炼追踪字段
class Event(Base):
    # ...existing fields...
    last_enhanced_at = Column(DateTime, nullable=True)
    # 记录上次 LLM 精炼时间，控制调用频率
```

### 3.2 迁移 SQL

```sql
ALTER TABLE event_articles ADD COLUMN phase TEXT DEFAULT 'development';
ALTER TABLE events ADD COLUMN last_enhanced_at DATETIME;
```

### 3.3 回填策略

对已有数据：
- 每个事件最早的文章 → phase = "trigger"
- 其余 → phase = "development"

---

## 四、API 设计

### 4.1 事件列表（增强）

```
GET /api/events/public
  ?time_range=today|week|month|all    # 新增：时间范围
  &category=科技|财经|...              # 已有：分类过滤
  &status=active|resolved|all          # 已有：状态过滤
  &page=1&page_size=20
```

### 4.2 事件详情（重构为 timeline 结构）

```
GET /api/events/{id}/public

Response:
{
  "id": 1,
  "title": "全球AI安全峰会在日内瓦召开",
  "summary": "2026年3月，多国领导人就AI安全监管达成共识...",
  "category": "科技",
  "importance": 4,
  "status": "active",
  "start_date": "2026-03-28",
  "end_date": null,
  "timeline": [
    {
      "phase": "trigger",
      "phase_label": "起因",
      "date": "2026-03-28",
      "articles": [
        {
          "id": 101,
          "title": "联合国宣布将在日内瓦举办AI安全峰会",
          "published_at": "2026-03-28T09:00:00Z",
          "source_name": "新华社",
          "credibility_score": 85.0
        }
      ]
    },
    {
      "phase": "development",
      "phase_label": "经过",
      "date": "2026-03-29",
      "articles": [
        {"id": 102, "title": "美欧就AI监管框架出现分歧", ...},
        {"id": 103, "title": "中方提出AI治理三原则", ...}
      ]
    },
    {
      "phase": "outcome",
      "phase_label": "结果",
      "date": "2026-03-30",
      "articles": [
        {"id": 104, "title": "峰会达成AI安全联合声明", ...}
      ]
    }
  ]
}
```

### 4.3 新增端点

```
GET /api/events/categories
Response: [{"name": "科技", "count": 15}, {"name": "财经", "count": 8}]
```

### 4.4 删除的端点

```
DELETE: /api/articles/people-daily/*       (全部6个)
DELETE: /api/admin/people/*                (全部2个)
```

---

## 五、前端架构

### 5.1 页面

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | Home | 事件时间线（按时间分组） |
| `/event/:id` | EventDetail | 事件详情（起因→经过→结果） |
| `/search` | Search | 搜索结果页（新增） |
| `/login` | Login | 登录 |
| `/register` | Register | 注册 |
| `/profile` | Profile | 个人中心 |
| `/admin/*` | Admin* | 管理后台（不变） |

### 5.2 新增组件

```
components/
├── Layout.tsx              # 重构：顶部导航 + 内嵌搜索栏
├── Navbar.tsx              # 新建：Logo + SearchBar + Auth
├── SearchBar.tsx           # 新建：全局搜索输入框
├── TimelineSection.tsx     # 新建：时间分组区块（今天/昨天/本周/更早）
├── TimelineEventCard.tsx   # 新建：时间线样式的事件卡片
├── EventHero.tsx           # 新建：事件详情页顶部 Hero 区域
├── ArticleTimeline.tsx     # 新建：文章时间线（按阶段分组）
├── ArticleTimelineItem.tsx # 新建：单篇文章时间线节点
├── CategoryBadge.tsx       # 新建：分类标签
├── StatusBadge.tsx         # 新建：状态标签（进行中/已完结）
├── FollowButton.tsx        # 新建：关注/取消关注按钮
├── EmptyState.tsx          # 新建：空状态占位
├── LoadingSkeleton.tsx     # 新建：骨架屏加载
└── Pagination.tsx          # 新建：分页控件
```

### 5.3 删除的组件

- `PeopleDailyArticle.tsx` → 删除
- `PeopleEvents.tsx` → 删除
- `PeopleTimeline.tsx` → 删除
- `EventCard.tsx` → 被 TimelineEventCard 替代
- `Timeline.tsx` → 被 ArticleTimeline 替代

### 5.4 首页布局

```
┌──────────────────────────────────────┐
│  事件时间线                           │
│  [今天] [本周] [本月] [全部]  [分类 ▼] │
├──────────────────────────────────────┤
│  ── 今天 · 3个事件 ───────────────── │
│  ┃🔴头条 科技 · 3小时前               │
│  ┃ AI安全峰会召开                     │
│  ┃ 多国领导人达成共识...              │
│  ┃ 12篇报道 · 86人关注               │
│  ┃                                   │
│  ┃ 科技 · 5小时前                     │
│  ┃ 特斯拉发布新自动驾驶系统            │
│  ┃ 8篇报道                           │
├──────────────────────────────────────┤
│  ── 昨天 · 5个事件 ───────────────── │
│  ┃ ...                               │
└──────────────────────────────────────┘
```

左侧彩色竖条表示重要程度：红=头条(5), 橙=热点(4), 青=重要(3), 灰=普通(1-2)

### 5.5 事件详情布局

```
┌──────────────────────────────────────────┐
│  [科技] [进行中 ●]                        │
│  AI安全峰会在日内瓦召开                    │
│  3月28日，联合国宣布...（摘要）             │
│  3/28~3/30 · 12篇 · 86关注  [关注]        │
├──────────────────────┬───────────────────┤
│  起因 (3/28)          │  事件信息          │
│  ● 联合国宣布...       │  重要度 ████░      │
│  │                    │  分类 科技          │
│  经过 (3/29)          │  状态 进行中        │
│  ● 美欧出现分歧       │                    │
│  │ ● 中方提三原则     │  相关事件          │
│  │                    │  · 欧盟AI法案      │
│  结果 (3/30)          │  · 芯片出口管制     │
│  ● 达成联合声明       │                    │
└──────────────────────┴───────────────────┘
```

---

## 六、实施阶段

### Phase 1: 清理（删除人民网代码）
1. 删除前端: `PeopleDailyArticle.tsx`, `PeopleEvents.tsx`, `PeopleTimeline.tsx`
2. 清理 `App.tsx` 路由
3. 清理 `Home.tsx` 中的人民网状态和渲染
4. 删除后端 `articles.py` 中 people-daily 端点
5. 删除后端 `admin.py` 中 people 端点
6. 删除 `crawl_people_daily.py`
7. 更新 `CLAUDE.md`

### Phase 2: 后端数据模型
1. `models.py`: EventArticle 添加 `phase`，Event 添加 `last_enhanced_at`
2. `main.py`: 添加迁移 SQL
3. 回填已有数据

### Phase 3: 后端算法
1. 重写 `services/aggregate.py`：阶段标注逻辑
2. 新建 `services/timeline.py`：时间线构建 + 阶段检测 + LLM精炼触发
3. `deps.py`: 添加 `get_timeline_service` 工厂

### Phase 4: 后端 API
1. `schemas.py`: 增加 timeline 相关 schema
2. `routes/events.py`: 增强（time_range参数、timeline结构响应、categories端点）
3. `routes/articles.py`: 清理 people-daily 端点

### Phase 5: 前端基础设施
1. 新建 `types.ts` 类型定义
2. 更新 `index.css` 扩展调色板
3. 新建 `api/events.ts` + `api/users.ts` 封装
4. 重构 `Layout.tsx` 导航栏（内嵌搜索）

### Phase 6: 前端核心页面
1. 新建 `TimelineEventCard.tsx` + `TimelineSection.tsx`
2. 重写 `Home.tsx` 为时间线布局
3. 新建 `EventHero.tsx` + `ArticleTimelineItem.tsx`
4. 重写 `EventDetail.tsx` 双栏布局
5. 新建 `LoadingSkeleton.tsx`, `EmptyState.tsx`

### Phase 7: 搜索 + 验证
1. 新建 `Search.tsx` 页面
2. 全流程测试
3. 移动端响应式验证
