"""Distiller — 原子化拆解层（LLM 优先）。

职责：将一条新闻拆解为原子事实。
输入：原始文章（标题 + 正文）
输出：结构化的原子事实列表

主路径：LLM 结构化提取（高质量）
降级路径：jieba 本地提取（标记低置信度，供后续审计识别）
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AtomicFact:
    """一条原子事实。"""
    content: str                # 事实描述
    fact_type: str              # fact | action | number | entity
    entities: list[str] = field(default_factory=list)   # 涉及的实体
    numbers: list[str] = field(default_factory=list)     # 关键数值
    confidence: float = 1.0     # 置信度


@dataclass
class DistillResult:
    """拆解结果。"""
    facts: list[AtomicFact] = field(default_factory=list)
    core_entities: list[str] = field(default_factory=list)
    key_numbers: list[str] = field(default_factory=list)
    primary_action: str = ""        # 主要动作
    summary_line: str = ""          # 一句话摘要
    confidence: float = 1.0         # 整体置信度
    model_used: str = ""            # 使用的模型名
    is_llm_generated: bool = False  # 是否由 LLM 生成
    processing_time_ms: int = 0     # 处理耗时


# ─── LLM 提示模板 ───

_DISTILL_PROMPT = """请将以下新闻拆解为结构化的原子事实。

要求：
1. 提取所有关键事实，每条事实一句话
2. 识别所有命名实体（人名、地名、机构名、产品名等）
3. 提取关键数值（金额、百分比、人数等）
4. 判断主要动作词（如：宣布、制裁、发射、签署等）
5. 生成一句话摘要

严格返回以下 JSON 格式，不要输出其他文字：
{{
  "facts": [
    {{"content": "事实描述", "type": "fact|action|number", "entities": ["实体1"], "numbers": ["数值1"]}}
  ],
  "entities": ["实体1", "实体2"],
  "numbers": ["数值1", "数值2"],
  "action": "主要动作词",
  "summary": "一句话摘要"
}}

