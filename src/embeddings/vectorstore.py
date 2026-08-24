from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from langchain_core.documents import Document

from src.embeddings.embeddings import get_embedding_model
from config import QDRANT_URL

COLLECTION_NAME = "personal_chatbot"
VECTOR_SIZE = 384  # dimension de multilingual-e5-small (change si tu changes de modèle)

def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)

def ensure_collection_exists() -> None:
    client = get_qdrant_client()
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

def get_vectorstore() -> QdrantVectorStore:
    ensure_collection_exists()
    embeddings = get_embedding_model()
    return QdrantVectorStore(
        client=get_qdrant_client(),
        collection_name=COLLECTION_NAME,
        embedding=embeddings,
    )

def index_chunks(chunks: list[Document]) -> None:
    vectorstore = get_vectorstore()
    vectorstore.add_documents(chunks)