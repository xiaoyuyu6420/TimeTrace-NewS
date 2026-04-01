# 新闻功能增强验证清单

## 1. 历史新闻获取服务

### 1.1 文件结构
- [ ] `backend/app/services/historical_crawler.py` 文件存在
- [ ] 包含必要的导入语句
- [ ] 定义了配置常量

### 1.2 函数实现
- [ ] `crawl_source()` 函数实现正确
- [ ] `crawl_all()` 函数实现正确
- [ ] `crawl_source_full()` 函数实现正确

### 1.3 功能验证
- [ ] 支持日期范围过滤
- [ ] 支持 ETag/Last-Modified 增量更新
- [ ] 支持最大文章数限制
- [ ] 错误处理完善
- [ ] 日志记录完整

### 1.4 测试用例
- [ ] 测试单源历史爬取
- [ ] 测试全量历史爬取
- [ ] 测试日期过滤功能
- [ ] 测试增量更新功能
- [ ] 测试错误重试机制

---

## 2. 智能去重服务

### 2.1 文件结构
- [ ] `backend/app/services/deduplication.py` 文件存在
- [ ] 包含必要的导入语句
- [ ] 定义了相似度阈值常量

### 2.2 函数实现
- [ ] `calculate_title_similarity()` 函数实现正确
- [ ] `calculate_content_similarity()` 函数实现正确
- [ ] `find_duplicate_articles()` 函数实现正确
- [ ] `merge_duplicate_articles()` 函数实现正确
- [ ] `deduplicate_all()` 函数实现正确

### 2.3 功能验证
- [ ] 标题相似度计算准确
- [ ] 内容相似度计算准确
- [ ] 支持批量去重
- [ ] 支持 dry-run 模式
- [ ] 事务处理正确

### 2.4 测试用例
- [ ] 测试标题相似度计算
- [ ] 测试内容相似度计算
- [ ] 测试重复文章查找
- [ ] 测试文章合并功能
- [ ] 测试全量去重功能

---

## 3. 可信度评价服务

### 3.1 文件结构
- [ ] `backend/app/services/credibility_service.py` 文件存在
- [ ] 包含必要的导入语句
- [ ] 定义了评分权重常量

### 3.2 函数实现
- [ ] `calculate_source_score()` 函数实现正确
- [ ] `calculate_content_score()` 函数实现正确
- [ ] `calculate_cross_ref_score()` 函数实现正确
- [ ] `calculate_timeliness_score()` 函数实现正确
- [ ] `calculate_credibility()` 函数实现正确
- [ ] `batch_evaluate()` 函数实现正确

### 3.3 功能验证
- [ ] 来源可信度计算正确
- [ ] 内容完整度计算正确
- [ ] 交叉验证计算正确
- [ ] 时效性计算正确
- [ ] 综合评分权重正确
- [ ] 评分范围在 0-100

### 3.4 测试用例
- [ ] 测试来源可信度计算
- [ ] 测试内容完整度计算
- [ ] 测试交叉验证计算
- [ ] 测试时效性计算
- [ ] 测试综合可信度计算
- [ ] 测试批量评估功能

---

## 4. 数据模型扩展

### 4.1 Article 模型
- [ ] `credibility_score` 字段已添加 (Float, default=0.0)
- [ ] `credibility_factors` 字段已添加 (JSON, default={})
- [ ] `duplicate_of` 字段已添加 (ForeignKey)
- [ ] `is_duplicate` 字段已添加 (Boolean, default=False)

### 4.2 RssSource 模型
- [ ] `credibility_tier` 字段已添加 (String(1), default='C')
- [ ] `source_reputation` 字段已添加 (Float, default=50.0)

### 4.3 数据库迁移
- [ ] Alembic 迁移脚本已创建
- [ ] 迁移已成功执行
- [ ] 数据库字段已验证

---

## 5. API 接口

### 5.1 管理接口
- [ ] `POST /api/admin/crawl/historical` 接口可用
- [ ] `POST /api/admin/deduplicate` 接口可用
- [ ] `POST /api/admin/credibility/evaluate` 接口可用
- [ ] `GET /api/admin/credibility/stats` 接口可用

### 5.2 接口功能
- [ ] 历史爬取接口返回正确响应
- [ ] 去重接口返回正确响应
- [ ] 可信度评估接口返回正确响应
- [ ] 统计接口返回正确响应

### 5.3 文章查询增强
- [ ] `min_credibility` 参数生效
- [ ] `deduplicated` 参数生效
- [ ] 文章响应包含可信度评分

### 5.4 路由注册
- [ ] 管理路由已注册到 main.py
- [ ] 路由前缀正确

---

## 6. 集成测试

### 6.1 服务集成
- [ ] 爬虫服务正确调用历史爬取
- [ ] 聚合服务正确集成去重逻辑
- [ ] 文章保存时自动评估可信度

### 6.2 端到端测试
- [ ] 完整流程测试通过
- [ ] 数据一致性验证通过
- [ ] 性能满足要求

### 6.3 错误处理
- [ ] 异常情况正确处理
- [ ] 错误日志记录完整
- [ ] 用户友好错误提示

---

## 7. 文档与配置

### 7.1 代码文档
- [ ] 函数文档字符串完整
- [ ] 类型注解完整
- [ ] 复杂逻辑有注释

### 7.2 配置文件
- [ ] 配置参数可调整
- [ ] 默认值合理
- [ ] 配置文档完整

---

## 验证结果汇总

| 模块 | 检查项数 | 通过数 | 通过率 |
|------|----------|--------|--------|
| 历史爬取 | 15 | - | - |
| 智能去重 | 15 | - | - |
| 可信度评价 | 18 | - | - |
| 数据模型 | 8 | - | - |
| API 接口 | 11 | - | - |
| 集成测试 | 8 | - | - |
| 文档配置 | 6 | - | - |
| **总计** | **81** | - | - |

---

## 验证日期

- 规范创建日期：2026-04-01
- 最后验证日期：_待填写_
- 验证人员：_待填写_
