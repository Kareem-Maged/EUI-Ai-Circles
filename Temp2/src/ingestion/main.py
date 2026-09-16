import json
from pathlib import Path

from src.ingestion.loader import load_documents
from src.config import CHUNKS_PATH


def save_chunks(chunks, path=CHUNKS_PATH):
    """Save processed chunks to JSON."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            chunks,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Saved {len(chunks)} chunks to {path}")


def main():
    print("Starting document ingestion...")

    # Phase 1: Load structured JSON files
    documents = load_documents()

    print(f"Loaded {len(documents)} documents")

    # Phase 2: Extract pre-chunked knowledge chunks
    chunks = []

    for document in documents:
        for knowledge_chunk in document["chunks"]:

            chunk = {
                "text": knowledge_chunk["content"]["narrative_explanation"],
                "metadata": {
                    "source": document["source"],
                    "chunk_id": knowledge_chunk["chunk_id"],
                    "topic": knowledge_chunk["topic"],
                    "pedagogical_type": knowledge_chunk["pedagogical_type"],
                    **document["metadata"],
                },
            }

            chunks.append(chunk)

    print(f"Generated {len(chunks)} chunks")

    # Phase 3: Save chunks
    save_chunks(chunks, path=CHUNKS_PATH)

    print("Document ingestion completed.")


if __name__ == "__main__":
    main()