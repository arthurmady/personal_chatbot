# from src.ingestion.ingest import ingest
# from src.chunking.chunk import chunk_documents_by_tokens
# from src.embeddings.vectorstore import index_chunks

# docs = ingest("data/identity.txt")
# chunks = chunk_documents_by_tokens(docs,chunk_size=150,chunk_overlap=40)
# index_chunks(chunks)

# print(chunks)
# # print(f"{len(chunks)} chunks indexés dans Qdrant")


from pathlib import Path
from src.chunking.chunk import chunk_markdown_by_header
from src.embeddings.vectorstore import index_chunks

text = Path("data/datas.md").read_text(encoding="utf-8")
chunks = chunk_markdown_by_header(text, source="data/datas.md", max_chars=500)

index_chunks(chunks)


from src.retrieval.retriever import retrieve_and_rerank

results = retrieve_and_rerank("Il a fait quoi comme formation", fetch_k=20, top_k=5)
for doc, score in results:
    print(f"[{score:.3f}] {doc.metadata['title']}")