# 历史新闻获取方案

## 设计决策

**专注单一数据源：人民网**

理由：
1. 数据质量可控 - 官方权威媒体，内容规范
2. 维护成本低 - 无需适配多个网站
3. 数据干净 - 结构化好，易于清洗
4. 覆盖面广 - 多频道（新闻、时政、社会、科技、财经、国际）

## 人民网爬虫实现

### 文件位置
`backend/app/services/people_crawler.py`

### 支持的频道
| 频道代码 | 名称 | 说明 |
|----------|------|------|
| news | 新闻 | 综合新闻 |
| politics | 时政 | 政治新闻 |
| society | 社会 | 社会新闻 |
| tech | 科技 | 科技新闻 |
| finance | 财经 | 财经新闻 |
| world | 国际 | 国际新闻 |

### 数据清洗
- 标题：去除网站后缀（人民网、人民网点等）
- 内容：去除多余空白、HTML标签、脚本
- 日期：多格式解析，支持URL提取日期
- 作者：提取编辑/记者信息

### API 接口

**获取历史新闻**
```
POST /api/admin/people/fetch
{
    "years": 2,           // 获取最近2年
    "max_articles": 10000, // 最大文章数
    "channels": ["news", "tech"]  // 可选，不填则全部
}
```

**查看可用频道**
```
GET /api/admin/people/channels
```

## 使用示例

```python
from app.services.people_crawler import PeopleCnCrawler

# 创建爬虫
crawler = PeopleCnCrawler(
    max_articles=10000,
    request_delay=1.0,
)

# 获取最近2年的新闻
articles = crawler.fetch_years(years=2)

# 获取指定频道
articles = crawler.fetch_years(
    years=2,
    channels=["news", "tech"]
)

# 保存到数据库
from app.database import SessionLocal
db = SessionLocal()
saved = crawler.save_to_database(articles, db)
```

## 性能参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| max_articles | 10000 | 最大文章数 |
| max_pages_per_channel | 100 | 每频道最大页数 |
| request_delay | 1.0秒 | 请求间隔 |
| timeout | 30秒 | 请求超时 |
| max_retries | 3 | 最大重试次数 |

## 注意事项

1. **遵守 robots.txt**：人民网允许爬取
2. **请求频率**：默认1秒间隔，避免被封
3. **数据量**：2年约 10-20 万篇文章
4. **编码**：人民网使用 GB2312 编码
