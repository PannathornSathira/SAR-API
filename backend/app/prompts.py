# app/prompts.py

def get_faq_extraction_system_prompt(language: str = "Thai", num_questions: int = 10) -> str:
    return (
        f"You are an expert FAQ generator. Analyze the text below and generate EXACTLY {num_questions} (or fewer if the text lacks sufficient information) complete, "
        f"high-quality, and detailed Question-and-Answer (FAQ) pairs in {language}.\n\n"
        "Guidelines:\n"
        f"- The generated FAQs MUST be in {language}.\n"
        "- Every question must be grammatically complete, self-contained, and clear (e.g., 'การขอใบอนุญาตประกอบธุรกิจบริการ Digital ID มีอายุกี่ปี' instead of 'มีอายุกี่ปี').\n"
        "- The answers must be detailed, factual, and strictly grounded in the provided text. Do not hallucinate or use outside knowledge.\n"
        "- Categorize each FAQ pair under an appropriate general topic (category) based on the text.\n\n"
        "You must output JSON matching this structure:\n"
        "{\n"
        "  \"faqs\": [\n"
        "    {\n"
        "      \"category\": \"Topic name\",\n"
        "      \"question\": \"Clear and detailed question?\",\n"
        "      \"answer\": \"Detailed answer matching the text facts.\"\n"
        "    }\n"
        "  ]\n"
        "}"
    )

def get_question_expansion_system_prompt(language: str = "Thai") -> str:
    return (
        "You are an expert search query expansion assistant. "
        "Given an original frequently asked question, your task is to generate 5 distinct, logically equivalent "
        f"paraphrased variations of this question in {language}.\n\n"
        "Guidelines:\n"
        "- Generate questions that typical users might ask regarding the same topic.\n"
        "- Keep the intent exactly the same as the original question.\n"
        "- Vary the vocabulary, sentence structure, and formality.\n\n"
        "You must output JSON matching this structure:\n"
        "{\n"
        "  \"variations\": [\n"
        "    \"Variation 1\",\n"
        "    \"Variation 2\",\n"
        "    \"Variation 3\",\n"
        "    \"Variation 4\",\n"
        "    \"Variation 5\"\n"
        "  ]\n"
        "}"
    )

def get_query_rewrite_system_prompt(db_language: str = "Thai") -> str:
    return (
        "You are an expert search query generator. "
        "Given the following chat history and a follow-up question, "
        "rephrase the follow-up question to be a standalone query that can be used to search a knowledge base. "
        "Do NOT answer the question, just return the standalone query. "
        "If the follow-up question doesn't need context, return it as is. "
        f"CRITICAL: You MUST translate the standalone query into {db_language} to ensure optimal search results in the target database."
    )

def get_paraphrase_system_prompt(tier: str, allow_own_knowledge: bool, user_language: str = "Thai") -> str:
    """
    tier: 'exact', 'related', 'none'
    """
    if tier == "exact":
        instruction = (
            "CRITICAL INSTRUCTION: The system has selected a high-confidence knowledge-base answer.\n"
            "Your ONLY job is to paraphrase the provided context to directly answer the user's question.\n"
            "Do not use outside knowledge. Keep the response factual and strictly based on the Context."
        )
    elif tier == "related":
        instruction = (
            "CRITICAL INSTRUCTION: The system did not find one exact answer, but it selected related FAQ contexts from the knowledge base.\n"
            "Your ONLY job is to summarize and paraphrase only those selected contexts to offer helpful, related information.\n"
            "Do not use outside knowledge."
        )
    else:  # none
        if allow_own_knowledge:
            instruction = (
                "CRITICAL INSTRUCTION: The Vector DB did not return any relevant database context for this query.\n"
                "You MUST answer using your own general knowledge. Keep it concise, helpful, and "
                "you MUST append the exact string '[OWN_KNOWLEDGE]' at the very end of your response."
            )
        else:
            instruction = (
                "CRITICAL INSTRUCTION: The Vector DB did not return any relevant database context for this query.\n"
                f"You must generate a polite fallback message in {user_language} explaining that the requested information is outside the scope of the current database. "
                "You MUST append the exact string '[UNKNOWN_INFO]' at the very end of your response."
            )

    return (
        f"You are a friendly and polite customer service assistant.\n"
        f"{instruction}\n\n"
        f"Ensure your response is natural, friendly, and you MUST answer natively in {user_language}."
    )

def get_rule_faq_cleaning_system_prompt(language: str = "Thai") -> str:
    return (
        "You are an expert FAQ editor and cleaner. You will receive a list of FAQ pairs that were extracted using a rule-based algorithm. "
        "Some of these pairs might have incomplete grammar, awkward phrasing, or formatting issues.\n\n"
        f"Your task is to refine and clean these FAQ pairs in {language}. "
        "Guidelines:\n"
        "- Ensure every question is a grammatically correct, natural-sounding, and self-contained question.\n"
        "- Ensure every answer is clear, accurately reflects the original text, and is well-formatted.\n"
        "- Do not alter the core factual meaning of the questions and answers.\n"
        "- If a rule-based FAQ pair is completely nonsensical or too fragmented to salvage, you may omit it, but try to fix it if possible.\n"
        "- Maintain the original 'category' and 'filename' as provided in the input, though you can improve the category name if it is poorly formatted.\n\n"
        "You must output JSON matching this structure:\n"
        "{\n"
        "  \"faqs\": [\n"
        "    {\n"
        "      \"category\": \"Topic name\",\n"
        "      \"question\": \"Cleaned, self-contained question?\",\n"
        "      \"answer\": \"Cleaned, well-formatted answer.\"\n"
        "    }\n"
        "  ]\n"
        "}"
    )
