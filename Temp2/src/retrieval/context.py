def format_citation(metadata: dict) -> str:
    """
    Format citation from curriculum metadata.
    """

    subject = metadata.get("subject", "")
    unit = metadata.get("unit_title", "")
    lesson = metadata.get("lesson_title", "")

    return f"[{subject} | {unit} | {lesson}]"


def build_context(results: dict) -> str:
    """
    Build context from retrieved documents.
    """

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]

    context_parts = []

    for document_id, document, metadata, distance in zip(
        ids,
        documents,
        metadatas,
        distances,
    ):
        citation = format_citation(metadata)

        similarity = 1 - distance

        context_parts.append(
            f"--- Evidence Chunk ({citation}) ---\n"
            f"Chunk ID: {document_id}\n"
            f"Similarity: {similarity:.4f}\n"
            f"Content:\n{document}"
        )

    return "\n\n---\n\n".join(context_parts)