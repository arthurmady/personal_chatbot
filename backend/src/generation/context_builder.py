from langchain_core.documents import Document

def build_context(results: list[Document]) -> str:
    blocks = []
    for doc in results:
        blocks.append(f"{doc.page_content}")

    return "\n\n---\n\n".join(blocks)