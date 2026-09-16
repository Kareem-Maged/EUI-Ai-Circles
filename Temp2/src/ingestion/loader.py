import json
from pathlib import Path

from src.config import RAW_DATA_PATH


def load_documents(data_dir=RAW_DATA_PATH):
    """
    Load structured JSON curriculum files.

    Each lesson JSON contains:
        - unit_metadata
        - knowledge_chunks

    Returns:
        [
            {
                "source": "U1_L1.json",
                "metadata": {...},
                "chunks": [...]
            }
        ]
    """

    documents = []

    for file_path in Path(data_dir).glob("*.json"):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Skip curriculum.json for now because it contains
        # table of contents rather than knowledge chunks.
        if "knowledge_chunks" not in data:
            continue

        documents.append(
            {
                "source": file_path.name,
                "metadata": data.get("unit_metadata", {}),
                "chunks": data["knowledge_chunks"],
            }
        )

    return documents