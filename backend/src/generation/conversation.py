import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.documents import Document

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

    @staticmethod
    def _normalize(text: str) -> str:
        return text.strip().lower()

    def _parse_response(self, raw_content: str) -> dict:
        cleaned = raw_content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").replace("json", "", 1).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            print("PARSE FAILED:", raw_content)
            return {"response": raw_content, "summary": "", "topics_covered": [], "suggestions": []}

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

    def _build_suggestions(self, llm_suggestions: list[str]) -> list[str]:
        seen = set()
        filtered = []
        for suggestion in llm_suggestions:
            suggestion = suggestion.strip()
            if suggestion and suggestion not in seen:
                seen.add(suggestion)
                filtered.append(suggestion)
        return filtered[:3]

    def ask(self, query: str) -> dict:
        messages = self._build_messages(query, self.summary)
        response = llm.invoke(messages)
        parsed = self._parse_response(response.content)

        response = parsed.get("response", "")
        topics_covered = parsed.get("topics_covered", [])
        llm_suggestions = parsed.get("suggestions", [])

        already_covered = self._update_topics_covered(topics_covered)
        self.summary = "" if already_covered else parsed.get("summary", "")

        suggestions = self._build_suggestions(llm_suggestions)
        return {"response": response, "suggestions": suggestions}