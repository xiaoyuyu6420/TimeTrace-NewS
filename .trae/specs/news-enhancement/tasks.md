# 新闻功能增强任务列表

## 阶段一：基础服务实现

### 1.1 历史新闻获取服务
- [ ] 创建 `backend/app/services/historical_crawler.py`
- [ ] 实现 `crawl_source()` 单源历史爬取函数
- [ ] 实现 `crawl_all()` 全量历史爬取函数
- [ ] 实现 `crawl_source_full()` 指定源完整爬取函数
- [ ] 添加日期范围过滤逻辑
- [ ] 添加 ETag/Last-Modified 增量更新支持
- [ ] 添加错误处理和重试机制

### 1.2 智能去重服务
- [ ] 创建 `backend/app/services/deduplication.py`
- [ ] 实现 `calculate_title_similarity()` 标题相似度计算
- [ ] 实现 `calculate_content_similarity()` 内容相似度计算
- [ ] 实现 `find_duplicate_articles()` 查找重复文章
- [ ] 实现 `merge_duplicate_articles()` 合并重复文章
- [ ] 实现 `deduplicate_all()` 全量去重函数
- [ ] 添加 dry-run 模式支持

### 1.3 可信度评价服务
- [ ] 创建 `backend/app/services/credibility_service.py`
- [ ] 实现 `calculate_source_score()` 来源可信度计算
- [ ] 实现 `calculate_content_score()` 内容完整度计算
- [ ] 实现 `calculate_cross_ref_score()` 交叉验证计算
- [ ] 实现 `calculate_timeliness_score()` 时效性计算
- [ ] 实现 `calculate_credibility()` 综合可信度计算
- [ ] 实现 `batch_evaluate()` 批量评估函数

## 阶段二：数据模型扩展

### 2.1 Article 模型更新
- [ ] 添加 `credibility_score` 字段 (Float)
- [ ] 添加 `credibility_factors` 字段 (JSON)
- [ ] 添加 `duplicate_of` 字段 (ForeignKey)
- [ ] 添加 `is_duplicate` 字段 (Boolean)

### 2.2 RssSource 模型更新
- [ ] 添加 `credibility_tier` 字段 (String)
- [ ] 添加 `source_reputation` 字段 (Float)

### 2.3 数据库迁移
- [ ] 创建 Alembic 迁移脚本
- [ ] 执行数据库迁移
- [ ] 验证迁移结果

## 阶段三：API 接口实现

### 3.1 管理接口
- [ ] 创建 `backend/app/api/admin.py` 路由模块
- [ ] 实现 `POST /api/admin/crawl/historical` 历史爬取接口
- [ ] 实现 `POST /api/admin/deduplicate` 去重接口
- [ ] 实现 `POST /api/admin/credibility/evaluate` 可信度评估接口
- [ ] 实现 `GET /api/admin/credibility/stats` 可信度统计接口

### 3.2 文章查询增强
- [ ] 更新 `GET /api/articles` 支持 `min_credibility` 参数
- [ ] 更新 `GET /api/articles` 支持 `deduplicated` 参数
- [ ] 添加可信度评分到文章响应

### 3.3 路由注册
- [ ] 在 `main.py` 注册管理路由
- [ ] 更新 CORS 配置（如需要）

## 阶段四：集成与测试

### 4.1 服务集成
- [ ] 更新爬虫服务调用历史爬取
- [ ] 更新聚合服务集成去重逻辑
- [ ] 更新文章保存时自动评估可信度

### 4.2 定时任务
- [ ] 添加定时历史爬取任务
- [ ] 添加定时去重任务
- [ ] 添加定时可信度重算任务

### 4.3 测试验证
- [ ] 测试历史爬取功能
- [ ] 测试去重功能
- [ ] 测试可信度评估功能
- [ ] 测试 API 接口

## 任务依赖关系

```
阶段一 (基础服务)
    ├── 1.1 历史爬取 ──┐
    ├── 1.2 去重服务 ──┼──► 阶段二 (模型扩展) ──► 阶段三 (API) ──► 阶段四 (集成测试)
    └── 1.3 可信度 ───┘
```

## 优先级说明

| 优先级 | 任务 | 原因 |
|--------|------|------|
| P0 | 历史爬取、去重、可信度服务 | 核心功能，其他依赖此 |
| P0 | 模型扩展 | 服务实现需要字段支持 |
| P1 | API 接口 | 用户交互入口 |
| P2 | 定时任务 | 自动化运维 |
