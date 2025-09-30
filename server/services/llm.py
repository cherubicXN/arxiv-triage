import os
from typing import Dict, Any

# Placeholder for optional GPT-5 Pro rubric scoring.
# We do not call the API here to keep the MLV minimal and offline-friendly.
# If OPENAI_API_KEY is configured in env, you can implement a call using openai SDK.
def llm_rubric_score(title: str, abstract: str) -> Dict[str, Any]:
    if not os.getenv("OPENAI_API_KEY"):
        # heuristic fallback
        return {"novelty": 3, "evidence": 3, "clarity": 3, "reusability": 2, "fit": 3, "total": 14}
    # Example (pseudocode):
    # from openai import OpenAI
    # client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    # prompt = f"Score the paper by rubric ... Title: {title}\nAbstract: {abstract}"
    # resp = client.chat.completions.create(model=os.getenv("LLM_MODEL","gpt-5-pro"), messages=[...])
    # parse resp → dict
    # return scores
    return {"novelty": 4, "evidence": 3, "clarity": 4, "reusability": 2, "fit": 3, "total": 16}
