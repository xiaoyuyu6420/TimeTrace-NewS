"""统一处理管线 — 爬取 → 拆解 → 推演 → 审计 → 入库。

三级管线架构：
  Distiller（小模型拆解）→ ReasoningEngine（大模型推演）→ Auditor（审计验证）

Day 1 模式：从部署当天开始采集，不导入历史数据。
每篇文章入库时必须经过关联度判定，决定是增量更新还是新事件。
"""

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Article, ArticleDistillation, ArticleReasoning, AuditLog, Event, EventArticle

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """单次管线运行的结果。"""
    crawled: int = 0
    distilled: int = 0       # 拆解完成
    reasoned: int = 0        # 推演完成
    audited: int = 0         # 审计通过
    linked: int = 0          # 关联到已有事件
    new_events: int = 0      # 创建的新事件
    manual_review: int = 0   # 需要人工审核
    safe_mode: int = 0       # 安全模式
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class Pipeline:
    """统一数据管线。

    设计原则：
    - Day 1 模式：不依赖历史数据，从空库开始也能正常运转
    - 三级管线：Distiller → ReasoningEngine → Auditor
    - 并行调度：多篇文章同时处理，每篇内部串行
    - 多级兜底：LLM 失败 → 规则引擎；审计不通过 → 安全模式
    - 幂等性：重复运行不会产生重复数据
    """

    # ─── 并行度 ───
    MAX_WORKERS = 4

    def __init__(self, db: Session, llm, nlp):
        self._db = db
        self._llm = llm
        self._nlp = nlp

    def run(self, skip_crawl: bool = False) -> PipelineResult:
        """执行完整管线：爬取 → 拆解 → 推演 → 审计 → 入库。

        Args:
            skip_crawl: True 时跳过爬取，只处理已有的 raw 文章。
        """
        start = datetime.now(timezone.utc)
        logger.info(f"=== Pipeline started (skip_crawl={skip_crawl}) ===")

        # 使用局部变量 + 线程锁，避免实例状态并发问题
        result = PipelineResult()
        lock = threading.Lock()

        def _add_error(msg: str):
            with lock:
                result.errors.append(msg)

        # Stage 1: 爬取（可选跳过）
        if not skip_crawl:
            self._stage_crawl(result)

        # Stage 2: 三级管线处理（拆解 → 推演 → 审计）
        self._stage_pipeline(result, lock)

        # Stage 3: LLM 精炼（选择性）
        self._stage_enhance(result)

        # 自动关闭超时事件
        self._auto_close_stale()

        result.duration_seconds = (datetime.now(timezone.utc) - start).total_seconds()
        logger.info(
            f"=== Pipeline done in {result.duration_seconds:.1f}s: "
            f"crawled={result.crawled} distilled={result.distilled} "
            f"reasoned={result.reasoned} audited={result.audited} "
            f"linked={result.linked} new={result.new_events} "
            f"review={result.manual_review} safe={result.safe_mode} ==="
        )
        return result

    # ─── Stage 1: 爬取 ─────────────────────────────

    def _stage_crawl(self, result: PipelineResult):
        """爬取所有活跃 RSS 源。"""
        try:
            from .crawl import CrawlService
            crawl_svc = CrawlService(self._db, self._llm, self._nlp)
            crawl_result = crawl_svc.crawl_all_active()
            result.crawled = crawl_result.get("total_new", 0)
            logger.info(f"Stage 1 (crawl): {result.crawled} new articles")
        except Exception as e:
            result.errors.append(f"crawl: {e}")
            logger.error(f"Stage 1 failed: {e}")

    # ─── Stage 2: 三级管线 ─────────────────────────

    def _stage_pipeline(self, result: PipelineResult, lock: threading.Lock):
        """三级管线：拆解 → 推演 → 审计，多篇文章并行处理。"""
        # 获取未处理的文章（pipeline_state = 'raw'）
        raw_articles = self._find_raw_articles(limit=100)
        if not raw_articles:
            logger.info("Stage 2 (pipeline): no raw articles")
            return

        # 获取近期活跃事件（30天窗口）
        active_events = self._find_active_events()

        # 并行处理
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures = {}
            for article in raw_articles:
                future = executor.submit(
                    self._process_article, article, active_events, result, lock
                )
                futures[future] = article.id

            for future in as_completed(futures):
                article_id = futures[future]
                try:
                    future.result()
                except Exception as e:
                    with lock:
                        result.errors.append(f"article {article_id}: {e}")
                    logger.warning(f"Failed to process article {article_id}: {e}")

        logger.info(
            f"Stage 2 (pipeline): distilled={result.distilled} "
            f"reasoned={result.reasoned} audited={result.audited} "
            f"linked={result.linked} new={result.new_events} "
            f"review={result.manual_review} safe={result.safe_mode}"
        )

    def _process_article(self, article: Article, active_events: list,
                         result: PipelineResult, lock: threading.Lock):
        """对单篇文章执行三级管线：拆解 → 推演 → 审计。

        每篇文章使用独立的数据库 Session 以避免并发冲突。
        使用线程锁保护共享 result 计数器。
        """
        db = None
        try:
            from ..database import SessionLocal
            db = SessionLocal()

            # 初始化三级引擎 — 从编排配置获取分角色 LLM
            from .distill import Distiller
            from .reason import ReasoningEngine
            from .audit import Auditor
            from ..deps import get_role_llm

            distill_llm = get_role_llm(db, "distill")
            reason_llm = get_role_llm(db, "reason")
            audit_llm = get_role_llm(db, "audit")

            distiller = Distiller(self._nlp, distill_llm)
            reasoner = ReasoningEngine(reason_llm, self._nlp)
            auditor = Auditor(audit_llm)

            # ─── 2a: 拆解 ───
            distill_record = None
            try:
                distill_result = distiller.distill(
                    article.title or "",
                    article.content or ""
                )
                # 写入蒸馏产物表
                distill_record = self._save_distillation(db, article.id, distill_result)
                article.pipeline_state = "distilled"
                db.commit()
                with lock:
                    result.distilled += 1
            except Exception as e:
                logger.warning(f"Distill failed for article {article.id}: {e}")
                article.pipeline_state = "safe_mode"
                db.commit()
                with lock:
                    result.safe_mode += 1
                self._write_audit_log(db, article.id, None, "distill", "safe_mode", 0.0, [], [str(e)])
                return

            # 重新加载活跃事件（从独立 session）
            events = self._find_active_events_in_session(db)

            # ─── 2b: 推演 ───
            reason_record = None
            try:
                reasoning_result = reasoner.reason(distill_result, article, events)
                # 写入推演产物表
                reason_record = self._save_reasoning(
                    db, article.id, distill_record.id if distill_record else None,
                    reasoning_result
                )
                article.pipeline_state = "reasoned"
                db.commit()
                with lock:
                    result.reasoned += 1
            except Exception as e:
                logger.warning(f"Reason failed for article {article.id}: {e}")
                article.pipeline_state = "safe_mode"
                db.commit()
                with lock:
                    result.safe_mode += 1
                self._write_audit_log(db, article.id, None, "reason", "safe_mode", 0.0, [], [str(e)])
                return

            # ─── 2c: 审计 ───
            try:
                audit_result = auditor.audit(article, distill_result, reasoning_result)
                with lock:
                    result.audited += 1

                if audit_result.status == "pass":
                    # 审计通过 → 执行入库
                    article.pipeline_state = "audited"
                    self._apply_reasoning(db, article, reasoning_result, events, result, lock)
                    self._write_audit_log(
                        db, article.id, reasoning_result.target_event_id,
                        "audit", "pass", audit_result.confidence,
                        audit_result.issues, audit_result.entity_check
                    )
                    db.commit()

                elif audit_result.status == "manual_review":
                    # 需要人工审核 → 仍然入库但标记
                    article.pipeline_state = "audited"
                    self._apply_reasoning(db, article, reasoning_result, events, result, lock)
                    with lock:
                        result.manual_review += 1
                    self._write_audit_log(
                        db, article.id, reasoning_result.target_event_id,
                        "audit", "manual_review", audit_result.confidence,
                        audit_result.issues, audit_result.entity_check
                    )
                    db.commit()

                else:
                    # 安全模式 → 仅保存原始标题和摘要
                    article.pipeline_state = "safe_mode"
                    with lock:
                        result.safe_mode += 1
                    self._write_audit_log(
                        db, article.id, reasoning_result.target_event_id,
                        "audit", "safe_mode", audit_result.confidence,
                        audit_result.issues, audit_result.entity_check
                    )
                    db.commit()

            except Exception as e:
                logger.warning(f"Audit failed for article {article.id}: {e}")
                article.pipeline_state = "safe_mode"
                db.commit()
                with lock:
                    result.safe_mode += 1
                self._write_audit_log(db, article.id, None, "audit", "safe_mode", 0.0, [], [str(e)])

        except Exception as e:
            logger.error(f"Pipeline processing error for article {getattr(article, 'id', '?')}: {e}")
            with lock:
                result.errors.append(f"process: {e}")
        finally:
            if db:
                db.close()

    def _apply_reasoning(self, db: Session, article: Article, reasoning_result,
                         active_events: list, result: PipelineResult, lock: threading.Lock):
        """根据推演结果将文章关联到事件或创建新事件。"""
        if reasoning_result.action == "link" and reasoning_result.target_event_id:
            # 关联到已有事件
            event = db.query(Event).filter(Event.id == reasoning_result.target_event_id).first()
            if event:
                self._link_to_event(db, article, event, reasoning_result)
                with lock:
                    result.linked += 1
                return

        # 新事件
        self._create_new_event(db, article, reasoning_result, active_events)
        with lock:
            result.new_events += 1

    def _link_to_event(self, db: Session, article: Article, event: Event, reasoning_result):
        """将文章关联到事件。"""
        # 检查是否已关联
        existing = db.query(EventArticle).filter(
            EventArticle.event_id == event.id,
            EventArticle.article_id == article.id,
        ).first()
        if existing:
            return

        phase = reasoning_result.phase or "development"
        link = EventArticle(
            event_id=event.id,
            article_id=article.id,
            relevance_score=reasoning_result.confidence,
            phase=phase,
        )
        db.add(link)

        # 更新事件时间范围
        if article.published_at:
            if not event.start_date or article.published_at < event.start_date:
                event.start_date = article.published_at
            if not event.end_date or article.published_at > event.end_date:
                event.end_date = article.published_at
        event.updated_at = datetime.now(timezone.utc)

    def _create_new_event(self, db: Session, article: Article, reasoning_result, active_events: list):
        """为文章创建新事件。"""
        event = Event(
            title=reasoning_result.event_title or article.title,
            summary=reasoning_result.event_summary or (article.content[:200] if article.content else ""),
            category=reasoning_result.suggested_category or "",
            importance=reasoning_result.suggested_importance or 3,
            embedding=article.embedding,
            start_date=article.published_at,
            end_date=article.published_at,
        )
        db.add(event)
        db.flush()  # 获取 event.id

        link = EventArticle(
            event_id=event.id,
            article_id=article.id,
            relevance_score=1.0,
            phase="trigger",
        )
        db.add(link)

    # ─── Stage 3: LLM 精炼 ─────────────────────────

    def _stage_enhance(self, result: PipelineResult):
        """对满足条件的事件执行 LLM 精炼（标题+摘要）。"""
        if not self._llm or not self._llm.is_available():
            return

        try:
            from .timeline import TimelineService
            timeline_svc = TimelineService(self._db, self._llm, self._nlp)

            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            candidates = (
                self._db.query(Event)
                .filter(Event.status == "active", Event.updated_at >= cutoff)
                .all()
            )

            for event in candidates:
                try:
                    # Fix: ensure event.updated_at is timezone-aware for comparison
                    event_updated = event.updated_at
                    if event_updated and event_updated.tzinfo is None:
                        event_updated = event_updated.replace(tzinfo=timezone.utc)
                    
                    if event_updated and event_updated >= cutoff:
                        if timeline_svc.should_enhance(event):
                            timeline_svc.enhance_event(event)
                except Exception as e:
                    logger.warning(f"Enhance event {event.id} failed: {e}")
        except Exception as e:
            result.errors.append(f"enhance: {e}")
            logger.error(f"Stage 3 (enhance) failed: {e}")

    # ─── 审计日志 ───────────────────────────────────

    def _write_audit_log(self, db: Session, article_id: int, event_id: int | None,
                         stage: str, status: str, confidence: float,
                         issues: list, entity_check):
        """写入审计日志。"""
        try:
            log = AuditLog(
                article_id=article_id,
                event_id=event_id,
                stage=stage,
                status=status,
                confidence=confidence,
                issues=issues if issues else None,
                entity_check=entity_check if isinstance(entity_check, dict) else None,
            )
            db.add(log)
            # 不 commit，由调用方统一 commit
        except Exception as e:
            logger.warning(f"Failed to write audit log: {e}")

    # ─── 写入独立表 ────────────────────────────────

    @staticmethod
    def _save_distillation(db: Session, article_id: int, distill_result) -> ArticleDistillation:
        """将蒸馏结果写入独立表。如果已存在则更新。"""
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

        existing = db.query(ArticleDistillation).filter(
            ArticleDistillation.article_id == article_id
        ).first()

        if existing:
            existing.facts = facts_data
            existing.core_entities = distill_result.core_entities
            existing.key_numbers = distill_result.key_numbers
            existing.primary_action = distill_result.primary_action
            existing.summary_line = distill_result.summary_line
            existing.confidence = distill_result.confidence
            existing.model_used = distill_result.model_used
            existing.is_llm_generated = distill_result.is_llm_generated
            existing.processing_time_ms = distill_result.processing_time_ms
            db.flush()
            return existing

        record = ArticleDistillation(
            article_id=article_id,
            facts=facts_data,
            core_entities=distill_result.core_entities,
            key_numbers=distill_result.key_numbers,
            primary_action=distill_result.primary_action,
            summary_line=distill_result.summary_line,
            confidence=distill_result.confidence,
            model_used=distill_result.model_used,
            is_llm_generated=distill_result.is_llm_generated,
            processing_time_ms=distill_result.processing_time_ms,
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def _save_reasoning(db: Session, article_id: int, distillation_id: int | None,
                        reasoning_result) -> ArticleReasoning:
        """将推演结果写入独立表。如果已存在则更新。"""
        existing = db.query(ArticleReasoning).filter(
            ArticleReasoning.article_id == article_id
        ).first()

        if existing:
            existing.distillation_id = distillation_id
            existing.action = reasoning_result.action
            existing.target_event_id = reasoning_result.target_event_id
            existing.target_event_title = reasoning_result.target_event_title
            existing.phase = reasoning_result.phase
            existing.suggested_category = reasoning_result.suggested_category
            existing.suggested_importance = reasoning_result.suggested_importance
            existing.event_title = reasoning_result.event_title
            existing.event_summary = reasoning_result.event_summary
            existing.has_conflict = reasoning_result.has_conflict
            existing.conflict_details = reasoning_result.conflict_details
            existing.confidence = reasoning_result.confidence
            existing.needs_review = reasoning_result.needs_review
            existing.safe_mode = reasoning_result.safe_mode
            db.flush()
            return existing

        record = ArticleReasoning(
            article_id=article_id,
            distillation_id=distillation_id,
            action=reasoning_result.action,
            target_event_id=reasoning_result.target_event_id,
            target_event_title=reasoning_result.target_event_title,
            phase=reasoning_result.phase,
            suggested_category=reasoning_result.suggested_category,
            suggested_importance=reasoning_result.suggested_importance,
            event_title=reasoning_result.event_title,
            event_summary=reasoning_result.event_summary,
            has_conflict=reasoning_result.has_conflict,
            conflict_details=reasoning_result.conflict_details,
            confidence=reasoning_result.confidence,
            needs_review=reasoning_result.needs_review,
            safe_mode=reasoning_result.safe_mode,
        )
        db.add(record)
        db.flush()
        return record

    # ─── 查询辅助 ──────────────────────────────────

    def _find_raw_articles(self, limit: int = 100) -> list[Article]:
        """获取未处理的文章。"""
        return (
            self._db.query(Article)
            .filter(Article.pipeline_state == "raw")
            .order_by(Article.published_at.desc())
            .limit(limit)
            .all()
        )

    def _find_active_events(self) -> list[Event]:
        """获取近30天的活跃事件（主 session）。"""
        window = datetime.now(timezone.utc) - timedelta(days=30)
        from sqlalchemy.orm import joinedload
        return (
            self._db.query(Event)
            .filter(Event.status == "active", Event.updated_at >= window)
            .options(joinedload(Event.article_links).joinedload(EventArticle.article))
            .all()
        )

    @staticmethod
    def _find_active_events_in_session(db: Session) -> list[Event]:
        """获取近30天的活跃事件（指定 session）。"""
        window = datetime.now(timezone.utc) - timedelta(days=30)
        from sqlalchemy.orm import joinedload
        return (
            db.query(Event)
            .filter(Event.status == "active", Event.updated_at >= window)
            .options(joinedload(Event.article_links).joinedload(EventArticle.article))
            .all()
        )

    def _auto_close_stale(self):
        """自动关闭超过14天无更新的活跃事件。"""
        threshold = datetime.now(timezone.utc) - timedelta(days=14)
        stale = self._db.query(Event).filter(
            Event.status == "active", Event.updated_at < threshold
        ).all()
        for event in stale:
            event.status = "resolved"
        if stale:
            self._db.commit()
            logger.info(f"Auto-closed {len(stale)} stale events")
