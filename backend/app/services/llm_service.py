"""LLM service: 智谱 GLM API + Embedding integration."""

import logging
import math

from ..config import settings

logger = logging.getLogger(__name__)


# ─── Core helpers ──────────────────────────────────────────

def _get_client():
    """Get 智谱 API client."""
    if not settings.LLM_API_KEY:
        return None
    try:
        from zhipuai import ZhipuAI
        return ZhipuAI(api_key=settings.LLM_API_KEY)
    except Exception as e:
        logger.warning(f"Failed to init zhipuai client: {e}")
        return None


def _call_llm(prompt: str, system: str = "你是一个新闻事件分析助手。") -> str | None:
    """Call 智谱 GLM chat API."""
    client = _get_client()
    if not client:
        return None
    try:
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"LLM call failed: {e}")
        return None


# ─── Embedding ─────────────────────────────────────────────

def get_embedding(text: str) -> list[float] | None:
    """Get embedding vector for a text string via 智谱 API."""
    if not settings.LLM_API_KEY:
        return None
    client = _get_client()
    if not client:
        return None
    try:
        response = client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=text[:2000],  # Truncate to avoid token limits
        )
        return response.data[0].embedding
    except Exception as e:
        logger.warning(f"Embedding call failed: {e}")
        return None


def batch_get_embeddings(texts: list[str]) -> list[list[float] | None]:
    """Get embeddings for multiple texts. Returns list aligned with input."""
    if not settings.LLM_API_KEY:
        return [None] * len(texts)
    results: list[list[float] | None] = []
    for text in texts:
        results.append(get_embedding(text))
    return results


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if not n1 or not n2:
        return 0.0
    return dot / (n1 * n2)


def compute_centroid(vectors: list[list[float]]) -> list[float] | None:
    """Compute the centroid (mean) of a list of vectors."""
    if not vectors:
        return None
    dim = len(vectors[0])
    centroid = [0.0] * dim
    for v in vectors:
        for i in range(dim):
            centroid[i] += v[i]
    n = len(vectors)
    return [x / n for x in centroid]


# ─── LLM event analysis ──────────────────────────────────

def generate_event_title(article_titles: str) -> str | None:
    """Generate a concise event title from article titles."""
    prompt = (
        f"根据以下新闻标题，生成一个简洁的事件标题（15字以内，不要标点）：\n\n"
        f"{article_titles}"
    )
    result = _call_llm(prompt)
    if result:
        result = result.strip('"').strip("'").strip("《》")
        if len(result) > 50:
            result = result[:50]
    return result


def generate_event_summary(article_titles: str) -> str | None:
    """Generate a brief event summary from article titles."""
    prompt = (
        f"根据以下新闻标题，生成一段简短的事件摘要（50字以内）：\n\n"
        f"{article_titles}"
    )
    return _call_llm(prompt)


def generate_article_summary(title: str, content: str) -> str | None:
    """Generate article summary."""
    text = content[:1500] if content else title
    prompt = f"请用一句话总结以下新闻（30字以内）：\n\n标题：{title}\n内容：{text}"
    return _call_llm(prompt)


def classify_article(title: str, content: str) -> str | None:
    """Classify article into category."""
    prompt = (
        f"请将以下新闻分类为一个类别，只返回类别名称：\n"
        f"科技、财经、社会、国际、娱乐、体育、健康、教育\n\n"
        f"标题：{title}\n内容：{content[:500]}"
    )
    result = _call_llm(prompt)
    if result:
        result = result.strip()
        valid = {"科技", "财经", "社会", "国际", "娱乐", "体育", "健康", "教育"}
        if result not in valid:
            result = "科技"
    return result


def verify_same_event(title1: str, title2: str, summary1: str = "", summary2: str = "") -> bool | None:
    """Use LLM to verify if two articles are about the same event.

    Returns True/False, or None if LLM unavailable.
    """
    prompt = (
        f"判断以下两条新闻是否在报道同一个事件。只回答"是"或"否"。\n\n"
        f"新闻1标题：{title1}\n"
        f"{'新闻1摘要：' + summary1[:200] if summary1 else ''}\n"
        f"新闻2标题：{title2}\n"
        f"{'新闻2摘要：' + summary2[:200] if summary2 else ''}"
    )
    result = _call_llm(prompt, system="你是一个新闻分析助手，只回答是或否。")
    if not result:
        return None
    result = result.strip()
    if "是" in result and "否" not in result:
        return True
    if "否" in result:
        return False
    return None
