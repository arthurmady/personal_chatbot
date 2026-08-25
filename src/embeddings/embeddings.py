from langchain_huggingface import HuggingFaceEmbeddings

class E5Embeddings(HuggingFaceEmbeddings):

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        prefixed = [f"passage: {t}" for t in texts]
        return super().embed_documents(prefixed)

    def embed_query(self, text: str) -> list[float]:
        return super().embed_query(f"query: {text}")


def get_embedding_model() -> E5Embeddings:
    return E5Embeddings(
        model_name="intfloat/multilingual-e5-small",
        encode_kwargs={"normalize_embeddings": True},
    )