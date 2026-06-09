# app/faq_generator.py

from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.callbacks import get_openai_callback
from app.prompts import get_faq_extraction_system_prompt, get_question_expansion_system_prompt

# Pydantic schemas for structured extraction
class FAQPair(BaseModel):
    category: str = Field(..., description="Appropriate general topic or category name")
    question: str = Field(..., description="Clear, self-contained and grammatically complete question")
    answer: str = Field(..., description="Detailed answer matching the facts in the text")

class FAQExtractionResult(BaseModel):
    faqs: List[FAQPair]

class QuestionExpansionResult(BaseModel):
    variations: List[str]

def chunk_text(text: str, chunk_size: int = 2000, overlap: int = 500) -> List[str]:
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

def extract_faqs_from_text(text: str, filename: str, language: str = "Thai", num_questions: int = 10) -> List[Dict[str, str]]:
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
    total_cost = 0.0
    
    # Calculate how many questions to ask per chunk to hit the total target
    target_per_chunk = max(1, (num_questions // len(chunks)) + 1)
    
    # 3. Process each chunk
    for i, chunk in enumerate(chunks):
        print(f"[FAQ Generator] Processing chunk {i+1}/{len(chunks)}...")
        try:
            system_prompt = get_faq_extraction_system_prompt(language=language, num_questions=target_per_chunk)
            with get_openai_callback() as cb:
                result = structured_llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Document Source: {filename}\n\nContent Chunk:\n{chunk}")
                ])
                total_cost += cb.total_cost
            
            # Append generated FAQs
            for item in result.faqs:
                extracted_faqs.append({
                    "category": item.category.strip(),
                    "question": item.question.strip(),
                    "answer": item.answer.strip(),
                    "filename": filename,
                    "source_type": "LLM"
                })
        except Exception as e:
            print(f"[FAQ Generator] Error extracting from chunk {i+1}: {e}")
            continue
            
    # Strictly enforce the target question count
    extracted_faqs = extracted_faqs[:num_questions]
            
    print(f"[FAQ Generator] Finished extraction. Generated {len(extracted_faqs)} FAQ pairs.")
    print(f"[FAQ Generator] Extraction Cost (USD): ${total_cost:.4f}")
    return extracted_faqs, total_cost

def expand_faq_questions(faqs: List[Dict[str, str]], language: str = "Thai") -> tuple[List[Dict[str, str]], float]:
    """
    Takes a list of approved FAQs and generates 5 paraphrased question variations for each.
    Returns the expanded list of FAQs (original + variations) and the cost.
    """
    print(f"[FAQ Generator] Starting question expansion for {len(faqs)} FAQs...")
    
    try:
        from app.config import OPENAI_API_KEY
        llm = init_chat_model("gpt-4o-mini", model_provider="openai", openai_api_key=OPENAI_API_KEY)
        structured_llm = llm.with_structured_output(QuestionExpansionResult)
    except Exception as e:
        print(f"[FAQ Generator] Error initializing LLM for expansion: {e}")
        return faqs, 0.0
        
    expanded_faqs = []
    total_cost = 0.0
    system_prompt = get_question_expansion_system_prompt(language=language)
    
    for i, faq in enumerate(faqs):
        print(f"[FAQ Generator] Expanding question {i+1}/{len(faqs)}...")
        expanded_faqs.append(faq) # Always keep the original
        try:
            with get_openai_callback() as cb:
                result = structured_llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Original Question:\n{faq['question']}")
                ])
                total_cost += cb.total_cost
                
            for variation in result.variations:
                expanded_faqs.append({
                    "category": faq["category"],
                    "question": variation.strip(),
                    "answer": faq["answer"],
                    "filename": faq.get("filename", ""),
                    "original_question": faq.get("original_question", faq["question"]),
                    "source_type": faq.get("source_type", "LLM")
                })
        except Exception as e:
            print(f"[FAQ Generator] Error expanding question {i+1}: {e}")
            continue
            
    print(f"[FAQ Generator] Finished expansion. Total pairs now: {len(expanded_faqs)}.")
    print(f"[FAQ Generator] Expansion Cost (USD): ${total_cost:.4f}")
    return expanded_faqs, total_cost
