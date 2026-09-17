import json
from pathlib import Path


def load_facts() -> list[dict]:
    all_facts = []
    data_dir = Path("data")
    for data_file in sorted(data_dir.glob("*.json")):
        raw = data_file.read_text(encoding="utf-8")
        data = json.loads(raw)
        all_facts.extend(data.get("facts", []))
    return all_facts


def build_context(facts: list[dict], essentiel_done: set[str] = None, detail_done: set[str] = None) -> str:
    if essentiel_done is None:
        essentiel_done = set()
    if detail_done is None:
        detail_done = set()

    blocks = []
    for fact in facts:
        tags_str = ", ".join(fact.get("tags", []))
        fid = fact["id"]
        details = fact.get("detail", [])
        plus = fact.get("plus")

        lines = [f"[id: {fid}] (tags: {tags_str})"]

        if fid not in essentiel_done:
            lines.append(f"Essentiel : {fact['essentiel']}")
            if plus:
                lines.append(f"Plus : {plus}")

        remaining_details = [d for d in details if d["id"] not in detail_done]
        if remaining_details:
            for d in remaining_details:
                lines.append(f"[$id: {d['id']}] {d['content']}")

        if len(lines) > 1:
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
    print(f"[DATA] Tags: {', '.join(topics)}")
    return topics
