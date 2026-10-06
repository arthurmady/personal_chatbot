import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _is_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_facts_data(data) -> str | None:
    """Premier défaut de schéma d'un fichier de faits, ou None s'il est valide.

    Un fait mal formé fait lever une KeyError dans `Conversation()` et casse
    toutes les nouvelles sessions : on le refuse avant de l'écrire.
    """
    if not isinstance(data, dict) or not isinstance(data.get("facts"), list):
        return "le fichier doit être un objet avec une liste « facts »"
    fact_ids: set[str] = set()
    detail_ids: set[str] = set()
    for i, fact in enumerate(data["facts"]):
        if not isinstance(fact, dict):
            return f"facts[{i}] doit être un objet"
        fid = fact.get("id")
        if not _is_text(fid):
            return f"facts[{i}] : « id » manquant"
        if fid in fact_ids:
            return f"fait {fid} : id en double"
        fact_ids.add(fid)
        if not _is_text(fact.get("essential")):
            return f"fait {fid} : « essential » manquant"
        tags = fact.get("tags")
        if not isinstance(tags, list) or not tags or not all(_is_text(t) for t in tags):
            return f"fait {fid} : « tags » doit être une liste non vide de textes"
        if fact.get("plus") is not None and not isinstance(fact["plus"], str):
            return f"fait {fid} : « plus » doit être un texte"
        details = fact.get("details", [])
        if not isinstance(details, list):
            return f"fait {fid} : « details » doit être une liste"
        for j, detail in enumerate(details):
            if not isinstance(detail, dict) or not _is_text(detail.get("id")) or not _is_text(detail.get("content")):
                return f"fait {fid} : details[{j}] doit avoir « id » et « content »"
            if detail["id"] in detail_ids or detail["id"] in fact_ids:
                return f"détail {detail['id']} : id en double"
            detail_ids.add(detail["id"])
    return None


def load_facts_from_file(data_file: Path) -> list[dict]:
    raw = data_file.read_text(encoding="utf-8")
    data = json.loads(raw)
    return data.get("facts", [])


def load_facts() -> list[dict]:
    all_facts = []
    data_dir = Path("data")
    for data_file in sorted(data_dir.glob("*.json")):
        if data_file.name == "sessions.json":
            continue
        try:
            data = json.loads(data_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("fichier de faits illisible, ignoré : %s", data_file.name)
            continue
        problem = validate_facts_data(data)
        if problem:
            logger.error("fichier de faits invalide, ignoré : %s (%s)", data_file.name, problem)
            continue
        all_facts.extend(data["facts"])
    return all_facts


def build_context(facts: list[dict], essentials_done: set[str] = None, details_done: set[str] = None) -> str:
    if essentials_done is None:
        essentials_done = set()
    if details_done is None:
        details_done = set()

    blocks = []
    for fact in facts:
        tags_str = ", ".join(fact.get("tags", []))
        fid = fact["id"]
        details = fact.get("details", [])
        plus = fact.get("plus")

        lines = [f"[id: {fid}] (tags: {tags_str})"]
        lines.append(f"Essential : {fact['essential']}")
        if plus:
            lines.append(f"Plus : {plus}")

        remaining_details = [d for d in details if d["id"] not in details_done]
        if remaining_details:
            if fid in essentials_done:
                for d in remaining_details:
                    lines.append(f"[$id: {d['id']}] {d['content']}")
            else:
                for d in remaining_details:
                    lines.append(f"[$id: {d['id']}] (contenu réservé : donner l'essentiel avant ce détail)")

        blocks.append("\n".join(lines))

    return "\n\n---\n\n".join(blocks)


def extract_topics(facts: list[dict]) -> list[str]:
    seen = set()
    topics = []
    for fact in facts:
        for tag in fact.get("tags", []):
            key = tag.strip().lower()
            if key not in seen:
                seen.add(key)
                topics.append(tag.strip())
    logger.debug("Tags: %s", ", ".join(topics))
    return topics
