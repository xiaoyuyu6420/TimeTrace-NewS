"""NLP processing - Jieba-based keyword extraction and similarity."""

import logging
from collections import Counter

import jieba
import jieba.analyse
import jieba.posseg as pseg

logger = logging.getLogger(__name__)

STOP_WORDS = set(
    "的了是在我有和就不人都一上也很到说要去你会着看好自己这那他她它们让被把"
)


class JiebaProcessor:
    """Jieba-based NLP processor."""

    def extract_keywords(self, text: str, topk: int = 10) -> list[str]:
        if not text:
            return []
        keywords = jieba.analyse.extract_tags(text, topK=topk, withWeight=False)
        return [w for w in keywords if w not in STOP_WORDS and len(w) > 1]

    def extract_entities(self, text: str) -> list[dict]:
        if not text:
            return []

        entities = []
        seen = set()

        for word, flag in pseg.cut(text):
            if flag in ("nr", "ns", "nt", "nz", "eng") and word not in seen and len(word) > 1:
                type_map = {
                    "nr": "PERSON",
                    "ns": "LOCATION",
                    "nt": "ORG",
                    "nz": "MISC",
                    "eng": "ENG",
                }
                entities.append({"name": word, "type": type_map.get(flag, "MISC")})
                seen.add(word)

        return entities[:15]

    def compute_similarity(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0

        words1 = set(jieba.cut(text1))
        words2 = set(jieba.cut(text2))

        words1 = {w for w in words1 if w not in STOP_WORDS and len(w) > 1}
        words2 = {w for w in words2 if w not in STOP_WORDS and len(w) > 1}

        return self.keyword_similarity(list(words1), list(words2))

    def keyword_similarity(self, keywords1: list[str], keywords2: list[str]) -> float:
        if not keywords1 or not keywords2:
            return 0.0

        set1, set2 = set(keywords1), set(keywords2)
        intersection = set1 & set2
        union = set1 | set2

        return len(intersection) / len(union) if union else 0.0

    def entity_similarity(self, entities1: list[dict], entities2: list[dict]) -> float:
        if not entities1 or not entities2:
            return 0.0

        type_weight = {"PERSON": 0.4, "ORG": 0.3, "LOCATION": 0.3, "MISC": 0.2, "ENG": 0.2}

        names1 = {e["name"]: e["type"] for e in entities1}
        names2 = {e["name"]: e["type"] for e in entities2}

        common = set(names1.keys()) & set(names2.keys())
        if not common:
            return 0.0

        score = sum(type_weight.get(names1[n], 0.2) for n in common)
        max_score = sum(
            max(
                type_weight.get(names1.get(n, ""), 0.2),
                type_weight.get(names2.get(n, ""), 0.2)
            )
            for n in common
        )

        return score / max_score if max_score else 0.0

    def title_char_similarity(self, title1: str, title2: str) -> float:
        if not title1 or not title2:
            return 0.0

        set1, set2 = set(title1), set(title2)
        intersection = set1 & set2
        union = set1 | set2

        return len(intersection) / len(union) if union else 0.0
