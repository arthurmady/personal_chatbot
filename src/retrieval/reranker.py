from sentence_transformers import CrossEncoder
from langchain_core.documents import Document

_reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank(query: str, docs: list[Document], top_k: int = 5) -> list[tuple[Document, float]]:
    if not docs:
        return []

    pairs = [(query, doc.page_content) for doc in docs]
    scores = _reranker.predict(pairs)

    ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)

    return ranked[:top_k]   