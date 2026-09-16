from src.embeddings.loader import load_chunks
from src.embeddings.generator import generate_embeddings
from src.embeddings.builder import (
    build_embedded_documents,
    save_embedded_documents,
)


def main():

    chunks = load_chunks()

    print(f"Loaded {len(chunks)} chunks")

    embeddings = generate_embeddings(chunks)

    print(
        f"Generated embeddings: "
        f"{len(embeddings)}"
    )

    if embeddings:
        print(
            f"Embedding dimension: "
            f"{len(embeddings[0])}"
        )

    embedded_documents = build_embedded_documents(
        chunks,
        embeddings,
    )

    print(
        f"Built {len(embedded_documents)} "
        f"embedded documents"
    )

    save_embedded_documents(
        embedded_documents
    )


if __name__ == "__main__":
    main()