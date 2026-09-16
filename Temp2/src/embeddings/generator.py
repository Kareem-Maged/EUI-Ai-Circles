import os

from sentence_transformers import SentenceTransformer


MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)


def load_embedding_model():
    """
    Load the configured embedding model.
    """

    print(f"Loading embedding model: {MODEL_NAME}")

    return SentenceTransformer(MODEL_NAME)


def generate_embeddings(chunks):
    """
    Generate normalized embeddings for document chunks.
    """

    if not chunks:
        return []

    model = load_embedding_model()

    texts = [chunk["text"] for chunk in chunks]

    embeddings = model.encode(
        texts,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    return embeddings.tolist()