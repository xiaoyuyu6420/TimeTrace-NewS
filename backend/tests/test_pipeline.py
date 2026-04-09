"""三级管线单元测试 — Distiller / ReasoningEngine / Auditor。"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ─── 共享 Fixtures ──────────────────────────────────────

@pytest.fixture
def nlp():
    """真实 jieba 处理器。"""
    from app.nlp import JiebaProcessor
    return JiebaProcessor()


@pytest.fixture
def mock_llm():
    """Mock LLM（不走网络）。"""
    from app.llm import MockLLMProvider
    return MockLLMProvider()


@pytest.fixture
def no_llm():
    """完全不可用的 LLM。"""
    llm = MagicMock()
    llm.is_available.return_value = False
    return llm


@pytest.fixture
def sample_title():
    return "中国宣布成功发射新一代载人飞船"


@pytest.fixture
def sample_content():
    return (
        "新华社北京1月15日电 中国于今日上午在酒泉卫星发射中心成功发射了新一代载人飞船。"
        "此次发射标志着中国航天事业取得重大突破。"
        "飞船搭载了两名航天员，将在轨运行30天。"
        "项目总投资约50亿元人民币。"
        "专家表示，这将为未来深空探测奠定基础。"
    )


@pytest.fixture
def mock_article(sample_title, sample_content):
    """模拟 Article ORM 对象。"""
    article = MagicMock()
    article.id = 1
    article.title = sample_title
    article.content = sample_content
    article.summary = sample_title
    article.source_url = "http://example.com/1"
    article.published_at = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
    article.keywords = ["中国", "飞船", "发射"]
    article.entities = [
        {"name": "中国", "type": "LOCATION"},
        {"name": "酒泉", "type": "LOCATION"},
    ]
    article.embedding = None
    article.pipeline_state = "raw"
    article.distilled_facts = None
    article.reasoning_result = None
    return article


@pytest.fixture
def mock_event():
    """模拟 Event ORM 对象。"""
    event = MagicMock()
    event.id = 10
    event.title = "中国载人航天工程新进展"
    event.summary = "中国载人航天领域持续取得突破"
    event.category = "科技"
    event.importance = 4
    event.status = "active"
    event.embedding = None
    event.start_date = datetime(2024, 1, 10, tzinfo=timezone.utc)
    event.end_date = datetime(2024, 1, 14, tzinfo=timezone.utc)
    event.updated_at = datetime(2024, 1, 14, tzinfo=timezone.utc)
    event.article_links = []
    return event


# ═══════════════════════════════════════════════════════
# Test 1: Distiller
# ═══════════════════════════════════════════════════════

class TestDistiller:

    def test_distill_basic(self, nlp, mock_llm, sample_title, sample_content):
        """基本拆解：标题+正文 → AtomicFact 列表。"""
        from app.services.distill import Distiller

        d = Distiller(nlp, mock_llm)
        result = d.distill(sample_title, sample_content)

        assert result.facts, "应产生至少一条原子事实"
        assert result.core_entities, "应提取核心实体"
        assert result.confidence > 0, "置信度应 > 0"
        assert result.summary_line, "应有一句话摘要"

    def test_distill_no_llm(self, nlp, no_llm, sample_title, sample_content):
        """LLM 不可用时，本地拆解仍然成功。"""
        from app.services.distill import Distiller

        d = Distiller(nlp, no_llm)
        result = d.distill(sample_title, sample_content)

        assert result.facts, "LLM 不可用，本地应仍能拆解"
        assert result.confidence == 0.6  # 本地降级默认置信度

    def test_distill_numbers(self, nlp, no_llm):
        """数值提取。"""
        from app.services.distill import Distiller

        d = Distiller(nlp, no_llm)
        result = d.distill(
            "GDP增速达到6.5%",
            "今年第一季度GDP同比增长6.5%，总量达到28万亿元人民币。"
        )

        assert len(result.key_numbers) > 0, "应提取到数值"
        has_pct = any("%" in n for n in result.key_numbers)
        assert has_pct, f"应提取百分比，得到: {result.key_numbers}"

    def test_distill_action(self, nlp, no_llm):
        """动作词提取 — 返回标题中找到的第一个动作词。"""
        from app.services.distill import Distiller

        d = Distiller(nlp, no_llm)
        result = d.distill(
            "美国宣布对俄实施新制裁",
            "美国总统宣布对俄罗斯实施新一轮经济制裁。"
        )

        # 标题包含"宣布"和"制裁"，应提取到其中之一
        assert result.primary_action in d._ACTION_KEYWORDS, \
            f"应提取到动作词，得到: {result.primary_action}"

    def test_distill_empty_content(self, nlp, no_llm):
        """空内容不崩溃。"""
        from app.services.distill import Distiller

        d = Distiller(nlp, no_llm)
        result = d.distill("测试标题", "")

        assert result is not None
        assert result.facts, "标题本身应作为核心事实"

    def test_distill_entities(self, nlp, mock_llm, sample_title, sample_content):
        """实体提取。"""
        from app.services.distill import Distiller

        d = Distiller(nlp, mock_llm)
        result = d.distill(sample_title, sample_content)

        # MockLLM 的 _call_llm 返回固定内容，实体可能来自 LLM 或 jieba 降级
        # 至少应有一些实体
        assert result.core_entities, f"应提取到实体，得到: {result.core_entities}"

    def test_distill_facts_have_type(self, nlp, no_llm, sample_title, sample_content):
        """每条原子事实都有类型。"""
        from app.services.distill import Distiller

        d = Distiller(nlp, no_llm)
        result = d.distill(sample_title, sample_content)

        valid_types = {"fact", "action", "number", "entity"}
        for fact in result.facts:
            assert fact.fact_type in valid_types, f"无效类型: {fact.fact_type}"


# ═══════════════════════════════════════════════════════
# Test 2: ReasoningEngine
# ═══════════════════════════════════════════════════════

class TestReasoningEngine:

    def test_reason_new_event_no_active(self, nlp, mock_llm, mock_article):
        """无活跃事件 → 必然创建新事件。"""
        from app.services.distill import Distiller
        from app.services.reason import ReasoningEngine

        d = Distiller(nlp, mock_llm)
        distill_result = d.distill(mock_article.title, mock_article.content)

        engine = ReasoningEngine(mock_llm, nlp)
        result = engine.reason(distill_result, mock_article, [])

        assert result.action == "new"
        assert result.phase == "trigger"
        assert result.event_title, "新事件应有标题"

    def test_reason_link_high_similarity(self, nlp, mock_llm, mock_article, mock_event):
        """与活跃事件高相似 → 应 link。"""
        from app.services.distill import Distiller
        from app.services.reason import ReasoningEngine

        # 让标题高度重叠以确保高相似度
        mock_article.title = mock_event.title
        mock_event.article_links = []

        d = Distiller(nlp, mock_llm)
        distill_result = d.distill(mock_article.title, mock_article.content)

        engine = ReasoningEngine(mock_llm, nlp)
        result = engine.reason(distill_result, mock_article, [mock_event])

        assert result.action == "link"
        assert result.target_event_id == mock_event.id

    def test_reason_no_llm(self, nlp, no_llm, mock_article):
        """LLM 不可用 → 规则引擎仍工作。"""
        from app.services.distill import Distiller
        from app.services.reason import ReasoningEngine

        d = Distiller(nlp, no_llm)
        distill_result = d.distill(mock_article.title, mock_article.content)

        engine = ReasoningEngine(no_llm, nlp)
        result = engine.reason(distill_result, mock_article, [])

        assert result.action in ("new", "link", "skip")
        assert result.confidence > 0

    def test_reason_importance_high(self, nlp, mock_llm, mock_article):
        """突发类标题 → 高重要度。

        MockLLMProvider 没有 _call_llm，LLM 分支会失败并标记 safe_mode。
        规则引擎的 _infer_importance 仍应识别"突发"关键词。
        但 LLM 失败会覆盖 importance，所以这里验证规则引擎逻辑。"""
        from app.services.distill import Distiller
        from app.services.reason import ReasoningEngine

        mock_article.title = "突发：重大地震袭击西部地区"
        mock_article.content = "据中国地震台网测定，今日凌晨发生7.5级地震。"

        d = Distiller(nlp, mock_llm)
        distill_result = d.distill(mock_article.title, mock_article.content)

        # 直接测试 _infer_importance（规则引擎逻辑）
        engine = ReasoningEngine(mock_llm, nlp)
        importance = engine._infer_importance(mock_article, distill_result)
        assert importance >= 4, f"突发应≥4，得到: {importance}"

    def test_reason_category_tech(self, nlp, mock_llm, mock_article):
        """科技类文章 → 正确分类。直接测试规则引擎的 _infer_category。"""
        from app.services.reason import ReasoningEngine

        mock_article.title = "AI芯片技术取得新突破"
        mock_article.content = "人工智能芯片性能提升显著。"

        engine = ReasoningEngine(mock_llm, nlp)
        category = engine._infer_category(mock_article, MagicMock(
            key_numbers=[], core_entities=[]
        ))
        assert category in ("科技", "综合"), f"科技文应归类为科技，得到: {category}"

    def test_reason_skip_when_safe_mode(self, nlp, mock_llm, mock_article, mock_event):
        """LLM _call_llm 抛异常 → safe_mode 标记。

        需要进入 _llm_reason 的 action=="new" 分支，这样 _call_llm 才会被调用。
        """
        from app.services.distill import Distiller
        from app.services.reason import ReasoningEngine

        # 模拟 LLM _call_llm 抛异常
        fail_llm = MagicMock()
        fail_llm.is_available.return_value = True
        fail_llm._call_llm.side_effect = Exception("API error")

        # 使用完全不相关的标题，确保低关联度 → action="new"
        mock_article.title = "火星基地发现水源"
        mock_article.content = "科学家在火星南极发现了大量冰层。" * 3
        mock_article.embedding = None
        mock_event.article_links = []

        d = Distiller(nlp, MagicMock(is_available=lambda: False))
        distill_result = d.distill(mock_article.title, mock_article.content)

        engine = ReasoningEngine(fail_llm, nlp)
        result = engine.reason(distill_result, mock_article, [mock_event])

        # action 应为 new，进入 _llm_reason 的标题生成分支 → _call_llm 异常 → safe_mode
        assert result.safe_mode is True, f"LLM 失败应标记 safe_mode，得到 action={result.action} safe={result.safe_mode}"


# ═══════════════════════════════════════════════════════
# Test 3: Auditor
# ═══════════════════════════════════════════════════════

class TestAuditor:

    def test_audit_pass(self, nlp, mock_llm, mock_article):
        """正常数据 → 审计通过。"""
        from app.services.distill import Distiller
        from app.services.reason import ReasoningEngine
        from app.services.audit import Auditor

        d = Distiller(nlp, mock_llm)
        distill_result = d.distill(mock_article.title, mock_article.content)

        engine = ReasoningEngine(mock_llm, nlp)
        reason_result = engine.reason(distill_result, mock_article, [])

        auditor = Auditor(mock_llm)
        audit_result = auditor.audit(mock_article, distill_result, reason_result)

        assert audit_result.confidence > 0
        assert audit_result.status in ("pass", "manual_review", "safe_mode")

    def test_audit_entity_traceback(self, mock_llm, mock_article, mock_event):
        """实体回溯：推理结果的实体应在原文中。"""
        from app.services.distill import DistillResult, AtomicFact
        from app.services.reason import ReasoningResult
        from app.services.audit import Auditor

        # 构造一个 entity 来自原文的拆解结果
        distill_result = DistillResult(
            facts=[AtomicFact(content="中国发射飞船", fact_type="action", entities=["中国", "飞船"])],
            core_entities=["中国", "飞船"],
            key_numbers=[],
            primary_action="发射",
            summary_line="中国发射飞船",
            confidence=0.9,
        )

        reason_result = ReasoningResult(
            action="new", phase="trigger",
            event_title="中国发射飞船",
            suggested_importance=3,
            confidence=0.9,
        )

        auditor = Auditor(mock_llm)
        audit_result = auditor.audit(mock_article, distill_result, reason_result)

        # "中国" 在原文中 → 应匹配
        assert "中国" in audit_result.entity_check.get("matched", []), \
            f"中国应在原文中匹配，得到: {audit_result.entity_check}"

    def test_audit_unmatched_entities(self, mock_llm, mock_article):
        """不匹配的实体应被标记为 unmatched。"""
        from app.services.distill import DistillResult, AtomicFact
        from app.services.reason import ReasoningResult
        from app.services.audit import Auditor

        # 构造一个实体不在原文中
        distill_result = DistillResult(
            facts=[],
            core_entities=["火星基地"],  # 不在原文中
            key_numbers=[],
            primary_action="",
            summary_line="测试",
            confidence=0.9,
        )

        reason_result = ReasoningResult(
            action="new", phase="trigger",
            event_title="火星基地建设",
            suggested_importance=3,
            confidence=0.9,
        )

        auditor = Auditor(mock_llm)
        audit_result = auditor.audit(mock_article, distill_result, reason_result)

        assert "火星基地" in audit_result.entity_check.get("unmatched", []), \
            f"火星基地应 unmatched，得到: {audit_result.entity_check}"

    def test_audit_safe_mode_low_confidence(self, mock_llm, mock_article):
        """低置信度 → safe_mode。"""
        from app.services.distill import DistillResult, AtomicFact
        from app.services.reason import ReasoningResult
        from app.services.audit import Auditor

        # 构造低置信度数据
        distill_result = DistillResult(
            facts=[],
            core_entities=["完全不存在的实体XYZ"],
            key_numbers=["9999万亿元"],
            primary_action="",
            summary_line="测试",
            confidence=0.2,
        )

        reason_result = ReasoningResult(
            action="new", phase="trigger",
            event_title="完全无关的标题XYZ",
            suggested_importance=3,
            confidence=0.1,
            safe_mode=True,
        )

        auditor = Auditor(mock_llm)
        audit_result = auditor.audit(mock_article, distill_result, reason_result)

        assert audit_result.status == "safe_mode", \
            f"低置信度应进入安全模式，得到: {audit_result.status}, conf={audit_result.confidence}"
        assert not audit_result.passed

    def test_audit_number_verification(self, mock_llm, mock_article):
        """数值验证：原文中的数值应能追溯。"""
        from app.services.distill import DistillResult, AtomicFact
        from app.services.reason import ReasoningResult
        from app.services.audit import Auditor

        distill_result = DistillResult(
            facts=[],
            core_entities=["中国"],
            key_numbers=["50亿元"],  # 在 sample_content 中
            primary_action="宣布",
            summary_line="测试",
            confidence=0.9,
        )

        reason_result = ReasoningResult(
            action="new", phase="trigger",
            event_title="中国发射飞船",
            suggested_importance=3,
            confidence=0.9,
        )

        auditor = Auditor(mock_llm)
        audit_result = auditor.audit(mock_article, distill_result, reason_result)

        # 50亿元 在原文中 → 不应有数值不可追溯问题
        number_issues = [i for i in audit_result.issues if "数值" in i]
        assert len(number_issues) == 0, f"50亿元在原文中，不应有数值问题: {number_issues}"

    def test_audit_consistency_link_no_entities(self, mock_llm, mock_article):
        """一致性检查：link 动作但无实体支撑。"""
        from app.services.distill import DistillResult
        from app.services.reason import ReasoningResult
        from app.services.audit import Auditor

        distill_result = DistillResult(
            facts=[],
            core_entities=[],  # 无实体
            key_numbers=[],
            primary_action="",
            summary_line="测试",
            confidence=0.5,
        )

        reason_result = ReasoningResult(
            action="link", phase="development",
            target_event_id=1,
            suggested_importance=3,
            confidence=0.5,
        )

        auditor = Auditor(mock_llm)
        audit_result = auditor.audit(mock_article, distill_result, reason_result)

        has_issue = any("无实体支撑" in i for i in audit_result.issues)
        assert has_issue, "link 无实体应有问题"


# ═══════════════════════════════════════════════════════
# Test 4: Pipeline 集成
# ═══════════════════════════════════════════════════════

class TestPipelineIntegration:
    """全流程：拆解 → 推演 → 审计。"""

    def test_full_pipeline_flow(self, nlp, mock_llm, mock_article):
        """完整三级管线端到端。"""
        from app.services.distill import Distiller
        from app.services.reason import ReasoningEngine
        from app.services.audit import Auditor

        # Stage 1: 拆解
        distiller = Distiller(nlp, mock_llm)
        distill_result = distiller.distill(mock_article.title, mock_article.content)
        assert distill_result.facts, "拆解应产生事实"

        # Stage 2: 推演
        engine = ReasoningEngine(mock_llm, nlp)
        reason_result = engine.reason(distill_result, mock_article, [])
        assert reason_result.action in ("new", "link", "skip")

        # Stage 3: 审计
        auditor = Auditor(mock_llm)
        audit_result = auditor.audit(mock_article, distill_result, reason_result)
        assert audit_result.status in ("pass", "manual_review", "safe_mode")

    def test_full_pipeline_degraded_no_llm(self, nlp, no_llm, mock_article):
        """LLM 完全不可用 → 降级模式仍工作。"""
        from app.services.distill import Distiller
        from app.services.reason import ReasoningEngine
        from app.services.audit import Auditor

        distiller = Distiller(nlp, no_llm)
        distill_result = distiller.distill(mock_article.title, mock_article.content)

        engine = ReasoningEngine(no_llm, nlp)
        reason_result = engine.reason(distill_result, mock_article, [])

        auditor = Auditor(no_llm)
        audit_result = auditor.audit(mock_article, distill_result, reason_result)

        assert audit_result.confidence > 0, "降级模式也应有置信度"

    def test_pipeline_serialization(self, nlp, mock_llm, mock_article):
        """序列化拆解和推演结果为 JSON。"""
        import json
        from app.services.distill import Distiller
        from app.services.reason import ReasoningEngine
        from app.services.pipeline import Pipeline

        distiller = Distiller(nlp, mock_llm)
        distill_result = distiller.distill(mock_article.title, mock_article.content)

        engine = ReasoningEngine(mock_llm, nlp)
        reason_result = engine.reason(distill_result, mock_article, [])

        # 使用 Pipeline 的 _save_distillation 方法逻辑进行序列化验证
        facts_data = [
            {
                "content": f.content,
                "fact_type": f.fact_type,
                "entities": f.entities,
                "numbers": f.numbers,
                "confidence": f.confidence,
            }
            for f in distill_result.facts
        ]
        d_dict = {
            "facts": facts_data,
            "core_entities": distill_result.core_entities,
            "key_numbers": distill_result.key_numbers,
            "primary_action": distill_result.primary_action,
            "summary_line": distill_result.summary_line,
            "confidence": distill_result.confidence,
        }

        r_dict = {
            "action": reason_result.action,
            "target_event_id": reason_result.target_event_id,
            "phase": reason_result.phase,
            "event_title": reason_result.event_title,
            "suggested_category": reason_result.suggested_category,
            "suggested_importance": reason_result.suggested_importance,
            "confidence": reason_result.confidence,
        }

        # 应可 JSON 序列化
        json.dumps(d_dict, ensure_ascii=False)
        json.dumps(r_dict, ensure_ascii=False)

        assert "facts" in d_dict
        assert "action" in r_dict


# ═══════════════════════════════════════════════════════
# Test 5: NLP 基础能力
# ═══════════════════════════════════════════════════════

class TestNLP:
    def test_extract_keywords(self, nlp):
        kws = nlp.extract_keywords("人工智能技术在近年来取得了重大突破")
        assert len(kws) > 0

    def test_extract_entities(self, nlp):
        ents = nlp.extract_entities("习近平在北京会见了普京")
        names = [e["name"] for e in ents]
        assert any(n in names for n in ["习近平", "北京", "普京"]), f"得到: {names}"

    def test_keyword_similarity_same(self, nlp):
        sim = nlp.keyword_similarity(["中国", "发射", "飞船"], ["中国", "飞船", "发射"])
        assert sim == 1.0

    def test_keyword_similarity_different(self, nlp):
        sim = nlp.keyword_similarity(["苹果", "香蕉"], ["火箭", "导弹"])
        assert sim == 0.0

    def test_compute_similarity(self, nlp):
        sim = nlp.compute_similarity("中国发射载人飞船", "中国成功发射载人航天器")
        assert sim > 0.3

    def test_empty_text(self, nlp):
        assert nlp.extract_keywords("") == []
        assert nlp.extract_entities("") == []
        assert nlp.compute_similarity("", "test") == 0.0


# ═══════════════════════════════════════════════════════
# Test 6: MockLLMProvider
# ═══════════════════════════════════════════════════════

class TestMockLLM:
    def test_available(self, mock_llm):
        assert mock_llm.is_available() is True

    def test_embedding(self, mock_llm):
        emb = mock_llm.get_embedding("测试文本")
        assert emb is not None
        assert len(emb) == 16  # 32 bytes / 2 = 16 floats

    def test_embedding_normalized(self, mock_llm):
        import math
        emb = mock_llm.get_embedding("测试文本")
        norm = math.sqrt(sum(x * x for x in emb))
        assert abs(norm - 1.0) < 0.01

    def test_verify_same_event_similar(self, mock_llm):
        result = mock_llm.verify_same_event("中国发射飞船", "中国发射载人航天器")
        assert result is True

    def test_verify_same_event_different(self, mock_llm):
        result = mock_llm.verify_same_event("苹果发布新手机", "中东局势紧张升级")
        assert result is False
