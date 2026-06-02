# app/retrieval.py

import re
import math
import time
from pythainlp.tokenize import word_tokenize
from app.vector_store import get_vector_store

_reranker_model = None

def get_reranker_model():
    """Lazily loads the reranker model on CUDA, MPS, or CPU."""
    global _reranker_model
    if _reranker_model is None:
        import torch
        from sentence_transformers import CrossEncoder
        device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
        print(f"[Reranker] Loading CrossEncoder 'BAAI/bge-reranker-v2-m3' on '{device}'...")
        _reranker_model = CrossEncoder('BAAI/bge-reranker-v2-m3', device=device)
    return _reranker_model

def tokenize_query_if_thai(query: str) -> str:
    """Detects if query has Thai characters and tokenizes with word spaces."""
    has_thai = bool(re.search(r'[\u0E00-\u0E7F]', query))
    if has_thai:
        # Segment Thai words using newmm engine and join with spaces
        tokenized = " ".join(word_tokenize(query, engine="newmm"))
        print(f"[Tokenization] Original: '{query}' -> Space-separated: '{tokenized}'")
        return tokenized
    return query

def retrieve_and_rerank(collection_name: str, query: str) -> tuple[list, float]:
    """
    Searches Qdrant, reranks documents, and normalizes scores.
    Returns a list of dictionaries with context details and the highest score.
    """
    start_time = time.time()
    
    # 1. Prepare query for sparse BM25
    processed_query = tokenize_query_if_thai(query)
    
    # 2. Connect to vector store and query top 5 documents
    try:
        store = get_vector_store(collection_name)
        initial_results = store.similarity_search_with_score(processed_query, k=5)
    except Exception as e:
        print(f"[Retrieval] Error querying Qdrant: {e}")
        return [], 0.0
        
    if not initial_results:
        return [], 0.0
        
    # 3. Compile context pairs for cross-encoder reranking
    initial_docs = [doc for doc, _ in initial_results]
    
    # The pairs are of format: [user_query, document_text]
    pairs = []
    for doc in initial_docs:
        doc_text = doc.page_content
        # Or construct from original_question and answer if present in metadata
        original_q = doc.metadata.get("original_question", "")
        answer = doc.metadata.get("answer", "")
        if original_q and answer:
            doc_text = f"คำถาม: {original_q}\nคำตอบ: {answer}"
        pairs.append([query, doc_text])
        
    # 4. Run Reranker
    try:
        reranker = get_reranker_model()
        raw_scores = reranker.predict(pairs)
    except Exception as e:
        print(f"[Reranker] Error running model: {e}. Falling back to default ordering.")
        raw_scores = [0.0] * len(initial_docs)
        
    # 5. Sigmoid normalization
    scores = [1 / (1 + math.exp(-s)) for s in raw_scores]
    
    # Combine docs with normalized reranker scores and sort descending
    reranked_docs = list(zip(initial_docs, scores))
    reranked_docs.sort(key=lambda x: x[1], reverse=True)
    
    best_score = float(reranked_docs[0][1]) if reranked_docs else 0.0
    print(f"[RAG] Search complete in {time.time() - start_time:.4f}s. Best score: {best_score:.4f}")
    
    # Filter top 3 documents
    final_docs = reranked_docs[:3]
    
    context_list = []
    for doc, score in final_docs:
        meta = doc.metadata or {}
        context_list.append({
            "content": doc.page_content,
            "source_file": meta.get("source_file", "unknown"),
            "category": meta.get("category", "No Category"),
            "score": float(score)
        })
        
    return context_list, best_score
