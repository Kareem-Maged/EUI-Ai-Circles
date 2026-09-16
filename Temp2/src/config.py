from pathlib import Path

RAW_DATA_PATH = Path("data/1st prep/semester1/science/raw")

PROCESSED_DATA_PATH = Path("data/1st prep/semester1/science/processed")

CHUNKS_PATH = PROCESSED_DATA_PATH / "chunks.json"

EMBEDDED_DOCUMENTS_PATH = PROCESSED_DATA_PATH / "embedded_documents.json"


DB_PATH = Path("data/1st prep/semester1/science/chromadb")