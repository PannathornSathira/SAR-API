# app/agents.py

from typing import Optional
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import ALLOW_OWN_KNOWLEDGE, OPENAI_API_KEY
from app.prompts import get_query_rewrite_system_prompt, get_paraphrase_system_prompt

def rewrite_query(query: str, chat_history: list[dict]) -> str:
    """Rewrites the query into a standalone search query if chat history exists."""
    if not chat_history:
        return query
        
    recent_history = chat_history[-5:]
    history_text = ""
    for turn in recent_history:
        role = "User" if turn.get("role") == "user" else "Assistant"
        history_text += f"{role}: {turn.get('content', '')}\n"
        
    system_prompt = get_query_rewrite_system_prompt()
    human_prompt = f"Chat History:\n{history_text}\nFollow-up question: {query}\nStandalone Query:"
    
    try:
        # Using gpt-4o-mini for cheap and fast rewrites
        llm = init_chat_model("gpt-4o-mini", model_provider="openai", openai_api_key=OPENAI_API_KEY)
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])
        standalone = response.content.strip()
        print(f"[Agents] Query Rewrite: '{query}' -> '{standalone}'")
        return standalone
    except Exception as e:
        print(f"[Agents] Error rewriting query: {e}. Using original.")
        return query

def synthesize_answer(
    query: str,
    contexts: list[dict],
    best_score: float,
    allow_own_knowledge: Optional[bool] = None
) -> tuple[str, str]:
    """
    Writes the answer based on Reranker score and system-selected context.
    Returns (response_text, match_type).
    
    Threshold Logic:
    - Exact Match (score >= 0.525): Paraphrase the selected knowledge-base answer.
    - Related Match (0.30 <= score < 0.525): Summarize selected related FAQ contexts.
    - No Match (score < 0.30):
        - If own knowledge is enabled -> Answer using LLM knowledge + [OWN_KNOWLEDGE] tag.
        - If disabled -> Return standard Thai fallback.
    """
    can_use_own_knowledge = ALLOW_OWN_KNOWLEDGE if allow_own_knowledge is None else allow_own_knowledge
    fallback_message = "ต้องขออภัยด้วยนะคะ ข้อมูลที่คุณค้นหาอยู่นอกเหนือขอบเขตในฐานข้อมูล..."
    
    # 1. Determine Tier
    if best_score >= 0.525 and contexts:
        tier = "exact"
    elif best_score >= 0.30 and contexts:
        tier = "related"
    else:
        tier = "none"
        
    # 2. Short-circuit if no match and own knowledge is disabled
    if tier == "none" and not can_use_own_knowledge:
        print("[Agents] Score is below threshold and own knowledge is disabled. Returning fallback.")
        return fallback_message, "none"
        
    # 3. Setup prompt
    system_prompt = get_paraphrase_system_prompt(tier, can_use_own_knowledge)
    
    # Format context for LLM
    context_text = ""
    for idx, c in enumerate(contexts):
        context_text += f"Document {idx+1} [Source: {c['source_file']}, Category: {c['category']}]:\n{c['content']}\n\n"
        
    human_prompt = f"Context:\n{context_text}\nUser Question: {query}\nAssistant:"
    
    try:
        # Use gpt-4o-mini for quick generation
        llm = init_chat_model("gpt-4o-mini", model_provider="openai", openai_api_key=OPENAI_API_KEY)
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ])
        ans = response.content.strip()
        
        # 4. Clean up response tag and prepend badges
        if "[OWN_KNOWLEDGE]" in ans:
            ans = ans.replace("[OWN_KNOWLEDGE]", "").strip()
            ans = f"💡 ข้อมูลทั่วไปเบื้องต้น (นอกเหนือจากฐานข้อมูลของ ETDA):\n\n{ans}"
            return ans, "own_knowledge"
            
        if "UNKNOWN_INFO" in ans:
            return fallback_message, "none"
            
        return ans, tier
        
    except Exception as e:
        print(f"[Agents] Error during synthesis: {e}")
        # Fallback to direct text if LLM fails
        if tier == "exact" or tier == "related":
            # Just output the top result answer directly as a crude fallback
            top_answer = contexts[0]['content'] if contexts else ""
            return f"นี่คือคำตอบที่พบบนระบบค่ะ:\n\n{top_answer}", tier
        return fallback_message, "none"
