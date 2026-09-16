import chromadb

from src.config import DB_PATH


def get_client():
    """
    Return a persistent ChromaDB client.
    """

    DB_PATH.mkdir(parents=True, exist_ok=True)

    return chromadb.PersistentClient(
        path=str(DB_PATH)
    )


def get_collection(
    collection_name="education_documents",
):
    """
    Get or create the education documents collection.
    """

    client = get_client()

    return client.get_or_create_collection(
        name=collection_name,
        metadata={
            "description": "Educational knowledge base",
            "hnsw:space": "cosine",
        },
    )


def reset_collection(
    collection_name="education_documents",
):
    """
    Delete existing collection if it exists, and create a fresh one.
    """

    client = get_client()

    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    return get_collection(collection_name)