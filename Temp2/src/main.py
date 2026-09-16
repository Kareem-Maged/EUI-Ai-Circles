from src.ingestion.main import main as ingestion_main
from src.embeddings.main import main as embeddings_main
from src.vectordb.main import main as vectordb_main


def main():
    print("=" * 50)
    print("Starting Sawa-Ed pipeline")
    print("=" * 50)

    # 1. Ingestion
    print("\n[1/3] Running ingestion...")
    ingestion_main()

    # 2. Embeddings
    print("\n[2/3] Running embeddings...")
    embeddings_main()

    # 3. Vector Database
    print("\n[3/3] Running vector database indexing...")
    vectordb_main()

    print("\n" + "=" * 50)
    print("Pipeline completed successfully.")
    print("Reasoning pipeline was not started.")
    print("=" * 50)


if __name__ == "__main__":
    main()