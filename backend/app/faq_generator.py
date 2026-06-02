# app/faq_generator.py

from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from app.prompts import get_faq_extraction_system_prompt

# Pydantic schemas for structured extraction
class FAQPair(BaseModel):
    category: str = Field(..., description="Appropriate general topic or category name")
    question: str = Field(..., description="Clear, self-contained and grammatically complete question")
    answer: str = Field(..., description="Detailed answer matching the facts in the text")

class FAQExtractionResult(BaseModel):
    faqs: List[FAQPair]

def chunk_text(text: str, chunk_size: int = 5000, overlap: int = 500) -> List[str]:
    """Chunks text into sizes of chunk_size with some overlap."""
    if not text:
        return []
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def extract_faqs_from_text(text: str, filename: str) -> List[Dict[str, str]]:
    """
    Analyzes document text and extracts a list of high-quality FAQ pairs.
    
    Note for Developer Team:
    You can easily replace the LLM call inside this function with your team's
    custom logic or fine-tuned model. The function must return a list of dicts:
    [
        {"category": "...", "question": "...", "answer": "..."},
        ...
    ]
    """
    print(f"[FAQ Generator] Starting extraction for {filename} (Length: {len(text)} chars)")
    
    # 1. Chunk the text if it exceeds context/optimal processing limits
    # We use 5000 chars as specified (approx 1200-1500 tokens in Thai)
    chunks = chunk_text(text, chunk_size=5000, overlap=500)
    print(f"[FAQ Generator] Chunked text into {len(chunks)} chunks")
    
    # 2. Setup the LLM with structured output
    try:
        from app.config import OPENAI_API_KEY
        # Initialize GPT-4o-mini with explicit API key
        llm = init_chat_model("gpt-4o-mini", model_provider="openai", openai_api_key=OPENAI_API_KEY)
        structured_llm = llm.with_structured_output(FAQExtractionResult)
    except Exception as e:
        print(f"[FAQ Generator] Error initializing LLM: {e}. Falling back to empty lists.")
        return []
        
    extracted_faqs = []
    
    # 3. Process each chunk
    for i, chunk in enumerate(chunks):
        print(f"[FAQ Generator] Processing chunk {i+1}/{len(chunks)}...")
        try:
            system_prompt = get_faq_extraction_system_prompt()
            result = structured_llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Document Source: {filename}\n\nContent Chunk:\n{chunk}")
            ])
            
            # Append generated FAQs
            for item in result.faqs:
                extracted_faqs.append({
                    "category": item.category.strip(),
                    "question": item.question.strip(),
                    "answer": item.answer.strip()
                })
        except Exception as e:
            print(f"[FAQ Generator] Error extracting from chunk {i+1}: {e}")
            continue
            
    print(f"[FAQ Generator] Finished extraction. Generated {len(extracted_faqs)} FAQ pairs.")
    return extracted_faqs
