# EUI Hackathon AI Circles

## 🚀 Project Setup

Follow the steps below to clone the project and set up the development environment.

### 1. Clone the repository

```bash
git clone https://github.com/amrhany964/EUI-Hackathon-Ai-Circles.git
```

### 2. Navigate to the project directory

```bash
cd EUI-Hackathon-Ai-Circles
```

### 3. Install `uv`

Make sure `uv` is installed on your machine.

Check if it is already installed:

```bash
uv --version
```

If `uv` is not installed, install it before continuing.

### 4. Create and sync the project environment

Run:

```bash
uv sync
```

This will automatically:

- Create the project's `.venv` virtual environment.
- Install all project dependencies.
- Use the Python version specified in `.python-version`.
- Use `uv.lock` to install the locked dependency versions.

### 5. Activate the virtual environment

#### Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
```

You should see `(.venv)` at the beginning of your terminal.

### 6. Verify the Python version

The project currently uses Python 3.14.

```bash
python --version
```

Expected:

```text
Python 3.14.x
```

### 7. Configure environment variables

Create a `.env` file in the project root using `.env.example` as a template.

For example:

```text
.env.example → .env
```

Add your required API keys and environment variables to `.env`.

> **Important:** Never commit or push your `.env` file to GitHub.

---

## ▶️ Running the Project

After completing the setup, run:

```bash
uv run python main.py
```

---

## 📦 Managing Dependencies

This project uses `uv` to manage Python dependencies.

To add a new package:

```bash
uv add <package-name>
```

For example:

```bash
uv add fastapi
```

`uv` will automatically update:

- `pyproject.toml`
- `uv.lock`
- The project environment

After adding a dependency, commit the updated files:

```bash
git add .
git commit -m "Add <package-name> dependency"
git push
```

---

## 🔄 Getting the Latest Changes

Before starting work:

```bash
git pull
uv sync
```

This keeps your local environment synchronized with the latest project dependencies.

---

## 👥 Team Workflow

1. Create a new branch for your task.
2. Make your changes.
3. Test your changes locally.
4. Commit your changes.
5. Push your branch.
6. Open a Pull Request.

Create a new branch:

```bash
git checkout -b feature/your-task
```

Then:

```bash
git add .
git commit -m "Implement your task"
git push -u origin feature/your-task
```

---

## 📁 Important Project Files

| File | Purpose |
|---|---|
| `.python-version` | Specifies the Python version used by the project |
| `pyproject.toml` | Project configuration and dependencies |
| `uv.lock` | Locks dependency versions for reproducible environments |
| `.env.example` | Template for required environment variables |
| `.env` | Local environment variables and secrets — do not commit |
| `.venv/` | Local virtual environment — do not commit |



## RAG Pipeline

The project is currently organized into four main phases:

### Phase 1 — Ingestion

The ingestion phase prepares the raw educational documents for the RAG pipeline.

It performs:
- Loading PDF documents.
- Cleaning extracted text.
- Splitting documents into smaller chunks.
- Saving the processed chunks as JSON.

**Output:**
```text
data/.../processed/chunks.json
```

### Phase 2 — Embeddings

The embeddings phase converts each document chunk into a numerical vector using the configured embedding model.

It performs:
- Loading the processed chunks.
- Generating normalized embeddings.
- Combining chunks with their embeddings.
- Saving the embedded documents.

**Output:**
```text
data/.../processed/embedded_documents.json
```

### Phase 3 — Vector Database

The Vector DB phase stores the embedded documents in ChromaDB for efficient semantic search.

It performs:
- Loading embedded documents.
- Creating/updating the ChromaDB collection.
- Indexing document texts, embeddings, and metadata.

**Output:**
```text
data/.../chromadb/
```

### Phase 4 — Retrieval

The retrieval phase takes a user's question and retrieves the most relevant chunks from ChromaDB.

It performs:
- Converting the user query into an embedding.
- Searching ChromaDB using semantic similarity.
- Retrieving the most relevant chunks.
- Building the retrieved context.

---

## Data Setup

Before running the pipeline, place your educational documents inside the `raw` folder specified by `config.py`.

The data path is configured in:

```text
src/config.py
```

For example:

```python
RAW_DATA_PATH = Path(
    "data/3rd prep/semester1/science/raw"
)
```

Place your PDF files inside this folder:

```text
data/
└── 3rd prep/
    └── semester1/
        └── science/
            └── raw/
                └── your_document.pdf
```

You can change the data path from `src/config.py` if you want to use a different subject, grade, or semester.

---

## Running the RAG Pipeline

Run the phases in the following order:

### 1. Run Ingestion

```bash
python -m src.ingestion.main
```

### 2. Generate Embeddings

```bash
python -m src.embeddings.main
```

### 3. Build Vector Database

```bash
python -m src.vectordb.main
```

### 4. Test Retrieval

```bash
python -m src.retrieval.main
```

After running the four phases, the RAG pipeline will be ready for the next stage.

---

## Project Structure

```text
EUI-Hackathon-Ai-Circles/
│
├── data/
│   └── 3rd prep/
│       └── semester1/
│           └── science/
│               ├── chromadb/
│               ├── processed/
│               │   ├── chunks.json
│               │   └── embedded_documents.json
│               └── raw/
│                   └── your_document.pdf
│
├── src/
│   ├── embeddings/
│   │   ├── __init__.py
│   │   ├── builder.py
│   │   ├── generator.py
│   │   ├── loader.py
│   │   └── main.py
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── chuncker.py
│   │   ├── cleaner.py
│   │   ├── loader.py
│   │   └── main.py
│   │
│   ├── reasoning/
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── context.py
│   │   ├── embedder.py
│   │   ├── main.py
│   │   └── query.py
│   │
│   ├── vectordb/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── indexer.py
│   │   └── main.py
│   │
│   └── config.py
│
├── .env
├── .env.example
├── .gitignore
├── .python-version
├── main.py
├── pyproject.toml
├── README.md
└── uv.lock
```

## Pipeline

```text
Raw PDFs
   ↓
[1] Ingestion
   ↓
chunks.json
   ↓
[2] Embeddings
   ↓
embedded_documents.json
   ↓
[3] Vector DB
   ↓
ChromaDB
   ↓
[4] Retrieval
   ↓
Relevant Context
```
