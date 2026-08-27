from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage

from src.llm_client import llm
from src.generation.prompts import SYSTEM_PROMPT
from src.generation.context_builder import build_context
from langchain_core.documents import Document

NAME = "Arthur"

class Conversation:

    def __init__(self, all_docs: list[Document]):
        self.all_docs = all_docs
        self.history: list[BaseMessage] = []

    def ask(self, query: str) -> str:
        if not self.history:
            context = build_context(self.all_docs)
            system_message = SystemMessage(
                content=SYSTEM_PROMPT.format(name=NAME, context=context)
            )
            self.history.append(system_message)

        self.history.append(HumanMessage(content=query))
        response = llm.invoke(self.history)
        self.history.append(AIMessage(content=response.content))

        return response.content