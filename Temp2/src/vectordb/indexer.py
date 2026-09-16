import json
from pathlib import Path

from src.config import EMBEDDED_DOCUMENTS_PATH
from src.vectordb.database import get_collection, reset_collection


def load_embedded_documents(path=EMBEDDED_DOCUMENTS_PATH):
    """
    Load embedded documents from JSON.
    """

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Embedded documents not found: {path}"
        )

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def index_documents(reset=True):
    """
    Index embedded documents into ChromaDB.
    """

    documents = load_embedded_documents()

    if reset:
        collection = reset_collection()
    else:
        collection = get_collection()

    if not documents:
        print("No documents to index.")
        return collection

    ids = [
    f"chunk_{i}"
    for i in range(len(documents))
    ]

    texts = [
        document["text"]
        for document in documents
    ]

    embeddings = [
        document["embedding"]
        for document in documents
    ]

    metadatas = [
        document.get("metadata", {})
        for document in documents
    ]

    collection.upsert(
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )

    print(
        f"Indexed {len(documents)} documents "
        f"into ChromaDB."
    )

    return collection