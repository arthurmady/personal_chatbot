import json
import re
import time
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.documents import Document
from json_repair import repair_json

from src.llm_client import llm
from src.generation.prompts import SYSTEM_PROMPT, FOLLOWUP_TEMPLATE
from src.generation.context_builder import build_context

NAME = "Arthur"

class Conversation:

    def __init__(self, all_docs: list[Document], topics: list[str]):
        self.all_docs = all_docs
        self.context = build_context(all_docs)
        self.topics_covered: dict[str, bool] = {topic: False for topic in topics}
        self.summary = ""

    def _extract_json_blob(self, raw_content: str) -> str:

        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_content, re.DOTALL)
        if fence_match:
            return fence_match.group(1)

        first = raw_content.find("{")
        last = raw_content.rfind("}")
        if first != -1 and last != -1 and last > first:
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
                return {"response": raw_content, "summary": "", "topics_covered": [], "suggestions": []}

        if not isinstance(parsed, dict):
            return {"response": raw_content, "summary": "", "topics_covered": [], "suggestions": []}

        parsed.setdefault("response", raw_content)
        parsed.setdefault("summary", "")
        if not isinstance(parsed.get("topics_covered"), list):
            parsed["topics_covered"] = []
        if not isinstance(parsed.get("suggestions"), list):
            parsed["suggestions"] = []

        return parsed

    def _build_messages(self, query: str, summary: str) -> list:
        remain_topics = self._remain_topics()
        remain_topics_display = "; ".join(remain_topics) if remain_topics else "(aucun)"
        all_topics = "; ".join(self.topics_covered.keys()) if self.topics_covered else "(aucun)"

        system_message = SystemMessage(
            content=SYSTEM_PROMPT.format(
                name=NAME,
                context=self.context,
                remain_topics=remain_topics_display,
                all_topics=all_topics,
            )
        )
        human_message = HumanMessage(content=FOLLOWUP_TEMPLATE.format(summary=summary, query=query))
        return [system_message, human_message]

    def _update_topics_covered(self, topics_covered: list[str]) -> list[str]:
        normalized = {topic.strip().lower(): topic for topic in self.topics_covered}
        already_covered = []
        for topic in topics_covered:
            key = topic.strip().lower()
            if key in normalized:
                original = normalized[key]
                if self.topics_covered[original]:
                    already_covered.append(original)
                self.topics_covered[original] = True
        return already_covered

    def _remain_topics(self) -> list[str]:
        return [topic for topic, covered in self.topics_covered.items() if not covered]

    def _build_suggestions(self, llm_suggestions: list) -> list[str]:
        seen = set()
        result = []
        for s in llm_suggestions:
            if isinstance(s, str) and s.strip() and s not in seen:
                seen.add(s)
                result.append(s)
        return result[:3]

    async def ask(self, query: str) -> dict:
        messages = self._build_messages(query, self.summary)

        start = time.perf_counter()
        response = await llm.ainvoke(messages)
        elapsed = time.perf_counter() - start
        model_used = getattr(response, 'response_metadata', {}).get('model_name', llm.model_name)
        print(f"Model: {model_used} | Time: {elapsed:.3f}s")

        parsed = self._parse_response(response.content)

        print("RAW RESPONSE:", response.content[:800])

        response_text = parsed.get("response", "")
        topics_covered = parsed.get("topics_covered", [])
        llm_suggestions = parsed.get("suggestions", [])

        print("PARSED RESPONSE:", response_text[:300])
        print("SUMMARY:", parsed.get("summary", "")[:300])

        already_covered = self._update_topics_covered(topics_covered)
        summary = "" if already_covered else parsed.get("summary", "")
        summary = summary.replace("\\n", "\n")
        self.summary = summary

        suggestions = self._build_suggestions(llm_suggestions)
        return {"response": response_text, "suggestions": suggestions}