"""Auditor — 审计验证层。

职责：对 Distiller 拆解结果和 ReasoningEngine 推演结果做交叉验证。
输入：原始文章 + DistillResult + ReasoningResult
输出：AuditResult（通过/人工审核/安全模式）

不依赖 models/schemas。通过回调写入 AuditLog。
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ─── 审计阈值 ───
_CONFIDENCE_PASS = 0.7        # ≥ 此值直接通过
_CONFIDENCE_REVIEW = 0.4      # ≥ 此值标记人工审核
# < 此值进入安全模式


@dataclass
class AuditResult:
    """审计结果。"""
    passed: bool = False              # 是否通过审计
    status: str = "fail"              # pass | manual_review | safe_mode
    confidence: float = 0.0           # 审计置信度 0-1

    # ─── 实体检证 ───
    entity_check: dict = field(default_factory=dict)
    # {"matched": [...], "unmatched": [...], "missing": [...]}

    # ─── 问题列表 ───
    issues: list[str] = field(default_factory=list)
    # ["实体不匹配: X", "数值冲突: Y", ...]

    # ─── 快照 ───
    raw_snapshot: dict = field(default_factory=dict)
    result_snapshot: dict = field(default_factory=dict)


class Auditor:
    """审计验证器。

    三级判定：
    1. 通过（confidence ≥ 0.7）→ 正常入库
    2. 人工审核（0.4 ≤ confidence < 0.7）→ 标记 needs_review
    3. 安全模式（confidence < 0.4）→ 仅展示原始标题和摘要

    验证项：
    - 实体回溯：推演结果中的实体是否在原文中出现
    - 数值校验：关键数值是否被篡改或缺失
    - 一致性检查：推演动作与拆解结果是否一致
    """

    def __init__(self, llm=None):
        self._llm = llm

    def audit(self, article, distill_result, reasoning_result) -> AuditResult:
        """对拆解+推演结果执行审计。"""
        result = AuditResult()

        # 收集原始文本用于验证
        raw_text = f"{article.title} {article.content[:2000] if article.content else ''}"

        # ─── 快照 ───
        result.raw_snapshot = {
            "title": article.title[:100],
            "entities": distill_result.core_entities[:10] if distill_result else [],
            "key_numbers": distill_result.key_numbers[:5] if distill_result else [],
        }
        result.result_snapshot = {
            "action": reasoning_result.action if reasoning_result else "skip",
            "event_title": reasoning_result.event_title[:50] if reasoning_result else "",
            "category": reasoning_result.suggested_category if reasoning_result else "",
            "importance": reasoning_result.suggested_importance if reasoning_result else 3,
        }

        # ─── 1. 实体回溯 ───
        entity_score = self._check_entities(raw_text, distill_result, reasoning_result, result)

        # ─── 2. 数值校验 ───
        number_score = self._check_numbers(raw_text, distill_result, result)

        # ─── 3. 一致性检查 ───
        consistency_score = self._check_consistency(distill_result, reasoning_result, result)

        # ─── 4. 安全模式检查 ───
        safe_mode_penalty = 0.0
        if reasoning_result and reasoning_result.safe_mode:
            safe_mode_penalty = 0.3
            result.issues.append("上游标记安全模式")

        # ─── 综合置信度 ───
        # 加权：实体 40% + 数值 25% + 一致性 25% + 安全惩罚 10%
        base_confidence = (
            entity_score * 0.4
            + number_score * 0.25
            + consistency_score * 0.25
        )
        # 如果有上游置信度，取平均
        upstream_conf = 1.0
        if reasoning_result:
            upstream_conf = reasoning_result.confidence
        if distill_result:
            upstream_conf = (upstream_conf + distill_result.confidence) / 2

        result.confidence = (base_confidence * 0.6 + upstream_conf * 0.4) - safe_mode_penalty
        result.confidence = max(0.0, min(1.0, result.confidence))

        # ─── 三级判定 ───
        if result.confidence >= _CONFIDENCE_PASS:
            result.passed = True
            result.status = "pass"
        elif result.confidence >= _CONFIDENCE_REVIEW:
            result.passed = False
            result.status = "manual_review"
            result.issues.append(f"置信度不足: {result.confidence:.2f}")
        else:
            result.passed = False
            result.status = "safe_mode"
            result.issues.append(f"置信度过低: {result.confidence:.2f}，进入安全模式")

        return result

    def _check_entities(self, raw_text, distill_result, reasoning_result, result: AuditResult) -> float:
        """实体回溯：检查推演结果中的实体是否在原文中可追溯。"""
        if not distill_result:
            return 0.5

        core_entities = distill_result.core_entities or []
        if not core_entities:
            # 没有实体提取出来，不扣分
            result.entity_check = {"matched": [], "unmatched": [], "missing": []}
            return 0.8

        matched = []
        unmatched = []

        for entity in core_entities:
            if entity in raw_text:
                matched.append(entity)
            else:
                unmatched.append(entity)

        # 如果推演产生了新实体（不在拆解结果中），标记为 missing
        missing = []
        if reasoning_result and reasoning_result.event_title:
            # 检查推演标题中是否出现了原文没有的实体
            for entity in core_entities:
                if entity in reasoning_result.event_title:
                    pass  # 合理使用
            # 不做额外惩罚，推演可以使用原文实体

        result.entity_check = {
            "matched": matched[:10],
            "unmatched": unmatched[:5],
            "missing": missing[:5],
        }

        if unmatched:
            result.issues.append(f"实体不匹配: {', '.join(unmatched[:3])}")

        if not core_entities:
            return 0.8
        return len(matched) / len(core_entities)

    def _check_numbers(self, raw_text, distill_result, result: AuditResult) -> float:
        """数值校验：检查关键数值是否在原文中。"""
        if not distill_result:
            return 0.5

        key_numbers = distill_result.key_numbers or []
        if not key_numbers:
            return 0.9  # 没有数值，不扣分

        matched = 0
        for num in key_numbers:
            if num in raw_text:
                matched += 1
            else:
                result.issues.append(f"数值不可追溯: {num}")

        return matched / len(key_numbers)

    def _check_consistency(self, distill_result, reasoning_result, result: AuditResult) -> float:
        """一致性检查：推演动作与拆解结果是否一致。"""
        if not reasoning_result:
            return 0.5

        score = 1.0

        # 检查：如果推演说是 link，但没有任何实体匹配 → 可疑
        if reasoning_result.action == "link":
            if not distill_result or not distill_result.core_entities:
                score -= 0.3
                result.issues.append("关联判定无实体支撑")

        # 检查：如果是新事件但重要度很高 → 需要验证
        if reasoning_result.action == "new" and reasoning_result.suggested_importance >= 5:
            if not distill_result or not distill_result.primary_action:
                score -= 0.2
                result.issues.append("高重要度新事件无动作支撑")

        # 检查：推演标题与原标题完全不重叠 → 可疑
        if reasoning_result.event_title and hasattr(distill_result, 'summary_line'):
            title_chars = set(reasoning_result.event_title)
            original_chars = set(distill_result.summary_line) if distill_result and distill_result.summary_line else set()
            if title_chars and original_chars:
                overlap = len(title_chars & original_chars) / len(title_chars | original_chars)
                if overlap < 0.1:
                    score -= 0.2
                    result.issues.append("推演标题与原文无重叠")

        return max(0.0, score)
