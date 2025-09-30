from rank_bm25 import BM25Okapi
from typing import List, Tuple
import re

def _tokenize(s: str):
    return re.findall(r"[A-Za-z0-9]+", s.lower())

def search_bm25(docs: List[Tuple[int, str]], query: str) -> List[int]:
    if not docs:
        return []
    corpus = [_tokenize(text) for _, text in docs]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(zip([i for i, _ in docs], scores), key=lambda x: x[1], reverse=True)
    return [i for i, _ in ranked]
