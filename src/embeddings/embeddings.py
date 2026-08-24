from langchain_huggingface import HuggingFaceEmbeddings

def get_embedding_model() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name="intfloat/multilingual-e5-small",
        encode_kwargs={"normalize_embeddings": True},
    )