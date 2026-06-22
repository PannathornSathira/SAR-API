import langdetect
from langdetect.lang_detect_exception import LangDetectException
from app.vector_store import client

# ISO 639-1 to standard name mapping (for common languages to help LLM)
LANGUAGE_MAP = {
    "th": "Thai",
    "en": "English",
    "zh-cn": "Chinese",
    "zh-tw": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German"
}

_db_language_cache = {}

def detect_language(text: str) -> str:
    """Detects the language of the provided text and returns its full name or ISO code."""
    if not text or not text.strip():
        return "Unknown"
    
    try:
        lang_code = langdetect.detect(text)
        detected = LANGUAGE_MAP.get(lang_code, lang_code)
        # Log a snippet of the text to give context
        snippet = text[:50].replace('\n', ' ') + ('...' if len(text) > 50 else '')
        print(f"[Language Detect] Detected '{detected}' from text: '{snippet}'")
        return detected
    except LangDetectException:
        print(f"[Language Detect] Failed to detect language, falling back to Unknown.")
        return "Unknown"

def get_db_language(collection_name: str) -> str:
    """Samples a document from the Qdrant collection to detect its primary language."""
    if collection_name in _db_language_cache:
        print(f"[Language Detect] Using cached DB language for collection '{collection_name}': {_db_language_cache[collection_name]}")
        return _db_language_cache[collection_name]
        
    try:
        records, _ = client.scroll(
            collection_name=collection_name,
            limit=1,
            with_payload=True
        )
        if records:
            content = records[0].payload.get("page_content", "")
            lang = detect_language(content)
            _db_language_cache[collection_name] = lang
            print(f"[Language Detect] First time sampling DB language for collection '{collection_name}': {lang}")
            return lang
    except Exception as e:
        print(f"[Language Detect] Error detecting DB language for {collection_name}: {e}")
        
    # Default to Thai if we can't detect or collection is empty
    print(f"[Language Detect] Collection '{collection_name}' empty or error occurred. Defaulting DB language to Thai.")
    return "Thai"
