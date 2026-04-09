"""
历史新闻获取脚本。

使用方法:
    cd backend
    python scripts/fetch_history.py

支持的数据源:
    1. RSSHub 深度爬取（支持分页的路由）
    2. 手动导入 JSON/CSV 文件
    3. Bing News Search API（需要 API key）

获取到的数据通过 /admin/import-articles 接口导入系统。
"""

import json
import sys
import os
import argparse
from datetime import datetime, timedelta, timezone

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests
from app.database import SessionLocal
from app.models import RssSource
from app.deps import hash_password


def fetch_via_rsshub(source_name: str, route: str, pages: int = 5) -> list[dict]:
    """通过 RSSHub 爬取多页数据。"""
    articles = []
    base = "https://rsshub.app"

    for page in range(1, pages + 1):
        url = f"{base}/{route}" if page == 1 else f"{base}/{route}/{page}"
        try:
            import feedparser
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = getattr(entry, "title", "").strip()
                if not title:
                    continue
                content = ""
                if hasattr(entry, "summary"):
                    content = entry.summary
                if hasattr(entry, "content") and entry.content:
                    content = entry.content[0].get("value", content) or content

                published = None
                for attr in ("published_parsed", "updated_parsed"):
                    val = getattr(entry, attr, None)
                    if val:
                        try:
                            from time import mktime
                            dt = datetime.fromtimestamp(mktime(val), tz=timezone.utc)
                            published = dt.isoformat()
                        except Exception:
                            pass
                        break

                articles.append({
                    "title": title,
                    "content": content[:3000],
                    "source_url": getattr(entry, "link", ""),
                    "published_at": published,
                    "source_name": source_name,
                })
            print(f"  {source_name} page {page}: {len(feed.entries)} entries")
            if len(feed.entries) == 0:
                break
        except Exception as e:
            print(f"  {source_name} page {page} error: {e}")
            break

    return articles


def import_to_api(articles: list[dict], base_url: str = "http://localhost:8000", token: str = ""):
    """通过 API 批量导入文章。"""
    if not articles:
        print("No articles to import")
        return

    # 分批导入（每批100条）
    batch_size = 100
    total_imported = 0
    total_skipped = 0

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        try:
            resp = requests.post(
                f"{base_url}/api/admin/import-articles",
                json={"articles": batch},
                headers=headers,
                timeout=60,
            )
            if resp.status_code == 200:
                data = resp.json()
                total_imported += data.get("imported", 0)
                total_skipped += data.get("skipped", 0)
                print(f"  Batch {i // batch_size + 1}: imported={data.get('imported')}, skipped={data.get('skipped')}")
            else:
                print(f"  Batch {i // batch_size + 1} error: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            print(f"  Batch {i // batch_size + 1} error: {e}")

    print(f"\nTotal: imported={total_imported}, skipped={total_skipped}")


def login(base_url: str = "http://localhost:8000") -> str:
    """登录获取 token。"""
    resp = requests.post(f"{base_url}/api/users/login", json={
        "username": "admin",
        "password": "admin123",
    })
    if resp.status_code == 200:
        return resp.json()["access_token"]
    print(f"Login failed: {resp.status_code}")
    sys.exit(1)


# ─── RSSHub 深度路由配置 ───
# 格式: (源名称, RSSHub路由, 爬取页数)
RSSHUB_ROUTES = [
    # 新华网 — 多个栏目
    ("新华网", "xinhuanet/politics", 3),
    # Reuters via RSSHub
    ("Reuters", "reuters/world", 3),
    # 半岛电视台
    ("半岛电视台", "aljazeera/news", 3),
    # FT中文网
    ("FT中文网", "ft/chinese/hotstoryby", 3),
    # 36氪
    ("36氪", "36kr/newsflashes", 5),
    # Hacker News
    ("Hacker News", "hackernews/best", 3),
    # Ars Technica
    ("Ars Technica", "ars/technica", 3),
]


def main():
    parser = argparse.ArgumentParser(description="历史新闻获取工具")
    parser.add_argument("--source", default="all", help="数据源: all/rsshub/file")
    parser.add_argument("--file", help="JSON/CSV 文件路径（source=file 时使用）")
    parser.add_argument("--pages", type=int, default=3, help="RSSHub 爬取页数")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API 地址")
    args = parser.parse_args()

    print("=" * 50)
    print("TimeTrace 历史新闻获取工具")
    print("=" * 50)

    # 登录
    print("\n[1/3] 登录...")
    token = login(args.base_url)
    print("  登录成功")

    # 获取数据
    all_articles = []

    if args.source in ("all", "rsshub"):
        print(f"\n[2/3] 通过 RSSHub 获取历史数据（每源{args.pages}页）...")
        for name, route, default_pages in RSSHUB_ROUTES:
            pages = args.pages or default_pages
            print(f"\n  爬取 {name} ({route}, {pages}页)...")
            articles = fetch_via_rsshub(name, route, pages)
            all_articles.extend(articles)
            print(f"  → {name}: {len(articles)} 篇")

    if args.source == "file" and args.file:
        print(f"\n[2/3] 从文件导入: {args.file}")
        with open(args.file, "r", encoding="utf-8") as f:
            if args.file.endswith(".json"):
                data = json.load(f)
                if isinstance(data, list):
                    all_articles.extend(data)
                elif isinstance(data, dict) and "articles" in data:
                    all_articles.extend(data["articles"])
            elif args.file.endswith(".csv"):
                import csv
                reader = csv.DictReader(f)
                for row in reader:
                    all_articles.append({
                        "title": row.get("title", ""),
                        "content": row.get("content", ""),
                        "source_url": row.get("source_url", ""),
                        "published_at": row.get("published_at"),
                        "source_name": row.get("source_name", ""),
                    })
        print(f"  → 文件: {len(all_articles)} 篇")

    if not args.source in ("all", "rsshub", "file"):
        print(f"\nUnknown source: {args.source}")
        sys.exit(1)

    print(f"\n共获取 {len(all_articles)} 篇文章")

    # 导入
    print("\n[3/3] 导入系统...")
    import_to_api(all_articles, args.base_url, token)

    print("\n完成！")


if __name__ == "__main__":
    main()
