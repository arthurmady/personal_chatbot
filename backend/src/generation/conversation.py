import json
import logging
import re
import time
from langchain_core.messages import SystemMessage, HumanMessage
from json_repair import repair_json

from src.llm_client import llm
from src.generation.prompts import SYSTEM_PROMPT, FOLLOWUP_TEMPLATE
from src.generation.context_builder import load_facts, build_context, extract_topics

logger = logging.getLogger(__name__)

NAME = "Arthur"

_PARSE_FALLBACK = {
    "response": "",
    "summary": [],
    "fact_ids": [],
    "level": {},
    "suggestions": [],
}

_MAX_KEYWORD_WORDS = 10

_STOPWORDS = frozenset("""
le la les de des du un une et en a à au aux pour par sur dans avec que qui ne pas se sa son ses
est sont plus mais aussi ou où d l s n c j m t qu on il elle ils elles nous vous tout tous très
the and or if then else this that
""".split()) | frozenset(chr(c) for c in range(ord("a"), ord("z") + 1))


class Conversation:

    def __init__(self):
        self.facts = load_facts()
        self.all_tags = extract_topics(self.facts)
        self.essentials_done: set[str] = set()
        self.details_done: set[str] = set()
        self.last_topic: str = ""

    def _get_fact_states(self) -> str:
        lines = []
        for fact in self.facts:
            fid = fact["id"]
            e_done = fid in self.essentials_done
            details = fact.get("details", [])
            details_given = [d["id"] for d in details if d["id"] in self.details_done]
            details_remaining = [d["id"] for d in details if d["id"] not in self.details_done]

            if not e_done:
                status = "not_discussed"
            elif details and not details_given:
                status = "essential_given"
            elif details_remaining:
                status = f"partial_details: [{', '.join(details_given)}]"
            else:
                status = "details_complete"
            lines.append(f"  {fid}: {status}")
        return "\n".join(lines)

    def _extract_json_blob(self, raw_content: str) -> str:
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_content, re.DOTALL)
        if fence_match:
            return fence_match.group(1)
        first = raw_content.find("{")
        last = raw_content.rfind("}")
        if first != -1 and last > first:
            return raw_content[first:last + 1]
        return raw_content

    def _parse_response(self, raw_content: str) -> dict:
        blob = self._extract_json_blob(raw_content)
        try:
            parsed = json.loads(blob)
        except json.JSONDecodeError:
            try:
                repaired = repair_json(blob)
                parsed = json.loads(repaired)
            except Exception:
                return {**_PARSE_FALLBACK, "response": raw_content}

        if not isinstance(parsed, dict):
            return {**_PARSE_FALLBACK, "response": raw_content}

        parsed.setdefault("response", raw_content)
        parsed.setdefault("summary", [])
        if not isinstance(parsed.get("fact_ids"), list):
            parsed["fact_ids"] = []
        if not isinstance(parsed.get("level"), dict):
            parsed["level"] = {}
        if not isinstance(parsed.get("suggestions"), list):
            parsed["suggestions"] = []

        return parsed

    def _build_messages(self, query: str) -> list:
        context = build_context(self.facts, self.essentials_done, self.details_done)
        remaining_topics = self._remaining_topics()
        remaining_topics_display = "; ".join(remaining_topics) if remaining_topics else "(none)"
        all_topics = "; ".join(self.all_tags) if self.all_tags else "(none)"
        fact_states = self._get_fact_states()

        covered_display = self._covered_tags_display()

        system_message = SystemMessage(
            content=SYSTEM_PROMPT.format(
                name=NAME,
                context=context,
                remaining_topics=remaining_topics_display,
                all_topics=all_topics,
                fact_states=fact_states,
            )
        )
        human_message = HumanMessage(content=FOLLOWUP_TEMPLATE.format(
            already_covered=covered_display,
            query=query,
            last_topic=self.last_topic,
        ))
        return [system_message, human_message]

    def _remaining_topics(self) -> list[str]:
        tag_to_fids: dict[str, list[str]] = {}
        for fact in self.facts:
            for tag in fact["tags"]:
                tag_to_fids.setdefault(tag.strip().lower(), []).append(fact["id"])

        covered_tags = set()
        for tag, fids in tag_to_fids.items():
            if all(fid in self.essentials_done for fid in fids):
                covered_tags.add(tag)

        return [t for t in self.all_tags if t.strip().lower() not in covered_tags]

    def _covered_tags_display(self) -> str:
        covered = []
        for fact in self.facts:
            if fact["id"] in self.essentials_done:
                for tag in fact["tags"]:
                    if tag not in covered:
                        covered.append(tag)
        return "; ".join(covered) if covered else "(none)"

    def _build_suggestions(self, llm_suggestions: list) -> list[str]:
        result = []
        seen = set()
        for s in llm_suggestions:
            if not isinstance(s, str) or not s.strip():
                continue
            if s in seen:
                continue
            seen.add(s)
            result.append(s.strip())
        return result[:3]

    @staticmethod
    def _strip_md(text: str) -> str:
        return text.replace("**", "").strip()

    def _parse_summary_markdown(self, text: str) -> list[dict]:
        entries: list[dict] = []
        tag = ""
        keywords: list[str] = []

        def flush():
            nonlocal tag, keywords
            if tag and keywords:
                entries.append({"tag": tag, "keywords": keywords})
            tag = ""
            keywords = []

        for raw_line in text.split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("**") and line.endswith("**") and line.count("**") == 2:
                flush()
                tag = line.strip("*").strip()
                continue
            if not tag:
                continue
            for part in line.split(","):
                part = part.strip()
                if part and len(part.split()) <= _MAX_KEYWORD_WORDS:
                    keywords.append(part)
        flush()
        return entries

    def _normalize_summary(self, raw) -> list[dict]:
        if isinstance(raw, str):
            raw = raw.replace("\\n", "\n")
            items = self._parse_summary_markdown(raw)
        elif isinstance(raw, list):
            items = raw
        else:
            return []

        entries: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            tag = item.get("tag")
            if not isinstance(tag, str):
                continue
            tag = self._strip_md(tag)
            if not tag:
                continue
            raw_keywords = item.get("keywords")
            if not isinstance(raw_keywords, list):
                continue
            keywords: list[str] = []
            seen: set[str] = set()
            for kw in raw_keywords:
                if not isinstance(kw, str):
                    continue
                kw = self._strip_md(kw).strip().rstrip(",;.")
                if not kw or len(kw.split()) > _MAX_KEYWORD_WORDS:
                    continue
                key = kw.lower()
                if key in seen:
                    continue
                seen.add(key)
                keywords.append(kw)
            if not keywords:
                continue
            entries.append({"tag": tag, "keywords": keywords})
        return entries

    @staticmethod
    def _summary_to_markdown(entries: list[dict]) -> str:
        blocks = []
        for entry in entries:
            lines = entry["keywords"]
            blocks.append(f"**{entry['tag']}**\n" + "\n".join(lines))
        return "\n\n".join(blocks)

    def _summary_suspicious_tokens(self) -> set[str]:
        if getattr(self, "_summary_guard_cache", None) is not None:
            return self._summary_guard_cache
        essential_tokens: set[str] = set()
        restricted_tokens: set[str] = set()
        for fact in self.facts:
            essential_tokens.update(self._norm_words(fact.get("essential", "")))
            plus = fact.get("plus")
            if plus:
                restricted_tokens.update(self._norm_words(plus))
            for detail in fact.get("details", []):
                restricted_tokens.update(self._norm_words(detail["content"]))
        self._summary_guard_cache = (restricted_tokens - essential_tokens) - _STOPWORDS
        return self._summary_guard_cache

    def _filter_non_essential_keywords(self, entries: list[dict]) -> list[dict]:
        suspicious = self._summary_suspicious_tokens()
        kept: list[dict] = []
        for entry in entries:
            tag_tokens = set(self._norm_words(entry["tag"]))
            keywords: list[str] = []
            for kw in entry["keywords"]:
                bad = sorted({w for w in self._norm_words(kw) if w in suspicious and w not in tag_tokens})
                if bad:
                    logger.info("summary keyword dropped (non-essential): %r -> %s", kw, bad)
                    continue
                keywords.append(kw)
            if keywords:
                kept.append({"tag": entry["tag"], "keywords": keywords})
            else:
                logger.info("summary tag dropped (all keywords non-essential): %r", entry["tag"])
        return kept

    @staticmethod
    def _norm_words(text: str) -> list[str]:
        return re.sub(r"[^\w\s]", " ", text.lower()).split()

    def _find_used_detail_ids(self, response_text: str) -> set[str]:
        resp_words = self._norm_words(response_text)
        if len(resp_words) < 4:
            return set()
        resp_grams = {tuple(resp_words[i:i + 4]) for i in range(len(resp_words) - 3)}
        used: set[str] = set()
        for fact in self.facts:
            for detail in fact.get("details", []):
                words = self._norm_words(detail["content"])
                if len(words) < 4:
                    continue
                if any(tuple(words[i:i + 4]) in resp_grams for i in range(len(words) - 3)):
                    used.add(detail["id"])
        return used

    def _has_open_subjects(self) -> bool:
        for fact in self.facts:
            if fact["id"] not in self.essentials_done:
                return True
            if any(d["id"] not in self.details_done for d in fact.get("details", [])):
                return True
        return False

    async def ask(self, query: str) -> dict:
        messages = self._build_messages(query)

        start = time.perf_counter()
        response = await llm.ainvoke(messages)
        elapsed = time.perf_counter() - start
        model_used = getattr(response, 'response_metadata', {}).get('model_name', llm.model_name)
        logger.info("Model: %s | Time: %.3fs", model_used, elapsed)

        parsed = self._parse_response(response.content)

        logger.debug("RAW RESPONSE: %s", response.content[:800])

        response_text = parsed.get("response", "")
        fact_ids = parsed.get("fact_ids", [])
        level_map = parsed.get("level", {})
        llm_suggestions = parsed.get("suggestions", [])

        logger.info("fact_ids: %s | level: %s", fact_ids, level_map)

        used_detail_ids = self._find_used_detail_ids(response_text)
        if used_detail_ids:
            logger.info("detail ids detected in response: %s", sorted(used_detail_ids))
            facts_by_id = {f["id"]: f for f in self.facts}
            for fid in fact_ids:
                if not isinstance(fid, str) or fid not in facts_by_id:
                    continue
                own = {d["id"] for d in facts_by_id[fid].get("details", [])} & used_detail_ids
                if not own:
                    continue
                current = level_map.get(fid, "essential")
                if current == "essential":
                    level_map[fid] = sorted(own)
                elif isinstance(current, list):
                    level_map[fid] = sorted(set(current) | own)
            logger.info("level after detail check: %s", level_map)

        logger.debug("PARSED RESPONSE: %s", response_text[:300])

        summary_entries = self._normalize_summary(parsed.get("summary", []))
        summary_entries = self._filter_non_essential_keywords(summary_entries)
        summary = self._summary_to_markdown(summary_entries)
        logger.debug("SUMMARY: %s", summary[:300])

        new_essential_ids = []
        has_new_essential = False
        for fid in fact_ids:
            if not isinstance(fid, str):
                continue
            level = level_map.get(fid, "essential")
            if fid not in self.essentials_done:
                new_essential_ids.append(fid)
                has_new_essential = True
            if level == "essential":
                self.essentials_done.add(fid)
            elif isinstance(level, list):
                self.essentials_done.add(fid)
                for sub_id in level:
                    if isinstance(sub_id, str):
                        self.details_done.add(sub_id)
            elif isinstance(level, str) and level.startswith("detail"):
                self.essentials_done.add(fid)

        divers_ids = {f["id"] for f in self.facts if "Divers" in f.get("tags", [])}
        non_divers = any(fid not in divers_ids for fid in new_essential_ids)

        turn_summary = summary if (has_new_essential and summary and non_divers) else ""

        suggestions = self._build_suggestions(llm_suggestions)
        if not self._has_open_subjects():
            suggestions = []
        self.last_topic = "; ".join(
            f["tags"][0] for f in self.facts
            if f["id"] in new_essential_ids and f.get("tags")
        )
        logger.debug("essentials_done: %s", self.essentials_done)
        logger.debug("details_done: %s", self.details_done)
        logger.debug("turn_summary: %r", turn_summary)
        return {"response": response_text, "suggestions": suggestions, "turn_summary": turn_summary}
