# SAR Engine Manager & API Service

A standalone, single-user system that allows users to upload documents, automatically extract them into FAQ pairs using an LLM, review/edit the extraction in an Admin UI, ingest them into Qdrant, and query them using a highly-optimized hybrid dense-sparse RAG pipeline.

---

## System Components

1. **FastAPI Backend (`backend/`)**: Manages file text extraction (with page numbers), customizable LLM FAQ generation (by language and count), query expansion (paraphrasing questions x5 before embedding), Qdrant collection creation (dense + sparse configurations), and handles dynamic query endpoints (`/api/v1/query/{collection_name}`) with tokenization, retrieval, and CrossEncoder reranking. The backend also calculates and returns OpenAI API cost estimations for transparency.
2. **Vue 3 Admin Frontend (`frontend/`)**: Provides drag-and-drop multi-document ingestion staging, configurable extraction settings (language, target question count), sequential processing with progress tracking, an interactive FAQ review grid, and an API Playground to test retrieval metrics and inspect match types.
3. **Qdrant Vector Database**: Storing and retrieving collections in hybrid mode (OpenAI Embeddings + BM25 Sparse Embeddings).

---

## 1. Prerequisites & Database Setup

### Run Qdrant Vector Database
You must have a running Qdrant instance. This project includes a `docker-compose.yml` configuration configured to mount storage directly inside the project and map to port `6335` (to avoid conflicts with default ports of other projects). Start it by running this command at the root of the project:
```bash
docker compose up -d
```
By default, the backend connects to `http://localhost:6335`.

### Environment Variables
You need an OpenAI API key. Create a `.env` file in the `backend/` directory:
```env
OPENAI_API_KEY=your-openai-api-key-here
QDRANT_URL=http://localhost:6335
ALLOW_OWN_KNOWLEDGE=false
PORT=8000
```

---

## 2. Backend Setup

1. **Navigate to the backend folder**:
   ```bash
   cd backend
   ```
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Start the backend server**:
   ```bash
   python run.py
   ```
   The backend API will run at `http://localhost:8000`.

---

## 3. Frontend Setup

1. **Navigate to the frontend folder**:
   ```bash
   cd ../frontend
   ```
2. **Install node dependencies**:
   ```bash
   npm install
   ```
3. **Start the Vite development server**:
   ```bash
   npm run dev
   ```
   The Admin UI dashboard will run at `http://localhost:5173`.

---

## 4. Query RAG Pipeline Logic

When external systems call the dynamic endpoint:
`POST /api/v1/query/{collection_name}`

The backend runs:
1. **Query Rewriting**: If `chat_history` is provided, `gpt-4o-mini` rephrases it to be conversational-context aware.
2. **Language Tokenization**: If the query contains Thai unicode, PyThaiNLP tokenizes the query inserting spaces so Qdrant's BM25 sparse index matches accurately.
3. **Hybrid Search**: Dense (OpenAI text-embedding-3-large) + Sparse (BM25) search on Qdrant, retrieving top 5.
4. **CrossEncoder Reranking**: Documents are reranked on CPU/GPU using `BAAI/bge-reranker-v2-m3`. Scores are normalized with Sigmoid to `[0.0, 1.0]`. Top 3 are kept.
5. **Thresholding**:
   - `score >= 0.525` -> Paraphrases context (Exact match)
   - `0.30 <= score < 0.525` -> Paraphrases context (Related match)
   - `score < 0.30` -> Fallback to own knowledge (if enabled) or standard Thai fallback message.
