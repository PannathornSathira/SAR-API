# app/vector_store.py

import os
import json
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest_models
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore, FastEmbedSparse, RetrievalMode
from app.config import QDRANT_URL, OPENAI_API_KEY

REGISTRY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "collections_registry.json")

# Initialize models
embeddings = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=OPENAI_API_KEY)
sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")

# Initialize Client
client = QdrantClient(url=QDRANT_URL)

def load_registry() -> list[str]:
    """Loads the list of collection names created within this project."""
    if not os.path.exists(REGISTRY_PATH):
        return []
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Vector Store] Error reading registry: {e}")
        return []

def save_registry(collections: list[str]):
    """Saves the list of collection names created within this project."""
    try:
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(collections, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Vector Store] Error saving registry: {e}")

def get_collections() -> list[str]:
    """Returns only the collection names registered in this application that still exist in Qdrant."""
    registry = load_registry()
    valid_collections = []
    
    try:
        # Check actual collections in Qdrant
        qdrant_collections = [col.name for col in client.get_collections().collections]
        for name in registry:
            if name in qdrant_collections:
                valid_collections.append(name)
    except Exception as e:
        print(f"[Vector Store] Error querying Qdrant collections: {e}")
        # Fallback to local registry if Qdrant is down or errored
        return registry
        
    return valid_collections

def create_collection(collection_name: str) -> bool:
    """Creates a new Qdrant collection configured for Dense + Sparse Hybrid Search."""
    collection_name = collection_name.strip().lower()
    
    # 1. Clean collection name (Qdrant doesn't support special chars in names)
    import re
    collection_name = re.sub(r'[^a-z0-9_-]', '_', collection_name)
    
    if not collection_name:
        raise ValueError("Invalid collection name")
        
    try:
        # Check if already exists in Qdrant
        if client.collection_exists(collection_name):
            print(f"[Vector Store] Collection '{collection_name}' already exists.")
        else:
            # Config vectors (OpenAI Dense + BM25 Sparse)
            client.create_collection(
                collection_name=collection_name,
                vectors_config=rest_models.VectorParams(
                    size=3072, # text-embedding-3-large
                    distance=rest_models.Distance.COSINE
                ),
                sparse_vectors_config={
                    "fastembed-sparse": rest_models.SparseVectorParams(
                        modifier=rest_models.Modifier.IDF
                    )
                }
            )
            print(f"[Vector Store] Collection '{collection_name}' created successfully in Qdrant.")
            
        # Update local registry if not already present
        registry = load_registry()
        if collection_name not in registry:
            registry.append(collection_name)
            save_registry(registry)
            
        return True
    except Exception as e:
        print(f"[Vector Store] Error creating collection: {e}")
        raise e

def get_vector_store(collection_name: str) -> QdrantVectorStore:
    """Returns a LangChain QdrantVectorStore instance configured for hybrid search."""
    return QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings,
        sparse_embedding=sparse_embeddings,
        retrieval_mode=RetrievalMode.HYBRID,
        sparse_vector_name="fastembed-sparse"
    )
