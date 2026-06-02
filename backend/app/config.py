import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
ALLOW_OWN_KNOWLEDGE = os.getenv("ALLOW_OWN_KNOWLEDGE", "false").lower() == "true"
PORT = int(os.getenv("PORT", "8000"))

# Basic validation
if not OPENAI_API_KEY:
    print("[WARNING] OPENAI_API_KEY is not set. LLM features and embeddings will fail.")
