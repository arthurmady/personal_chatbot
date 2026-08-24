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

text = Path("datas.md").read_text(encoding="utf-8")
chunks = chunk_markdown_by_header(text, source="datas.md", max_chars=500)

for c in chunks:
    print(f"--- {c.metadata['title']} | tags={c.metadata['tags']} ---")
    print(c.page_content)
    print("next")

index_chunks(chunks)