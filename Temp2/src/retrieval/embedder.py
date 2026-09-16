from sentence_transformers import SentenceTransformer

from src.embeddings.generator import MODEL_NAME


model = SentenceTransformer(MODEL_NAME)


def embed_query(query: str):
    embedding = model.encode(
        query,
        normalize_embeddings=True,
    )

    return embedding.tolist()