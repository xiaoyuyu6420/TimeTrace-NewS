"""Run the complete pipeline end-to-end with detailed terminal-like logging."""

import logging
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from datetime import datetime, timezone

# Configure logging to output to stdout like a terminal
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stdout,
)

logger = logging.getLogger("PipelineRunner")


def print_header(text: str):
    """Print a formatted section header."""
    width = 80
    print("\n" + "=" * width)
    print(f"  {text}")
    print("=" * width)


def print_section(text: str):
    """Print a formatted subsection header."""
    width = 80
    print("\n" + "-" * width)
    print(f"  {text}")
    print("-" * width)


def print_step(text: str):
    """Print a step in the process."""
    print(f"  → {text}")


def print_result(text: str):
    """Print a result."""
    print(f"  [OK] {text}")


def print_error(text: str):
    """Print an error."""
    print(f"  [ERR] {text}")


def main():
    print_header("TimeTrace — Complete Pipeline Run")
    print(f"  Start Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Mode: Fresh data collection from active RSS sources")

    # ─── Step 1: Database Setup ────────────────────────────────
    print_section("Step 1: Database Initialization")
    
    from app.database import SessionLocal
    from app.models import RssSource, Article, Event, ArticleDistillation, ArticleReasoning, AuditLog
    from app.models import LlmProvider, LlmModel, EmbedProvider, EmbedModel, LlmRouting
    
    db = SessionLocal()
    print_step("Database session created")
    
    # Check RSS sources
    active_sources = db.query(RssSource).filter(RssSource.is_active == True).all()
    all_sources = db.query(RssSource).all()
    print_result(f"Active RSS sources: {len(active_sources)} / {len(all_sources)} total")
    for s in active_sources:
        print(f"    - {s.name} ({s.category}) — {s.url}")
    
    # Check articles
    total_articles = db.query(Article).count()
    raw_articles = db.query(Article).filter(Article.pipeline_state == "raw").count()
    print_result(f"Articles in DB: {total_articles} total, {raw_articles} raw (unprocessed)")
    
    # Check events
    total_events = db.query(Event).count()
    active_events = db.query(Event).filter(Event.status == "active").count()
    print_result(f"Events in DB: {total_events} total, {active_events} active")

    # ─── Step 2: LLM/Embedding Configuration ───────────────────
    print_section("Step 2: LLM & Embedding Configuration")
    
    routing = db.query(LlmRouting).first()
    if routing:
        print_step("LLM Routing Configuration:")
        
        # Distill model
        if routing.distill_model_id:
            model = db.query(LlmModel).filter(LlmModel.id == routing.distill_model_id).first()
            if model:
                provider = db.query(LlmProvider).filter(LlmProvider.id == model.provider_id).first()
                print(f"    Distill: {model.name} via {provider.name} ({provider.api_base[:50]}...)")
        
        # Reason model
        if routing.reason_model_id:
            model = db.query(LlmModel).filter(LlmModel.id == routing.reason_model_id).first()
            if model:
                provider = db.query(LlmProvider).filter(LlmProvider.id == model.provider_id).first()
                print(f"    Reason:  {model.name} via {provider.name} ({provider.api_base[:50]}...)")
        
        # Audit model
        if routing.audit_model_id:
            model = db.query(LlmModel).filter(LlmModel.id == routing.audit_model_id).first()
            if model:
                provider = db.query(LlmProvider).filter(LlmProvider.id == model.provider_id).first()
                print(f"    Audit:   {model.name} via {provider.name} ({provider.api_base[:50]}...)")
        
        # Embed model
        if routing.embed_model_id:
            model = db.query(EmbedModel).filter(EmbedModel.id == routing.embed_model_id).first()
            if model:
                provider = db.query(EmbedProvider).filter(EmbedProvider.id == model.provider_id).first()
                print(f"    Embed:   {model.name} via {provider.name} ({provider.api_base[:50]}...)")
    else:
        print_error("No LLM routing configuration found!")
    
    db.close()

    # ─── Step 3: Run Pipeline ──────────────────────────────────
    print_section("Step 3: Running Complete Pipeline")
    
    from app.database import SessionLocal as create_db
    from app.deps import get_pipeline, get_llm, get_nlp
    
    db = create_db()
    llm = get_llm()
    nlp = get_nlp()
    
    print_step(f"LLM Provider: {llm.__class__.__name__}")
    print_step(f"NLP Processor: {nlp.__class__.__name__}")
    
    # Create pipeline
    pipeline = get_pipeline(db)
    
    print_step("Starting pipeline execution...")
    print("(This may take a while depending on RSS feed size and LLM response times)")
    
    # Run the pipeline
    try:
        result = pipeline.run(skip_crawl=False)
        
        print_section("Pipeline Results")
        print_result(f"Crawled:      {result.crawled} new articles")
        print_result(f"Distilled:    {result.distilled} articles")
        print_result(f"Reasoned:     {result.reasoned} articles")
        print_result(f"Audited:      {result.audited} articles")
        print_result(f"Linked:       {result.linked} to existing events")
        print_result(f"New Events:   {result.new_events} created")
        print_result(f"Manual Review: {result.manual_review} articles")
        print_result(f"Safe Mode:    {result.safe_mode} articles")
        print_result(f"Duration:     {result.duration_seconds:.1f} seconds")
        
        if result.errors:
            print_error(f"Errors ({len(result.errors)}):")
            for err in result.errors:
                print(f"    • {err}")
        
    except Exception as e:
        print_error(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return

    # ─── Step 4: Verify Results ────────────────────────────────
    print_section("Step 4: Verifying Results")
    
    # Refresh session
    db.expire_all()
    
    # Check new articles
    new_total = db.query(Article).count()
    new_raw = db.query(Article).filter(Article.pipeline_state == "raw").count()
    new_distilled = db.query(Article).filter(Article.pipeline_state == "distilled").count()
    new_reasoned = db.query(Article).filter(Article.pipeline_state == "reasoned").count()
    new_audited = db.query(Article).filter(Article.pipeline_state == "audited").count()
    new_safe = db.query(Article).filter(Article.pipeline_state == "safe_mode").count()
    
    print_result(f"Article States:")
    print(f"    Raw:       {new_raw}")
    print(f"    Distilled: {new_distilled}")
    print(f"    Reasoned:  {new_reasoned}")
    print(f"    Audited:   {new_audited}")
    print(f"    Safe Mode: {new_safe}")
    
    # Check events
    new_events = db.query(Event).filter(Event.status == "active").all()
    print_result(f"Active Events: {len(new_events)}")
    
    for event in new_events[:10]:  # Show first 10
        article_count = db.query(Article).filter(
            Article.event_links.any()
        ).count()
        
        print(f"\n    Event #{event.id}: {event.title}")
        print(f"      Category: {event.category}")
        print(f"      Importance: {event.importance}/5")
        print(f"      Status: {event.status}")
        print(f"      Articles: {len(event.article_links)}")
        
        # Show distillation details for linked articles
        for link in event.article_links[:3]:  # First 3 articles
            article = link.article
            print(f"\n      Article: {article.title[:80]}")
            print(f"        Source: {article.rss_source.name if article.rss_source else 'N/A'}")
            print(f"        Published: {article.published_at}")
            print(f"        Phase: {link.phase}")
            print(f"        Keywords: {', '.join(article.keywords[:5]) if article.keywords else 'N/A'}")
            
            # Show distillation
            distill = db.query(ArticleDistillation).filter(
                ArticleDistillation.article_id == article.id
            ).first()
            if distill:
                print(f"        Distilled: {len(distill.facts)} facts, {len(distill.core_entities)} entities")
                print(f"        Model: {distill.model_used}")
                print(f"        Entities: {', '.join(distill.core_entities[:5])}")
            
            # Show reasoning
            reasoning = db.query(ArticleReasoning).filter(
                ArticleReasoning.article_id == article.id
            ).first()
            if reasoning:
                print(f"        Reasoned: action={reasoning.action}, phase={reasoning.phase}")
                print(f"        Confidence: {reasoning.confidence:.2f}")
    
    # Check audit logs
    audit_count = db.query(AuditLog).count()
    print(f"\n    Audit Logs: {audit_count} entries")
    
    # Show recent audit logs
    recent_logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(5).all()
    if recent_logs:
        print("\n    Recent Audit Logs:")
        for log in recent_logs:
            article = db.query(Article).filter(Article.id == log.article_id).first()
            print(f"      [{log.stage}] Article #{log.article_id} — {log.status} (confidence: {log.confidence:.2f})")
            if article:
                print(f"        Title: {article.title[:60]}")
            if log.issues:
                print(f"        Issues: {', '.join(log.issues[:2])}")

    # ─── Step 5: Summary ───────────────────────────────────────
    print_header("Pipeline Run Complete")
    print(f"  End Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Duration: {result.duration_seconds:.1f} seconds")
    print(f"  Articles Processed: {result.crawled} crawled, {result.distilled} distilled, {result.audited} audited")
    print(f"  Events Created/Updated: {result.new_events} new, {result.linked} linked")
    
    if result.errors:
        print(f"\n  [WARN] {len(result.errors)} errors occurred")
        for err in result.errors:
            print(f"    - {err}")
    else:
        print(f"\n  [OK] No errors encountered")
    
    print("\n  Next Steps:")
    print("    • Check frontend at http://localhost:5173 to view events")
    print("    • Run again to collect more data")
    print("    • Check admin panel at /admin/pipeline for visualization")
    
    db.close()


if __name__ == "__main__":
    main()
