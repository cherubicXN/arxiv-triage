import os
import json
from typing import Dict, Any, Optional, Tuple, List

def _heuristic_score(title: str, abstract: str) -> Dict[str, Any]:
    # very rough baseline so UI can show something without a key
    tl = len(title or "")
    al = len(abstract or "")
    novelty = 3 + (1 if "first" in (abstract or "").lower() else 0)
    clarity = 3 + (1 if tl < 120 and al < 3000 else 0)
    evidence = 3
    reusability = 2 + (1 if any(k in (abstract or "").lower() for k in ["code", "dataset", "open-sourced"]) else 0)
    fit = 3
    total = novelty + clarity + evidence + reusability + fit
    return {"novelty": novelty, "evidence": evidence, "clarity": clarity, "reusability": reusability, "fit": fit, "total": total}

def llm_rubric_score(title: str, abstract: str, provider: Optional[str] = None) -> Dict[str, Any]:
    """
    Compute rubric scores via an LLM provider if configured, else return a heuristic fallback.

    Provider selection (by priority):
      - function arg `provider` in {"openai","deepseek"}
      - env `LLM_PROVIDER` (default: openai)

    Env (OpenAI):
      - OPENAI_API_KEY (required)
      - OPENAI_BASE_URL or OPENAI_API_BASE (optional)
      - LLM_MODEL (default: gpt-4o-mini)

    Env (DeepSeek):
      - DEEPSEEK_API_KEY (or OPENAI_API_KEY)
      - DEEPSEEK_BASE_URL (default: https://api.deepseek.com/v1)
      - DEEPSEEK_MODEL (default: deepseek-chat)
    """
    prov = (provider or os.getenv("LLM_PROVIDER") or "openai").strip().lower()
    try:
        from openai import OpenAI
    except Exception:
        # SDK not installed at runtime
        return _heuristic_score(title, abstract)

    if prov == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return _heuristic_score(title, abstract)
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        model = os.getenv("DEEPSEEK_MODEL", os.getenv("LLM_MODEL", "deepseek-chat"))
        client = OpenAI(api_key=api_key, base_url=base_url)
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return _heuristic_score(title, abstract)
        base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    system = (
        "You are a strict evaluator. Return ONLY a compact JSON object with integer scores."
        " Rubric: novelty(1-5), evidence(1-5), clarity(1-5), reusability(1-5), fit(1-5)."
        " Also include total (sum). Keep it under 200 chars."
    )
    user = (
        f"Title: {title}\n\nAbstract: {abstract}\n\n"
        "Respond as JSON: {\"novelty\":n,\"evidence\":n,\"clarity\":n,\"reusability\":n,\"fit\":n,\"total\":n}"
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=120,
        )
        content = resp.choices[0].message.content if getattr(resp, "choices", None) else ""
        data = json.loads(content or "{}")
        # validate fields
        fields = ["novelty", "evidence", "clarity", "reusability", "fit", "total"]
        if not all(k in data for k in fields):
            raise ValueError("missing fields")
        # coerce to ints
        for k in fields:
            data[k] = int(data.get(k, 0))
        return data
    except Exception:
        # fall back gracefully
        return _heuristic_score(title, abstract)


def _make_client_and_model(provider: Optional[str] = None) -> Optional[Tuple["OpenAI", str]]:  # type: ignore[name-defined]
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None
    prov = (provider or os.getenv("LLM_PROVIDER") or "openai").strip().lower()
    if prov == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        model = os.getenv("DEEPSEEK_MODEL", os.getenv("LLM_MODEL", "deepseek-chat"))
        client = OpenAI(api_key=api_key, base_url=base_url)
        return client, model
    # default openai
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    return client, model


def llm_suggest_tags(title: str, abstract: str, categories: Optional[str] = None, provider: Optional[str] = None) -> List[str]:
    """
    Suggest up to 5 concise tags for a paper. Returns a list of normalized tags.
    If provider/API not configured, returns an empty list (no suggestions).
    """
    made = _make_client_and_model(provider)
    if not made:
        return []
    client, model = made
    system = (
        "You generate concise topical tags for arXiv papers."
        " Return ONLY a JSON array of up to 5 short tags (1-3 words)."
        " Use lowercase; prefer hyphens instead of spaces; avoid punctuation."
    )
    user = (
        f"Title: {title}\n\nAbstract: {abstract}\n\n"
        f"Categories: {categories or ''}\n\nReturn JSON array of tags, e.g. [\"diffusion-models\", \"few-shot-learning\"]."
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=120,
        )
        content = resp.choices[0].message.content if getattr(resp, "choices", None) else ""
        raw = []
        try:
            raw = json.loads(content or "[]")
        except Exception:
            # fallback: split by commas
            raw = [x.strip() for x in (content or "").split(",")]
        # normalize
        out: List[str] = []
        for t in raw:
            if not isinstance(t, str):
                continue
            s = t.lower().strip()
            s = s.replace("/", "-")
            s = s.replace(" ", "-")
            s = "".join(ch for ch in s if ch.isalnum() or ch == "-")
            s = s.strip("-")
            if s and s not in out:
                out.append(s)
            if len(out) >= 5:
                break
        return out
    except Exception:
        return []
