import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_facts() -> list[dict]:
    all_facts = []
    data_dir = Path("data")
    for data_file in sorted(data_dir.glob("*.json")):
        raw = data_file.read_text(encoding="utf-8")
        data = json.loads(raw)
        all_facts.extend(data.get("facts", []))
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

        if fid not in essentials_done:
            lines.append(f"Essential : {fact['essential']}")
            if plus:
                lines.append(f"Plus : {plus}")
        else:
            lines.append(f"(Already discussed — essential given)")

        remaining_details = [d for d in details if d["id"] not in details_done]
        if remaining_details:
            for d in remaining_details:
                lines.append(f"[$id: {d['id']}] {d['content']}")

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
