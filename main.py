from src.ingestion.ingest import ingest
from src.generation.generate import generate_answer
from pathlib import Path

all_docs = []

for file in Path("data").glob("*"):
    if file.is_file():
        file_path = str(file.resolve())
        docs_file = ingest(file_path)
        all_docs.extend(docs_file)

print(generate_answer("Quels sont ses compétences ?", all_docs))