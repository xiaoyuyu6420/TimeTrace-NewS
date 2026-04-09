"""Test distillation with a real article to verify JSON parsing fix."""

import logging
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

from app.database import SessionLocal
from app.models import Article
from app.deps import get_llm, get_nlp
from app.services.distill import Distiller

db = SessionLocal()

# Get a recent article
article = db.query(Article).order_by(Article.id.desc()).first()
if not article:
    print("No articles found")
    exit(1)

print("=" * 80)
print("  Testing Distillation Fix")
print("=" * 80)
print(f"\nArticle #{article.id}: {article.title[:80]}")
print(f"Content length: {len(article.content) if article.content else 0} chars")
print(f"Current state: {article.pipeline_state}")

# Initialize distiller - use role-based LLM from DB routing
from app.deps import get_role_llm
db2 = SessionLocal()
distill_llm = get_role_llm(db2, 'distill')
nlp = get_nlp()
distiller = Distiller(nlp, distill_llm)

print(f"\nDistiller initialized:")
print(f"  LLM: {distill_llm.__class__.__name__} (model: {distill_llm._model if hasattr(distill_llm, '_model') else 'N/A'})")
print(f"  LLM available: {distill_llm.is_available()}")
print(f"  NLP: {nlp.__class__.__name__}")

print("\n" + "-" * 80)
print("  Running Distillation...")
print("-" * 80)

result = distiller.distill(article.title or "", article.content or "")

print("\n" + "=" * 80)
print("  Distillation Result")
print("=" * 80)
print(f"\nModel used: {result.model_used}")
print(f"Confidence: {result.confidence}")
print(f"LLM generated: {result.is_llm_generated}")
print(f"Processing time: {result.processing_time_ms}ms")
print(f"\nFacts extracted: {len(result.facts)}")
for i, fact in enumerate(result.facts[:5], 1):
    print(f"  {i}. [{fact.fact_type}] {fact.content[:80]}")

print(f"\nCore entities: {len(result.core_entities)}")
for entity in result.core_entities[:5]:
    print(f"  - {entity}")

print(f"\nKey numbers: {len(result.key_numbers)}")
for num in result.key_numbers[:5]:
    print(f"  - {num}")

print(f"\nPrimary action: {result.primary_action}")
print(f"Summary: {result.summary_line[:100]}")

db.close()
