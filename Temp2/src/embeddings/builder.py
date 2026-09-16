import json
from pathlib import Path

from src.config import EMBEDDED_DOCUMENTS_PATH


def build_embedded_documents(chunks, embeddings):
    """
    Combine chunks with their generated embeddings.
    """

    if len(chunks) != len(embeddings):
        raise ValueError(
            "Number of chunks must match number of embeddings."
        )

    embedded_documents = []

    for chunk, embedding in zip(chunks, embeddings):
        embedded_documents.append(
            {
                "text": chunk["text"],
                "metadata": chunk.get("metadata", {}),
                "embedding": embedding,
            }
        )

    return embedded_documents


def save_embedded_documents(
    documents,
    path=EMBEDDED_DOCUMENTS_PATH,
):
    """
    Save embedded documents to JSON.
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            documents,
            f,
            ensure_ascii=False,
        )

    print(
        f"Saved {len(documents)} embedded documents "
        f"to {path}"
    )