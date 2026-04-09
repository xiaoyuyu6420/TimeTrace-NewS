"""ReasoningEngine — 大模型推演层。

职责：接收 Distiller 的原子事实，执行宏观判断。
输入：原子事实列表 + 近期活跃事件列表
输出：推演结果（时间线归属 + 阶段判定 + 冲突标记）

不依赖 models/schemas。
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ReasoningResult:
    """推演结果。"""
    # ─── 时间线归属 ───
    action: str = "new"              # link | new | skip
    target_event_id: int | None = None  # link 时目标事件 ID
    target_event_title: str = ""     # 目标事件标题

    # ─── 阶段判定 ───
    phase: str = "trigger"           # trigger | development | outcome | followup
    phase_confidence: float = 0.5    # 阶段判定的置信度

    # ─── 事件属性 ───
    suggested_category: str = ""     # 建议分类
    suggested_importance: int = 3    # 建议重要度 1-5
    event_title: str = ""            # 如果是新事件，建议的标题
    event_summary: str = ""          # 事件摘要

    # ─── 冲突检测 ───
    has_conflict: bool = False       # 是否与现有事实冲突
    conflict_details: str = ""       # 冲突描述

    # ─── 整体 ───
    confidence: float = 0.5          # 推演整体置信度
    needs_review: bool = False       # 是否需要人工审核
    safe_mode: bool = False          # 是否进入安全模式


class ReasoningEngine:
    """大模型推演引擎。

    两级策略：
    1. 规则引擎（零成本）：embedding 相似度 + 关键词匹配 + 阶段关键词
    2. 大模型（选择性调用）：语义判定 + 分类 + 冲突检测

    如果大模型不可用，完全降级到规则引擎。
    """

    def __init__(self, llm, nlp):
        self._llm = llm
        self._nlp = nlp

    def reason(self, distill_result, article, active_events: list) -> ReasoningResult:
        """对拆解后的事实执行推演。"""
        # Stage A: 规则引擎 — 关联度计算（零成本）
        result = self._rule_based_reason(distill_result, article, active_events)

        # Stage B: 大模型推演（选择性，约¥0.01/次）
        if self._llm and self._llm.is_available():
            self._llm_reason(article, distill_result, active_events, result)

        return result

    def _rule_based_reason(self, distill_result, article, active_events: list) -> ReasoningResult:
        """规则引擎：embedding + 关键词计算关联度。"""
        result = ReasoningResult()
        result.event_title = article.title
        result.event_summary = distill_result.summary_line
        result.suggested_importance = 3

        if not active_events:
            result.action = "new"
            result.phase = "trigger"
            result.confidence = 0.7
            return result

        # 计算与每个活跃事件的相似度
        best_event = None
        best_score = 0.0

        for event in active_events:
            score = self._compute_relevance(article, event, distill_result)
            if score > best_score:
                best_score = score
                best_event = event

        # 三级判定
        if best_event and best_score >= 0.55:
            # ── 高关联：增量更新 ──
            result.action = "link"
            result.target_event_id = best_event.id
            result.target_event_title = best_event.title
            result.phase = self._infer_phase(best_event, article, distill_result)
            result.confidence = 0.9
            result.suggested_importance = best_event.importance

        elif best_event and best_score >= 0.35:
            # ── 中关联：需要 LLM 验证 ──
            result.action = "link"
            result.target_event_id = best_event.id
            result.target_event_title = best_event.title
            result.phase = "development"
            result.confidence = 0.5
            result.needs_review = True  # 标记需要验证

        else:
            # ── 低关联：新事件 ──
            result.action = "new"
            result.phase = "trigger"
            result.confidence = 0.7

        # 重要性推断
        result.suggested_importance = self._infer_importance(article, distill_result)

        # 分类推断
        result.suggested_category = self._infer_category(article, distill_result)

        return result

    def _compute_relevance(self, article, event, distill_result) -> float:
        """计算文章与事件的关联度。"""
        # Embedding 相似度
        if article.embedding:
            if event.embedding:
                return self._cosine(article.embedding, event.embedding)
            # 与事件的每篇文章比较
            for link in getattr(event, 'article_links', []):
                if hasattr(link, 'article') and link.article and link.article.embedding:
                    score = self._cosine(article.embedding, link.article.embedding)
                    if score > 0.55:
                        return score

        # 回退到关键词匹配
        event_keywords = self._collect_event_keywords(event)
        if distill_result.core_entities and event_keywords:
            ent_sim = self._nlp.keyword_similarity(
                distill_result.core_entities, event_keywords
            )
            if ent_sim > 0.3:
                return ent_sim

        # 标题字符重叠
        if article.title and event.title:
            s1, s2 = set(article.title), set(event.title)
            return len(s1 & s2) / len(s1 | s2) if s1 | s2 else 0.0

        return 0.0

    def _infer_phase(self, event, article, distill_result) -> str:
        """推断文章在事件中的阶段。"""
        from .timeline import determine_phase

        existing_count = 0
        for link in getattr(event, 'article_links', []):
            existing_count += 1

        return determine_phase(event, article, existing_count)

    def _infer_importance(self, article, distill_result) -> int:
        """推断重要度。"""
        title = article.title or ""
        # 头条特征
        if any(kw in title for kw in ["突发", "重大", "紧急", "刚刚", "重磅", "历史性"]):
            return 5
        # 热点特征
        if any(kw in title for kw in ["突破", "首次", "宣布", "决定", "制裁", "发射"]):
            return 4
        # 数值大
        if any(n in title for n in distill_result.key_numbers[:3]):
            return 4
        return 3

    def _infer_category(self, article, distill_result) -> str:
        """推断分类。"""
        text = f"{article.title} {article.content[:500] if article.content else ''}"
        if any(kw in text for kw in ["科技", "AI", "人工智能", "芯片", "互联网", "技术"]):
            return "科技"
        if any(kw in text for kw in ["经济", "股市", "GDP", "央行", "利率", "通胀"]):
            return "财经"
        if any(kw in text for kw in ["国际", "外交", "联合国", "峰会", "总统"]):
            return "国际"
        if any(kw in text for kw in ["政策", "法规", "改革", "出台", "发布"]):
            return "政策"
        return "综合"

    def _llm_reason(self, article, distill_result, active_events: list, result: ReasoningResult) -> None:
        """大模型推演（选择性调用）。"""
        try:
            # 如果是中关联，让 LLM 验证
            if result.needs_review and result.target_event_title:
                prompt = (
                    f"判断这条新闻是否属于已知事件。只回答\"是\"或\"否\"。\n\n"
                    f"已知事件：{result.target_event_title}\n"
                    f"新闻标题：{article.title}\n\n"
                    f"回答："
                )
                resp = self._llm._call_llm(prompt)
                if resp and "否" in resp.strip()[:5]:
                    # LLM 否定关联 → 改为新事件
                    result.action = "new"
                    result.target_event_id = None
                    result.target_event_title = ""
                    result.phase = "trigger"
                    result.needs_review = False
                    return
                result.needs_review = False

            # 如果是新事件，让 LLM 生成标题和分类
            if result.action == "new" and article.content:
                prompt = (
                    f"根据以下新闻，生成：\n"
                    f"1. 事件标题（15字以内）\n"
                    f"2. 事件分类（科技/财经/国际/政策/社会/综合）\n"
                    f"3. 重要度（1-5）\n\n"
                    f"标题：{article.title}\n"
                    f"内容：{article.content[:500]}\n\n"
                    f"格式：标题|分类|重要度"
                )
                resp = self._llm._call_llm(prompt)
                if resp:
                    parts = resp.strip().split("|")
                    if len(parts) >= 3:
                        result.event_title = parts[0].strip().strip('"')[:50]
                        result.suggested_category = parts[1].strip()
                        try:
                            result.suggested_importance = max(1, min(5, int(parts[2].strip())))
                        except ValueError:
                            pass

            result.confidence = min(1.0, result.confidence + 0.2)

        except Exception as e:
            logger.warning(f"LLM reasoning failed: {e}")
            result.safe_mode = True  # LLM 失败 → 安全模式

    def _collect_event_keywords(self, event) -> list[str]:
        """收集事件的所有关键词。"""
        keywords = []
        for link in getattr(event, 'article_links', []):
            if hasattr(link, 'article') and link.article and link.article.keywords:
                keywords.extend(link.article.keywords)
        return list(set(keywords))

    def _cosine(self, v1: list, v2: list) -> float:
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        n1 = sum(a * a for a in v1) ** 0.5
        n2 = sum(b * b for b in v2) ** 0.5
        return dot / (n1 * n2) if n1 and n2 else 0.0
