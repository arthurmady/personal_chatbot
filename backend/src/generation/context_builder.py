from langchain_core.documents import Document
import re

def build_context(results: list[Document]) -> str:
    blocks = [doc.page_content for doc in results]
    return "\n\n---\n\n".join(blocks)

def extract_topics(markdown_text: str) -> list[str]:
    return [t.strip() for t in re.findall(r"^##\s+(.+?)\s*$", markdown_text, flags=re.MULTILINE)]