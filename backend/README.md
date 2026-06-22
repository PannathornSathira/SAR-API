# SAR Engine Manager & API Service

This is the backend API for the SAR FAQ system. It handles FAQ extraction from documents, ingestion into Qdrant vector database, and querying using LLMs.

### Key Features
- **Intelligent FAQ Generation:** Automatically extracts FAQ pairs from documents (.pdf, .docx, .txt) using LLM and Rule-based logic.
- **Hybrid Semantic Search:** Uses Dense vectors (OpenAI) and Sparse vectors (BM25) for high accuracy retrieval.
- **Dynamic Multilingual Support:** Automatically detects the user's language and the database's primary language. It dynamically translates queries for optimal hybrid search performance and responds natively in the user's original language!

## Prerequisites
- Python 3.10+
- Qdrant Vector Database (can be run locally via Docker)

## Setup and Installation

### Local Setup
1. Clone the repository and navigate to the backend folder.
2. Install the requirements:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the `.env.example` file to `.env` and fill in your values (specifically the `OPENAI_API_KEY`).
   ```bash
   cp .env.example .env
   ```
4. Run the application:
   ```bash
   python run.py
   ```
   The API will be available at `http://localhost:8000`. You can view the API documentation at `http://localhost:8000/docs`.

---

> [!WARNING]  
> ## 🚨 CRITICAL PRODUCTION NOTES FOR SENIOR DEVELOPER 🚨
> 
> Before deploying this code to a production server, please be aware of the following security configurations that need to be implemented:
> 
> **1. API Security (No Authentication Currently)**  
> Currently, all endpoints (e.g., `/api/v1/extract-faq`, `/api/v1/query`) are fully open. Because these endpoints call OpenAI's LLMs which incur costs, **you should add an API Key authentication mechanism** (e.g., using FastAPI's `APIKeyHeader` or `HTTPBearer`) to prevent unauthorized access and potential abuse of your OpenAI quota. The current setup assumes only a single trusted user/frontend.
>
> **2. CORS Configuration (Fully Open Currently)**  
> The `CORSMiddleware` in `app/main.py` is currently set to `allow_origins=["*"]`. This means any website on the internet can make requests to this API. In production, this must be restricted to only the domains of your frontend applications.
> 
> **Please address these two items before opening this server to the internet.**

---

### Docker Deployment

For easy deployment, the entire stack (Frontend, Backend, Database) is orchestrated via Docker Compose in the root directory.

1. Ensure you have Docker and Docker Compose installed.
2. From the root of the project (not the backend folder), run:
   ```bash
   docker-compose up -d --build
   ```
   *Note: When running via Docker Compose, the backend automatically connects to Qdrant internally. You do not need to configure `QDRANT_URL` in your `.env` for Docker deployment.*
