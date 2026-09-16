import json
from pathlib import Path

from src.config import CHUNKS_PATH


def load_chunks(path=CHUNKS_PATH):
    """
    Load processed document chunks from JSON.
    """

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Chunks file not found: {path}"
        )

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)