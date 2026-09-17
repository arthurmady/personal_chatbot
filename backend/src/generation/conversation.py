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


class Conversation:

    def __init__(self):
        self.facts = load_facts()
        self.all_tags = extract_topics(self.facts)
        self.essentiel_done: set[str] = set()
        self.detail_done: set[str] = set()
        self.summary = ""

    def _get_fact_state(self) -> str:
        lines = []
        for fact in self.facts:
            fid = fact["id"]
            e_done = fid in self.essentiel_done
            details = fact.get("detail", [])
            details_given = [d["id"] for d in details if d["id"] in self.detail_done]
            details_remaining = [d["id"] for d in details if d["id"] not in self.detail_done]

            if not e_done:
                status = "non_abordé"
            elif details and not details_given:
                status = "essentiel_donné"
            elif details_remaining:
                status = f"detail_partiel: [{', '.join(details_given)}]"
            else:
                status = "detail_complet"
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
                return {"response": raw_content, "summary": "", "topics_covered": [], "fact_ids": [], "level": {}, "suggestions": []}

        if not isinstance(parsed, dict):
            return {"response": raw_content, "summary": "", "topics_covered": [], "fact_ids": [], "level": {}, "suggestions": []}

        parsed.setdefault("response", raw_content)
        parsed.setdefault("summary", "")
        if not isinstance(parsed.get("topics_covered"), list):
            parsed["topics_covered"] = []
        if not isinstance(parsed.get("fact_ids"), list):
            parsed["fact_ids"] = []
        if not isinstance(parsed.get("level"), dict):
            parsed["level"] = {}
        if not isinstance(parsed.get("suggestions"), list):
            parsed["suggestions"] = []

        return parsed

    def _build_messages(self, query: str, summary: str) -> list:
        context = build_context(self.facts, self.essentiel_done, self.detail_done)
        remain_topics = self._remain_topics()
        remain_topics_display = "; ".join(remain_topics) if remain_topics else "(aucun)"
        all_topics = "; ".join(self.all_tags) if self.all_tags else "(aucun)"
        fact_state = self._get_fact_state()

        system_message = SystemMessage(
            content=SYSTEM_PROMPT.format(
                name=NAME,
                context=context,
                remain_topics=remain_topics_display,
                all_topics=all_topics,
                fact_state=fact_state,
            )
        )
        human_message = HumanMessage(content=FOLLOWUP_TEMPLATE.format(summary=summary, query=query))
        return [system_message, human_message]

    def _remain_topics(self) -> list[str]:
        covered_tags = set()
        for fact in self.facts:
            if fact["id"] in self.essentiel_done:
                for tag in fact["tags"]:
                    covered_tags.add(tag.strip().lower())
        return [t for t in self.all_tags if t.strip().lower() not in covered_tags]

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

    async def ask(self, query: str) -> dict:
        messages = self._build_messages(query, self.summary)

        start = time.perf_counter()
        response = await llm.ainvoke(messages)
        elapsed = time.perf_counter() - start
        model_used = getattr(response, 'response_metadata', {}).get('model_name', llm.model_name)
        logger.info("Model: %s | Time: %.3fs", model_used, elapsed)
        print(f"[LLM] Model: {model_used} | Time: {elapsed:.3f}s")

        parsed = self._parse_response(response.content)

        logger.debug("RAW RESPONSE: %s", response.content[:800])

        response_text = parsed.get("response", "")
        fact_ids = parsed.get("fact_ids", [])
        level_map = parsed.get("level", {})
        llm_suggestions = parsed.get("suggestions", [])

        logger.debug("PARSED RESPONSE: %s", response_text[:300])
        logger.debug("SUMMARY: %s", parsed.get("summary", "")[:300])

        essentiel_ids_this_turn = []
        has_essentiel = False
        for fid in fact_ids:
            if not isinstance(fid, str):
                continue
            level = level_map.get(fid, "essentiel")
            if level == "essentiel":
                if fid not in self.essentiel_done:
                    essentiel_ids_this_turn.append(fid)
                    has_essentiel = True
                self.essentiel_done.add(fid)
            elif isinstance(level, list):
                self.essentiel_done.add(fid)
                for sub_id in level:
                    if isinstance(sub_id, str):
                        self.detail_done.add(sub_id)
            elif isinstance(level, str) and level.startswith("detail"):
                self.essentiel_done.add(fid)

        summary = parsed.get("summary", "")
        summary = summary.replace("\\n", "\n")
        if not has_essentiel:
            summary = ""
        self.summary = summary

        suggestions = self._build_suggestions(llm_suggestions)
        return {"response": response_text, "suggestions": suggestions}
