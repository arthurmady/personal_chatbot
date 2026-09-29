import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


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
        all_facts.extend(load_facts_from_file(data_file))
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
