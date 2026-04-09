"""Timeline service - 构建事件生命周期时间线 + 阶段标注 + LLM精炼。"""

import logging
from datetime import datetime, timezone
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..models import Article, Event, EventArticle
from ..schemas import TimelinePhase, ArticleOut

logger = logging.getLogger(__name__)

# 阶段标签映射
PHASE_LABELS = {
    "trigger": "起因",
    "development": "经过",
    "outcome": "结果",
    "followup": "后续",
}

# 结果关键词库（命中即判定为 outcome）
OUTCOME_KEYWORDS = {
    "宣布", "决定", "通过", "批准", "签署", "发布", "出台",
    "结果", "判决", "裁定", "闭幕", "落幕", "终止", "结束",
    "达成", "共识", "协议", "和解", "妥协",
    "破案", "获救", "脱险", "遇难", "去世", "身亡",
    "最终", "定论", "证实", "确认", "澄清",
}


def determine_phase(event, article, existing_count: int) -> str:
    """根据规则判断文章在事件中的阶段。无需 LLM。"""
    title = article.title or ""

    # 已关闭事件的新报道 → 后续
    if event.status == "resolved":
        return "followup"

    # 结果关键词检测
    if any(kw in title for kw in OUTCOME_KEYWORDS):
        return "outcome"

    # 事件初期 → 起因
    if existing_count <= 1:
        return "trigger"

    return "development"


class TimelineService:
    """时间线构建 + 事件精炼服务。"""

    def __init__(self, db: Session, llm, nlp):
        self._db = db
        self._llm = llm
        self._nlp = nlp

    def build_timeline(self, event_id: int) -> list[TimelinePhase]:
        """构建事件的阶段时间线。按 phase 分组，每组内按时间排序。"""
        links = (
            self._db.query(EventArticle, Article)
            .join(Article, EventArticle.article_id == Article.id)
            .filter(EventArticle.event_id == event_id)
            .order_by(Article.published_at.asc())
            .all()
        )

        if not links:
            return []

        # 按 phase 分组
        phase_groups: dict[str, list[ArticleOut]] = defaultdict(list)
        phase_dates: dict[str, str] = {}

        for link, article in links:
            phase = link.phase or "development"
            article_out = ArticleOut(
                id=article.id,
                title=article.title,
                content=article.content or "",
                summary=article.summary or "",
                source_url=article.source_url or "",
                keywords=article.keywords or [],
                entities=article.entities or [],
                rss_source_id=article.rss_source_id,
                rss_source_name=article.rss_source.name if article.rss_source else "",
                credibility_score=article.credibility_score or 0.0,
                published_at=article.published_at,
                created_at=article.created_at,
            )
            phase_groups[phase].append(article_out)

            # 记录每个阶段的首个日期
            if phase not in phase_dates and article.published_at:
                phase_dates[phase] = article.published_at.strftime("%Y-%m-%d")

        # 按 phase 顺序排列
        phase_order = ["trigger", "development", "outcome", "followup"]
        result = []
        for phase in phase_order:
            if phase in phase_groups:
                result.append(TimelinePhase(
                    phase=phase,
                    phase_label=PHASE_LABELS.get(phase, phase),
                    date=phase_dates.get(phase),
                    articles=phase_groups[phase],
                ))

        return result

    def should_enhance(self, event: Event) -> bool:
        """判断事件是否需要 LLM 精炼。"""
        if not self._llm.is_available():
            return False

        # 从未精炼过
        if event.last_enhanced_at is None:
            # 至少有 3 篇文章且创建超过 1 小时
            count = (
                self._db.query(func.count(EventArticle.article_id))
                .filter(EventArticle.event_id == event.id)
                .scalar() or 0
            )
            if count >= 3:
                return True
            if count >= 1 and event.created_at:
                # Fix: handle both timezone-aware and naive datetimes
                created_at = event.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - created_at).total_seconds()
                if age > 3600:  # 1 小时
                    return True
            return False

        # 上次精炼后新增了 5+ 篇文章
        new_count = (
            self._db.query(func.count(EventArticle.article_id))
            .filter(
                EventArticle.event_id == event.id,
                EventArticle.article_id.in_(
                    self._db.query(Article.id)
                    .filter(Article.created_at > event.last_enhanced_at)
                )
            )
            .scalar() or 0
        )
        if new_count >= 5:
            return True

        return False

    def enhance_event(self, event: Event) -> None:
        """用 LLM 精炼事件标题和摘要。成本控制：仅在满足条件时调用。"""
        if not self._llm.is_available():
            return

        links = (
            self._db.query(Article)
            .join(EventArticle, EventArticle.article_id == Article.id)
            .filter(EventArticle.event_id == event.id)
            .order_by(Article.published_at.asc())
            .limit(15)
            .all()
        )

        if not links:
            return

        titles = [a.title for a in links if a.title]
        if not titles:
            return

        # 生成事件标题
        new_title = self._llm.generate_event_title(titles)
        if new_title:
            event.title = new_title

        # 生成叙述性摘要（起因+经过+结果）
        timeline_text = "\n".join(
            f"[{a.published_at.strftime('%m/%d') if a.published_at else '?'}] {a.title}"
            for a in links[:10]
        )
        prompt = f"根据以下时间线新闻标题，用3-5句话描述事件的起因、经过和结果：\n\n{timeline_text}"
        narrative = self._llm._call_llm(prompt)
        if narrative:
            event.summary = narrative

        event.last_enhanced_at = datetime.now(timezone.utc)
        self._db.commit()
        logger.info(f"Enhanced event #{event.id}: {event.title}")
