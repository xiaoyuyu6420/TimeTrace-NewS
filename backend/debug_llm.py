"""Debug LLM response to understand JSON parsing issue."""

import logging
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s: %(message)s')

from app.deps import get_llm
from app.services.distill import Distiller, _DISTILL_PROMPT

llm = get_llm()

# Test article
title = "三安光电：公司可提供用于光模块的激光器等产品，目前高速产品已实现批量出货"
content = "36氪获悉，三安光电在互动平台回复称，公司可提供用于光模块的激光器、探测器产品，目前高速产品已实现批量出货，客户以国内为主。"

prompt = _DISTILL_PROMPT.format(title=title, content=content[:1500])

print("=" * 80)
print("  Testing LLM Response")
print("=" * 80)
print(f"\nPrompt (first 200 chars):\n{prompt[:200]}...")

print("\n" + "-" * 80)
print("  Calling LLM...")
print("-" * 80)

response = llm._call_llm(prompt, max_tokens_override=2000)

print("\n" + "=" * 80)
print("  LLM Raw Response")
print("=" * 80)
if response:
    print(f"\nLength: {len(response)} chars")
    print(f"\nFull response:\n{response}")
    
    # Try to extract JSON
    print("\n" + "-" * 80)
    print("  JSON Extraction")
    print("-" * 80)
    
    parsed = Distiller._extract_json(response)
    if parsed:
        print(f"\nJSON extracted successfully!")
        print(f"Keys: {list(parsed.keys())}")
        if 'facts' in parsed:
            print(f"Facts count: {len(parsed['facts'])}")
    else:
        print("\nJSON extraction failed!")
else:
    print("\nLLM returned empty response")
