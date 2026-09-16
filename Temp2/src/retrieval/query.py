from src.retrieval.embedder import embed_query
from src.vectordb.database import get_collection


def retrieve_documents(query: str, n_results=8):
    query_embedding = embed_query(query)

    collection = get_collection()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],

    )

    return results