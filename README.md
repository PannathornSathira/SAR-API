# SAR Engine Manager & API Service

A standalone, single-user SAR system that allows users to upload documents, automatically extract them into FAQ pairs using an LLM as a language expert or a cleaned rule-based approach, review/edit the extraction in a modular Admin UI, ingest them into Qdrant, and query them using a highly-optimized hybrid dense-sparse SAR pipeline.

---

## System Components

1. **FastAPI Backend (`backend/`)**: 
   - Manages text extraction (with page numbers) from uploaded files.
   - Generates customizable LLM FAQs (by language and count) or cleans rule-based extractions with an LLM for grammar, context, and formatting.
   - Calculates OpenAI API cost estimations dynamically.
   - Handles query expansion (paraphrasing questions x5 before embedding).
   - Manages Qdrant collection creation (dense + sparse configurations).
   - Serves dynamic query endpoints (`/api/v1/query/{collection_name}`) with tokenization, retrieval, and CrossEncoder reranking.
   - Automatically exports ingested FAQs to local CSV files for record-keeping.
   - Exposes a retrieval endpoint to fetch live FAQ samples directly from collections in Qdrant.

2. **Vue 3 Admin Frontend (`frontend/`)**: 
   - Provides a modular, senior-architected user interface.
   - **Ingestion Panel**: Drag-and-drop multi-document ingestion staging, settings configuration (language, question quantity), step-by-step sequential progress tracking, and interactive FAQ editing grid.
   - **Manual FAQ Additions**: Allows users to manually create new FAQ pairs on-the-fly before final vector database ingestion.
   - **System Dashboard**: Displays active collections, total FAQ points count, active statuses, and supports interactive clicking on collections to inspect live FAQ pairs stored inside Qdrant.
   - **API Playground**: Allows developers to test retrieval metrics, query terms, and inspect match types.

3. **Qdrant Vector Database**: Storing and retrieving collections in hybrid mode (OpenAI Embeddings + BM25 Sparse Embeddings).

---

## 1. Quick Start: Docker Deployment (Recommended)

The easiest way to run the entire SAR Engine Manager (Frontend, Backend, and Database) is using Docker Compose. This ensures a consistent environment and zero manual configuration for database connections.

1. **Clone the repository.**
2. **Create backend environment variables**:
   ```bash
   cp backend/.env.example backend/.env
   ```
   *Edit `backend/.env` and add your `OPENAI_API_KEY`.*
3. **Start the whole stack**:
   ```bash
   docker-compose up -d --build
   ```

Once running, you can access the services at:
- **Admin UI (Frontend)**: `http://localhost:80`
- **API Documentation (Backend)**: `http://localhost:8000/docs`
- **Qdrant DB**: `http://localhost:6335`

---

## 2. Local Development Setup (Manual)

If you prefer to run the services manually without Docker (e.g., for active development):

### Backend Setup
1. **Navigate to the backend folder**:
   ```bash
   cd backend
   ```
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Set up `.env`**: Copy `.env.example` to `.env` and add your OpenAI key. For local dev, `QDRANT_URL=http://localhost:6335` is correct.
4. **Start the backend server**:
   ```bash
   python run.py
   ```

### Frontend Setup
1. **Navigate to the frontend folder**:
   ```bash
   cd frontend
   ```
2. **Install node dependencies**:
   ```bash
   npm install
   ```
3. **Set up `.env`**: Copy `.env.example` to `.env`. For local dev, `VITE_API_URL=http://localhost:8000` is correct.
4. **Start the Vite development server**:
   ```bash
   npm run dev
   ```

---

## 4. Query SAR Pipeline Logic

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
