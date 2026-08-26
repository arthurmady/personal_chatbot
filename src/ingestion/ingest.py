from pathlib import Path
from langchain_core.documents import Document
from langchain_community.document_loaders import (PyPDFLoader,Docx2txtLoader,TextLoader,WebBaseLoader)

def ingest(path_or_url: str) -> list[Document]:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        loader = WebBaseLoader(path_or_url)
        docs_file = loader.load()
 
    else:
        path = Path(path_or_url)
        if not path.exists():
            raise FileNotFoundError(f"Fichier introuvable : {path_or_url}")
 
        suffix = path.suffix.lower()
 
        if suffix == ".pdf":
            loader = PyPDFLoader(str(path))
        elif suffix == ".docx":
            loader = Docx2txtLoader(str(path))
        elif suffix in (".txt", ".md"):
            loader = TextLoader(str(path), encoding="utf-8")
        else:
            raise ValueError(f"Format non supporté : {suffix}")
 
        docs_file = loader.load()
 
    for doc in docs_file:
        doc.metadata.setdefault("source", path_or_url)
 
    return docs_file