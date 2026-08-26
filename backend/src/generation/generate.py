from langchain_core.messages import SystemMessage, HumanMessage
from src.llm_client import llm
from src.generation.context_builder import build_context
from src.generation.prompts import SYSTEM_PROMPT
from langchain_core.documents import Document

NAME = "Arthur"

def generate_answer(query: str, docs: list[Document]) -> str:

    context = build_context(docs)

    system_message = SystemMessage(
        content=SYSTEM_PROMPT.format(name=NAME, context=context)
    )
    human_message = HumanMessage(content=query)

    response = llm.invoke([system_message, human_message])
    return response.content