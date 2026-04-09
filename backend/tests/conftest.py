"""Test configuration and fixtures."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# 强制使用测试数据库和密码（在导入 app 之前设置环境变量）
os.environ["DATABASE_URL"] = "sqlite:///./test_timetrace.db"
os.environ["ADMIN_PASSWORD"] = "test_admin_123"


@pytest.fixture(scope="session")
def app_client():
    """创建测试用的 FastAPI TestClient，使用独立测试数据库。"""
    from fastapi.testclient import TestClient

    # 清理旧测试数据库，避免残留的 admin 用户导致密码不一致
    _test_db_path = Path(__file__).parent.parent / "test_timetrace.db"
    if _test_db_path.exists():
        _test_db_path.unlink()

    import app.config as config_module
    import app.database as db_module

    # 直接修改全局 settings 实例的属性（而非替换对象）
    # 这样所有 from .config import settings 的引用都能生效
    config_module.settings.ADMIN_PASSWORD = "test_admin_123"
    test_db_url = "sqlite:///./test_timetrace.db"
    config_module.settings.DATABASE_URL = test_db_url

    # 重新创建 engine
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    test_engine = create_engine(
        test_db_url,
        connect_args={"check_same_thread": False},
    )
    test_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # 替换全局 engine 和 SessionLocal
    db_module.engine = test_engine
    db_module.SessionLocal = test_session_factory

    # 创建所有表
    from app.models import Base
    Base.metadata.create_all(bind=test_engine)

    # 运行种子数据
    from app.main import seed_database
    seed_database()

    # 导入 app（此时会使用新的 engine）
    from app.main import app
    client = TestClient(app)

    yield client

    # 清理：删除测试数据库
    import gc
    gc.collect()
    try:
        _test_db_path.unlink(missing_ok=True)
    except Exception:
        pass


@pytest.fixture(scope="session")
def admin_token(app_client):
    """获取管理员 token。"""
    resp = app_client.post("/api/users/login", json={
        "username": "admin",
        "password": "test_admin_123",
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
def sample_article_html():
    """Sample article HTML for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="publishdate" content="2024-01-15">
        <title>测试文章标题_人民网</title>
    </head>
    <body>
        <h1>测试文章标题</h1>
        <div class="box01_date">2024年01月15日10:30</div>
        <div class="editor">责任编辑：张三</div>
        <div id="rwb_zw">
            <p>这是第一段测试内容，用于验证内容提取功能。</p>
            <p>这是第二段测试内容，包含更多的文字信息。</p>
            <p>这是第三段测试内容，确保能够正确提取多段落文本。</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_list_html():
    """Sample list page HTML for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <body>
        <ul>
            <li><a href="http://www.people.com.cn/n1/2024/01-15/c123456-78901234.html">文章标题1</a></li>
            <li><a href="http://www.people.com.cn/n1/2024/01-14/c123456-78901233.html">文章标题2</a></li>
            <li><a href="http://www.people.com.cn/n1/2024/01-13/c123456-78901232.html">文章标题3</a></li>
        </ul>
    </body>
    </html>
    """


@pytest.fixture
def sample_articles():
    """Sample articles for testing."""
    from datetime import datetime, timezone
    
    return [
        {
            "title": "人工智能发展迅速，科技行业迎来新机遇",
            "content": "人工智能技术在近年来取得了重大突破，深度学习、自然语言处理等领域发展迅速。专家预测，未来五年AI将在更多领域得到应用。",
            "source_url": "http://example.com/article/1",
            "published_at": datetime(2024, 1, 15, 10, 30, tzinfo=timezone.utc),
        },
        {
            "title": "人工智能发展迅猛，科技行业迎来新机会",
            "content": "人工智能技术近年来取得重大突破，深度学习、自然语言处理等领域发展迅猛。专家预测未来五年AI将在更多领域应用。",
            "source_url": "http://example.com/article/2",
            "published_at": datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc),
        },
        {
            "title": "新能源汽车销量创新高",
            "content": "2024年第一季度，新能源汽车销量同比增长50%，市场渗透率持续提升。",
            "source_url": "http://example.com/article/3",
            "published_at": datetime(2024, 1, 16, 9, 0, tzinfo=timezone.utc),
        },
    ]
