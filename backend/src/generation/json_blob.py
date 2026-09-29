import re


def extract_json_blob(raw: str) -> str:
    """Extrait le premier objet JSON d'une réponse LLM (blocs ```json inclus)."""
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence_match:
        return fence_match.group(1)
    first = raw.find("{")
    last = raw.rfind("}")
    if first != -1 and last > first:
        return raw[first:last + 1]
    return raw
