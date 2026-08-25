from src.retrieval.reranker import rerank
from langchain_core.documents import Document
from qdrant_client.models import Filter, FieldCondition, MatchAny
from src.embeddings.vectorstore import get_vectorstore


def retrieve(query: str,top_k: int = 5,tags: list[str] | None = None) -> list[tuple[Document, float]]:
    vectorstore = get_vectorstore()
    results = vectorstore.similarity_search_with_score(query=query,k=top_k)

    return results

def retrieve_and_rerank(query: str,fetch_k: int = 20,top_k: int = 5) -> list[tuple[Document, float]]:
    candidates = retrieve(query, top_k=fetch_k)  # -> liste de (Document, score cosinus)
    docs = [doc for doc, _ in candidates]

    return rerank(query, docs, top_k=top_k)      # -> liste de (Document, score reranker)