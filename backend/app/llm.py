"""LLM 集成 — OpenAI 兼容格式。

支持所有兼容 OpenAI API 的服务商：
  智谱 GLM、DeepSeek、Moonshot、通义千问、零一万物、Ollama 等。

使用 openai SDK 统一调用，通过 LLM_API_BASE 切换服务商。
"""

import logging
import math
import hashlib

logger = logging.getLogger(__name__)


class OpenAICompatibleLLM:
    """OpenAI 兼容 LLM 实现。

    所有国产大模型厂商都支持 OpenAI 兼容 API，只需改 base_url：
    - 智谱: https://open.bigmodel.cn/api/paas/v4
    - DeepSeek: https://api.deepseek.com/v1
    - Moonshot: https://api.moonshot.cn/v1
    - 通义: https://dashscope.aliyuncs.com/compatible-mode/v1
    - Ollama: http://localhost:11434/v1
    """

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://open.bigmodel.cn/api/paas/v4",
        model: str = "",
        temperature: float = 0.3,
        top_p: float = 0.7,
        max_tokens: int = 300,
        embedding_model: str = "embedding-3",
    ):
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._top_p = top_p
        self._max_tokens = max_tokens
        self._embedding_model = embedding_model
        self._client = None

    def _get_client(self):
        if self._client is None and self._api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self._api_key,
                    base_url=self._api_base,
                )
            except Exception as e:
                logger.warning(f"Failed to init OpenAI client: {e}")
        return self._client

    def is_available(self) -> bool:
        return bool(self._api_key) and bool(self._model) and self._get_client() is not None

    def list_models(self) -> list[dict]:
        """获取可用模型列表。返回 [{"id": "model-name", "owned_by": "..."}]。"""
        client = self._get_client()
        if not client:
            return []
        try:
            resp = client.models.list()
            return [
                {"id": m.id, "owned_by": getattr(m, "owned_by", "")}
                for m in resp.data
            ]
        except Exception as e:
            logger.warning(f"List models failed: {e}")
            return []

    def _call_llm(self, prompt: str, system: str = "你是一个新闻事件分析助手。", max_tokens_override: int | None = None) -> str | None:
        """调用 LLM，返回文本结果。"""
        client = self._get_client()
        if not client or not self._model:
            return None
        try:
            max_tokens = max_tokens_override if max_tokens_override is not None else self._max_tokens
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=self._temperature,
                top_p=self._top_p,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"LLM call failed (model={self._model}): {e}")
            return None

    def generate_summary(self, text: str, max_length: int = 50) -> str | None:
        prompt = f"请用一句话总结以下新闻（{max_length}字以内）：\n\n{text[:1500]}"
        return self._call_llm(prompt)

    def generate_event_title(self, article_titles: list[str]) -> str | None:
        titles_text = "\n".join(f"- {t}" for t in article_titles[:5])
        prompt = f"根据以下新闻标题，生成一个简洁的事件标题（15字以内，不要标点）：\n\n{titles_text}"
        result = self._call_llm(prompt)
        if result:
            result = result.strip('"').strip("'").strip("《》")
            if len(result) > 50:
                result = result[:50]
        return result

    def generate_event_summary(self, article_titles: list[str]) -> str | None:
        titles_text = "\n".join(f"- {t}" for t in article_titles[:5])
        prompt = f"根据以下新闻标题，生成一段简短的事件摘要（50字以内）：\n\n{titles_text}"
        return self._call_llm(prompt)

    def get_embedding(self, text: str) -> list[float] | None:
        """获取文本 embedding。"""
        client = self._get_client()
        if not client:
            return None
        try:
            response = client.embeddings.create(
                model=self._embedding_model,
                input=text[:2000],
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(f"Embedding call failed: {e}")
            return None

    def batch_get_embeddings(self, texts: list[str]) -> list[list[float] | None]:
        return [self.get_embedding(text) for text in texts]

    def verify_same_event(
        self,
        title1: str,
        title2: str,
        summary1: str = "",
        summary2: str = "",
    ) -> bool | None:
        prompt = (
            f"判断以下两条新闻是否在报道同一个事件。只回答\"是\"或\"否\"。\n\n"
            f"新闻1标题：{title1}\n"
            f"{'新闻1摘要：' + summary1[:200] if summary1 else ''}\n"
            f"新闻2标题：{title2}\n"
            f"{'新闻2摘要：' + summary2[:200] if summary2 else ''}"
        )
        result = self._call_llm(prompt, system="你是一个新闻分析助手，只回答是或否。")
        if not result:
            return None
        result = result.strip()
        if "是" in result and "否" not in result:
            return True
        if "否" in result:
            return False
        return None

    def classify_article(self, title: str, content: str) -> str | None:
        prompt = (
            f"请将以下新闻分类为一个类别，只返回类别名称：\n"
            f"科技、财经、社会、国际、娱乐、体育、健康、教育\n\n"
            f"标题：{title}\n内容：{content[:500]}"
        )
        result = self._call_llm(prompt)
        if result:
            result = result.strip()
            valid = {"科技", "财经", "社会", "国际", "娱乐", "体育", "健康", "教育"}
            if result not in valid:
                result = "科技"
        return result


class MockLLMProvider:
    """Mock LLM implementation for testing."""

    def __init__(self, seed: int = 42):
        self._seed = seed

    def is_available(self) -> bool:
        return True

    def _call_llm(self, prompt: str, system: str = "你是一个新闻事件分析助手。", max_tokens_override: int | None = None) -> str | None:
        """Mock LLM 调用 — 返回简单的 JSON 结构化响应。"""
        import json
        # 如果是蒸馏提示，返回结构化 JSON
        if "拆解为结构化的原子事实" in prompt or "原子事实" in prompt:
            return json.dumps({
                "facts": [
                    {"content": "[Mock] 测试事实", "type": "fact", "entities": ["测试"], "numbers": []}
                ],
                "entities": ["测试"],
                "numbers": [],
                "action": "测试",
                "summary": "[Mock] 测试摘要"
            }, ensure_ascii=False)
        # 如果是判断事件关联
        if "是否属于" in prompt or "是否在报道同一个事件" in prompt:
            return "是"
        # 如果是生成事件标题/分类
        if "事件标题" in prompt and "分类" in prompt:
            return "[Mock]事件|科技|3"
        # 默认返回
        return "[Mock] 测试响应"

    def generate_summary(self, text: str, max_length: int = 50) -> str | None:
        return f"[Mock] 这是一条测试摘要，内容长度约{len(text)}字。"

    def generate_event_title(self, article_titles: list[str]) -> str | None:
        if not article_titles:
            return None
        return f"[Mock] 事件：{article_titles[0][:15]}"

    def generate_event_summary(self, article_titles: list[str]) -> str | None:
        return f"[Mock] 这是一个包含{len(article_titles)}篇文章的事件摘要。"

    def get_embedding(self, text: str) -> list[float] | None:
        hash_obj = hashlib.md5(text.encode())
        hash_bytes = hash_obj.digest()
        embedding = []
        for i in range(0, 32, 2):
            val = int.from_bytes(hash_bytes[i:i+2], 'big')
            embedding.append(val / 65535.0)
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]
        return embedding

    def batch_get_embeddings(self, texts: list[str]) -> list[list[float] | None]:
        return [self.get_embedding(text) for text in texts]

    def verify_same_event(
        self,
        title1: str,
        title2: str,
        summary1: str = "",
        summary2: str = "",
    ) -> bool | None:
        common_chars = set(title1) & set(title2)
        similarity = len(common_chars) / max(len(set(title1) | set(title2)), 1)
        return similarity > 0.3

    def classify_article(self, title: str, content: str) -> str | None:
        text = title + content
        if any(kw in text for kw in ["科技", "技术", "AI", "互联网"]):
            return "科技"
        if any(kw in text for kw in ["财经", "经济", "股市", "金融"]):
            return "财经"
        if any(kw in text for kw in ["国际", "外交", "国家"]):
            return "国际"
        return "社会"

    def list_models(self) -> list[dict]:
        return []


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if not n1 or not n2:
        return 0.0
    return dot / (n1 * n2)


def compute_centroid(vectors: list[list[float]]) -> list[float] | None:
    if not vectors:
        return None
    dim = len(vectors[0])
    centroid = [0.0] * dim
    for v in vectors:
        for i in range(dim):
            centroid[i] += v[i]
    n = len(vectors)
    return [x / n for x in centroid]


def create_llm_from_model(model_obj, provider) -> OpenAICompatibleLLM:
    """从 LlmModel + LlmProvider ORM 对象创建 OpenAICompatibleLLM 实例。"""
    return OpenAICompatibleLLM(
        api_key=provider.api_key,
        api_base=provider.api_base,
        model=model_obj.model,
        temperature=model_obj.temperature,
        top_p=model_obj.top_p,
        max_tokens=model_obj.max_tokens,
    )


def create_llm_from_embed(embed_model, embed_provider) -> OpenAICompatibleLLM:
    """从 EmbedModel + EmbedProvider ORM 对象创建 OpenAICompatibleLLM 实例（用于向量生成）。"""
    return OpenAICompatibleLLM(
        api_key=embed_provider.api_key,
        api_base=embed_provider.api_base,
        model=embed_model.model,
        embedding_model=embed_model.model,
    )
