# app/main.py

import io
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.documents import Document

import docx
import pypdf

from app.config import PORT
from app.vector_store import get_collections, create_collection, get_vector_store
from app.faq_generator import extract_faqs_from_text, expand_faq_questions
from app.retrieval import retrieve_and_rerank
from app.agents import rewrite_query, synthesize_answer

app = FastAPI(
    title="SAR Engine Manager & API Service",
    description="Admin UI backend and external integration gateway for the SAR FAQ RAG system."
)

# Enable CORS for frontend API calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Schemas
class CreateCollectionRequest(BaseModel):
    name: str

class FAQItem(BaseModel):
    category: str
    question: str
    answer: str
    filename: Optional[str] = ""

class IngestRequest(BaseModel):
    collection_name: str
    filename: str
    faqs: List[FAQItem]
    language: str = "Thai"

class QueryRequest(BaseModel):
    query: str
    chat_history: List[Dict[str, str]] = []

@app.get("/api/v1/collections")
async def api_get_collections():
    """Lists Qdrant collections created within this app."""
    try:
        cols = get_collections()
        return {"collections": cols}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/collections/create")
async def api_create_collection(req: CreateCollectionRequest):
    """Creates a new Qdrant collection configured for hybrid search."""
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Collection name cannot be empty")
    try:
        create_collection(req.name)
        return {"status": "success", "collection": req.name.strip().lower()}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/extract-faq")
async def api_extract_faq(
    file: UploadFile = File(...),
    language: str = Form("Thai"),
    num_questions: int = Form(10)
):
    """Extracts clean text from a document and generates FAQ pairs."""
    filename = file.filename
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    
    if ext not in ["docx", "pdf", "txt"]:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: .{ext}. Supported formats are .docx, .pdf, .txt")
        
    try:
        file_bytes = await file.read()
        text = ""
        
        # 1. Clean Text Extraction
        if ext == "docx":
            doc = docx.Document(io.BytesIO(file_bytes))
            # Extract text paragraph by paragraph
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        elif ext == "pdf":
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            text_pages = []
            for i, page in enumerate(reader.pages):
                t = page.extract_text()
                if t:
                    text_pages.append(f"--- Page {i+1} ---\n{t}")
            text = "\n".join(text_pages)
        elif ext == "txt":
            text = file_bytes.decode("utf-8", errors="ignore")
            
        if not text.strip():
            raise HTTPException(status_code=400, detail="No readable text found in document.")
            
        # 2. FAQ Extraction using modular generator
        extracted_faqs, extraction_cost = extract_faqs_from_text(text, filename, language, num_questions)
        
        return {
            "filename": filename,
            "faqs": extracted_faqs,
            "extraction_cost": extraction_cost
        }
    except Exception as e:
        print(f"[main] Error during text extraction/FAQ generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/collections/ingest")
async def api_ingest_faqs(req: IngestRequest):
    """Embeds and saves the FAQ pairs to the chosen Qdrant collection."""
    if not req.faqs:
        raise HTTPException(status_code=400, detail="FAQ list is empty")
        
    try:
        # 1. Expand FAQs
        faqs_to_expand = []
        for faq in req.faqs:
            d = faq.model_dump() if hasattr(faq, 'model_dump') else faq.dict()
            d['original_question'] = faq.question
            faqs_to_expand.append(d)
            
        expanded_faqs, expansion_cost = expand_faq_questions(faqs_to_expand, language=req.language)

        # 2. Create documents
        docs = []
        for faq in expanded_faqs:
            page_content = f"Question: {faq['question']}\nAnswer: {faq['answer']}"
            metadata = {
                "category": faq['category'],
                "original_question": faq['original_question'],
                "answer": faq['answer'],
                "source_file": faq.get('filename') or req.filename
            }
            docs.append(Document(page_content=page_content, metadata=metadata))
            
        # Add to vector store in hybrid mode
        store = get_vector_store(req.collection_name)
        store.add_documents(docs)
        
        return {"status": "success", "count": len(docs), "expansion_cost": expansion_cost}
    except Exception as e:
        print(f"[main] Error during ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/query/{collection_name}")
async def api_query_collection(collection_name: str, req: QueryRequest):
    """Exposes a dynamic RAG endpoint for external application queries."""
    # Ensure collection exists
    collection_name = collection_name.strip().lower()
    valid_cols = get_collections()
    if collection_name not in valid_cols:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found or not initialized in this app")
        
    try:
        # 1. Query Rewrite (using memory)
        rewritten = rewrite_query(req.query, req.chat_history)
        
        # 2. Retrieve & Rerank (using tokenization and CrossEncoder)
        contexts, best_score = retrieve_and_rerank(collection_name, rewritten)
        
        # 3. Synthesize Answer (Threshold logic + Fallback)
        response_text, match_type = synthesize_answer(rewritten, contexts, best_score)
        
        # Format sources
        sources = list(set([c["source_file"] for c in contexts]))
        
        # Format context for return JSON
        formatted_context = [
            {
                "content": c["content"],
                "source_file": c["source_file"],
                "category": c["category"]
            }
            for c in contexts
        ]
        
        return {
            "response": response_text,
            "match_type": match_type,
            "score": best_score,
            "sources": sources,
            "context": formatted_context
        }
    except Exception as e:
        print(f"[main] Error querying collection '{collection_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))
