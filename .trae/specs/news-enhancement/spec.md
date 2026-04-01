# 新闻功能增强规范

## 1. 概述

### 1.1 背景
TimeTrace 新闻追踪系统当前存在以下问题：
- 仅能获取最新 RSS 条目，无法获取历史新闻数据
- 去重仅基于 URL，缺乏内容相似度去重
- 缺乏新闻可信度自动评价机制

### 1.2 目标
实现三个核心功能：
1. **历史新闻获取** - 支持从 RSS 源回溯获取历史新闻
2. **智能去重** - 基于标题和内容相似度的多策略去重
3. **可信度评价** - 自动评估新闻文章的可信度

### 1.3 范围
- 后端服务层实现
- 数据库模型扩展
- API 接口扩展

## 2. 功能设计

### 2.1 历史新闻获取

#### 2.1.1 功能描述
从 RSS 源获取历史新闻数据，支持日期范围过滤和增量更新。

#### 2.1.2 技术方案
```
historical_crawler.py
├── crawl_source()      - 单源历史爬取
├── crawl_all()         - 全量历史爬取
└── crawl_source_full() - 指定源完整爬取
```

#### 2.1.3 配置参数
| 参数 | 默认值 | 说明 |
|------|--------|------|
| MAX_HISTORICAL_DAYS | 30 | 最大回溯天数 |
| MAX_ARTICLES_PER_SOURCE | 500 | 每源最大文章数 |

#### 2.1.4 核心逻辑
1. 解析 RSS feed 获取所有条目
2. 根据 `published_date` 过滤日期范围
3. 检查 URL 是否已存在，避免重复
4. 使用 ETag/Last-Modified 优化增量更新

### 2.2 智能去重

#### 2.2.1 功能描述
基于多策略的文章去重，包括标题相似度和内容相似度。

#### 2.2.2 技术方案
```
deduplication.py
├── find_duplicate_articles()    - 查找重复文章
├── merge_duplicate_articles()   - 合并重复文章
└── deduplicate_all()            - 全量去重
```

#### 2.2.3 去重策略
| 策略 | 阈值 | 说明 |
|------|------|------|
| URL 完全匹配 | 100% | 已在现有爬虫实现 |
| 标题相似度 | 85% | SequenceMatcher |
| 内容相似度 | 70% | Jaccard + 余弦相似度 |

#### 2.2.4 核心算法
```python
def calculate_title_similarity(title1: str, title2: str) -> float:
    return SequenceMatcher(None, title1, title2).ratio()

def calculate_content_similarity(content1: str, content2: str) -> float:
    words1 = set(jieba.cut(content1))
    words2 = set(jieba.cut(content2))
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union) if union else 0.0
```

### 2.3 可信度评价

#### 2.3.1 功能描述
自动评估新闻文章的可信度，生成 0-100 的可信度评分。

#### 2.3.2 技术方案
```
credibility_service.py
├── calculate_source_score()     - 计算来源可信度
├── calculate_content_score()    - 计算内容可信度
├── calculate_cross_ref_score()  - 计算交叉验证分数
├── calculate_credibility()      - 综合可信度计算
└── batch_evaluate()             - 批量评估
```

#### 2.3.3 评分维度
| 维度 | 权重 | 说明 |
|------|------|------|
| 来源可信度 | 30% | RSS 源声誉等级 |
| 内容完整度 | 20% | 标题、正文、作者完整性 |
| 交叉验证 | 30% | 多源报道同一事件 |
| 时效性 | 20% | 新闻发布时间新鲜度 |

#### 2.3.4 来源可信度等级
| 等级 | 分数范围 | 示例来源 |
|------|----------|----------|
| A级 | 90-100 | 官方媒体、权威新闻机构 |
| B级 | 70-89 | 主流媒体、行业媒体 |
| C级 | 50-69 | 自媒体、博客 |
| D级 | 0-49 | 未认证来源、匿名来源 |

## 3. 数据模型扩展

### 3.1 Article 模型扩展
```python
class Article(Base):
    # 现有字段...
    
    # 新增字段
    credibility_score = Column(Float, default=0.0)  # 可信度评分
    credibility_factors = Column(JSON, default={})   # 评分因子详情
    duplicate_of = Column(Integer, ForeignKey('articles.id'))  # 重复文章关联
    is_duplicate = Column(Boolean, default=False)   # 是否为重复文章
```

### 3.2 RssSource 模型扩展
```python
class RssSource(Base):
    # 现有字段...
    
    # 新增字段
    credibility_tier = Column(String(1), default='C')  # 可信度等级 A/B/C/D
    source_reputation = Column(Float, default=50.0)    # 来源声誉分数
```

## 4. API 接口设计

### 4.1 历史爬取接口
```
POST /api/admin/crawl/historical
{
    "source_id": 1,        // 可选，不填则全量
    "days_back": 30        // 回溯天数
}

Response:
{
    "success": true,
    "articles_added": 150,
    "sources_processed": 5
}
```

### 4.2 去重接口
```
POST /api/admin/deduplicate
{
    "dry_run": false,      // 是否仅预览
    "threshold": 0.85      // 相似度阈值
}

Response:
{
    "success": true,
    "duplicates_found": 23,
    "articles_merged": 23
}
```

### 4.3 可信度评估接口
```
POST /api/admin/credibility/evaluate
{
    "article_id": 1,       // 可选，不填则批量
    "force_recalculate": false
}

Response:
{
    "success": true,
    "articles_evaluated": 100,
    "average_score": 72.5
}
```

### 4.4 文章查询增强
```
GET /api/articles?min_credibility=60&deduplicated=true

Response:
{
    "articles": [...],
    "total": 100,
    "filters": {
        "min_credibility": 60,
        "deduplicated": true
    }
}
```

## 5. 实现计划

### 5.1 阶段一：基础服务
1. 实现 `historical_crawler.py`
2. 实现 `deduplication.py`
3. 实现 `credibility_service.py`

### 5.2 阶段二：模型扩展
1. 添加 Article 新字段
2. 添加 RssSource 新字段
3. 数据库迁移

### 5.3 阶段三：API 集成
1. 添加管理接口路由
2. 更新文章查询接口
3. 添加定时任务

## 6. 非功能性需求

### 6.1 性能要求
- 历史爬取：支持并发处理多个 RSS 源
- 去重：批量处理 1000 篇文章 < 30秒
- 可信度评估：单篇 < 100ms

### 6.2 可靠性要求
- 爬取失败自动重试（最多3次）
- 去重操作支持事务回滚
- 可信度评估异常不影响文章存储

### 6.3 可维护性要求
- 完善的日志记录
- 配置参数可调整
- 支持干运行（dry-run）模式

## 7. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| RSS 源不稳定 | 历史数据不完整 | 多源备份、失败重试 |
| 去重误判 | 丢失有效文章 | 高阈值设置、人工审核 |
| 可信度偏差 | 评分不准确 | 多维度综合、持续优化权重 |
