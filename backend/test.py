from pathlib import Path

from src.generation.conversation import Conversation
from src.generation.generate import generate_answer
from src.ingestion.ingest import ingest


# all_docs = []

# for file in Path("data").glob("*"):
#     if file.is_file():
#         file_path = str(file.resolve())
#         docs_file = ingest(file_path)
#         all_docs.extend(docs_file)
# reponse = generate_answer("Quelles sont ses compétences ?", all_docs)
# print(reponse)


all_docs = []

for file in Path("data").glob("*"):
    if file.is_file():
        file_path = str(file.resolve())
        docs_file = ingest(file_path)
        all_docs.extend(docs_file)

conv = Conversation(all_docs)
print(conv.ask("Quelles sont ses expériences professionnelles ?"))