标题：{title}
内容：{content}"""


class Distiller:
    """原子化拆解器（LLM 优先）。

    流程：
    1. 优先用 LLM 做结构化提取（高置信度 0.9+）
    2. LLM 失败时降级到 jieba 本地提取（低置信度 0.6）
    """

    def __init__(self, nlp, llm=None):
        self._nlp = nlp
        self._llm = llm

    def distill(self, title: str, content: str) -> DistillResult:
        """将一篇文章拆解为原子事实。LLM 优先，jieba 兜底。"""
        start = time.time()

        # 主路径：LLM 结构化提取
        if self._llm and self._llm.is_available():
            result = self._llm_distill(title, content)
            if result:
                result.processing_time_ms = int((time.time() - start) * 1000)
                return result
            logger.info("LLM distill failed, falling back to jieba")

        # 降级路径：jieba 本地提取
        result = self._local_distill(title, content)
        result.processing_time_ms = int((time.time() - start) * 1000)
        return result

    def _llm_distill(self, title: str, content: str) -> DistillResult | None:
        """用 LLM 做结构化提取。成功返回 DistillResult，失败返回 None。"""
        try:
            text = content[:1500] if content else ""
            prompt = _DISTILL_PROMPT.format(title=title, content=text)

            # 使用更大的 max_tokens — 蒸馏需要返回完整 JSON
            response = self._llm._call_llm(prompt, max_tokens_override=2000)
            if not response:
                logger.warning("LLM returned empty response for distill")
                return None

            logger.info(f"LLM distill raw response (first 300 chars): {response[:300]}")

            # 清理 LLM 返回的文本，提取 JSON 对象
            parsed = self._extract_json(response)
            
            if parsed is None:
                logger.warning(f"Failed to extract JSON from LLM response: {response[:200]}")
                return None

            # 构建 AtomicFact 列表
            facts = []
            for item in parsed.get("facts", [])[:15]:
                if isinstance(item, dict) and "content" in item:
                    facts.append(AtomicFact(
                        content=str(item["content"])[:200],
                        fact_type=str(item.get("type", "fact")),
                        entities=item.get("entities", [])[:5],
                        numbers=item.get("numbers", [])[:3],
                        confidence=0.95,
                    ))

            result = DistillResult(
                facts=facts,
                core_entities=parsed.get("entities", [])[:10],
                key_numbers=parsed.get("numbers", [])[:10],
                primary_action=parsed.get("action", ""),
                summary_line=parsed.get("summary", title if len(title) <= 60 else title[:57] + "..."),
                confidence=0.9,
                model_used=getattr(self._llm, '_model_name', 'unknown'),
                is_llm_generated=True,
            )

            # 如果 LLM 没提取到任何事实，视为失败
            if not result.facts and not result.core_entities:
                logger.warning("LLM returned empty extraction result")
                return None

            logger.info(f"LLM distill success: {len(result.facts)} facts, {len(result.core_entities)} entities")
            return result

        except Exception as e:
            logger.warning(f"LLM distill error: {e}")
            return None

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """从 LLM 返回文本中提取 JSON 对象，处理各种格式。"""
        text = text.strip()

        # 1. 去掉 markdown 代码块包裹
        if "```" in text:
            text = re.sub(r'^.*?```\w*\n?', '', text, count=1)
            text = re.sub(r'\n?```.*$', '', text, count=1)
            text = text.strip()

        # 2. 找到第一个 { 和最后一个 } 之间的内容
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            logger.warning(f"No JSON object found in response: {text[:100]}")
            return None

        json_str = text[start:end + 1]

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.debug(f"Initial JSON parse failed: {e}")

        # 3. 尝试修复常见问题：单引号 → 双引号、去掉尾逗号
        fixed = json_str.replace("'", '"')
        fixed = re.sub(r',\s*([}\]])', r'\1', fixed)  # 去掉 } ] 前的逗号
        try:
            return json.loads(fixed)
        except json.JSONDecodeError as e:
            logger.debug(f"Fixed JSON parse failed: {e}")

        # 4. 尝试修复未闭合的字符串和缺失的引号
        # 处理键没有引号的情况: {facts: [...]} → {"facts": [...]}
        fixed2 = re.sub(r'(\w+)\s*:', r'"\1":', fixed)
        try:
            return json.loads(fixed2)
        except json.JSONDecodeError as e:
            logger.debug(f"Quoted keys JSON parse failed: {e}")

        # 5. 逐层尝试：从外到内找可解析的 JSON
        for depth_end in range(end, start, -1):
            if text[depth_end] == '}':
                try:
                    return json.loads(text[start:depth_end + 1])
                except json.JSONDecodeError:
                    continue

        logger.warning(f"Failed to parse JSON from response: {text[:200]}")
        return None

    def _local_distill(self, title: str, content: str) -> DistillResult:
        """jieba 本地原子化 — 降级路径，低置信度。"""
        text = f"{title}。{content[:2000]}" if content else title

        # 关键词 + 实体
        keywords = self._nlp.extract_keywords(text)
        entities = self._nlp.extract_entities(text)

        entity_names = [e.get("name", "") for e in entities if e.get("name")]
        core_entities = list(dict.fromkeys(entity_names))[:10]

        key_numbers = self._extract_numbers(text)
        primary_action = self._extract_action(title)
        facts = self._split_facts(title, content or "", core_entities, key_numbers)
        summary_line = title if len(title) <= 60 else title[:57] + "..."

        return DistillResult(
            facts=facts,
            core_entities=core_entities,
            key_numbers=key_numbers,
            primary_action=primary_action,
            summary_line=summary_line,
            confidence=0.6,
            model_used="jieba",
            is_llm_generated=False,
        )

    # ─── 数字提取 ───

    _NUMBER_PATTERNS = [
        re.compile(r'\d+\.?\d*\s*[万亿千百十]?[元美元人%个百分点]', re.UNICODE),
        re.compile(r'\d+\.?\d*\s*[—\-–]\s*\d+\.?\d*'),
        re.compile(r'\d{1,3}(,\d{3})+'),
        re.compile(r'\d+\.?\d*%'),
    ]

    def _extract_numbers(self, text: str) -> list[str]:
        numbers = []
        for pattern in self._NUMBER_PATTERNS:
            for match in pattern.finditer(text):
                num = match.group().strip()
                if num and num not in numbers:
                    numbers.append(num)
        return numbers[:10]

    # ─── 动作词提取 ───

    _ACTION_KEYWORDS = {
        "宣布", "决定", "通过", "签署", "发布", "批准", "拒绝", "制裁",
        "发射", "爆炸", "袭击", "抗议", "崩盘", "暴涨", "下跌", "逮捕",
        "辞职", "当选", "任命", "解除", "废除", "推出", "关闭", "重启",
        "启动", "完成", "中断", "恢复", "暂停", "合并", "收购", "上市",
    }

    def _extract_action(self, title: str) -> str:
        for kw in self._ACTION_KEYWORDS:
            if kw in title:
                return kw
        return ""

    # ─── 原子事实拆解 ───

    def _split_facts(self, title: str, content: str, entities: list[str], numbers: list[str]) -> list[AtomicFact]:
        facts = []

        # 标题本身就是核心事实
        facts.append(AtomicFact(
            content=title,
            fact_type="fact",
            entities=[e for e in entities if e in title],
            numbers=[n for n in numbers if n in title],
            confidence=1.0,
        ))

        # 按句子拆解正文
        sentences = re.split(r'[。！？\n]', content)
        for sent in sentences[:10]:
            sent = sent.strip()
            if not sent or len(sent) < 10:
                continue

            fact_type = "fact"
            if any(kw in sent for kw in self._ACTION_KEYWORDS):
                fact_type = "action"
            elif any(n in sent for n in numbers):
                fact_type = "number"

            sent_entities = [e for e in entities if e in sent]
            sent_numbers = [n for n in numbers if n in sent]

            if sent_entities or sent_numbers or fact_type == "action":
                facts.append(AtomicFact(
                    content=sent[:200],
                    fact_type=fact_type,
                    entities=sent_entities[:5],
                    numbers=sent_numbers[:3],
                    confidence=0.8,
                ))

        return facts[:15]
