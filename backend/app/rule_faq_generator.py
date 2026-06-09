import re
from typing import List, Dict

THAI_MEANS = "หมายถึง"
THAI_IS = "คือ"
THAI_HAS_COMPONENTS = "มีองค์ประกอบ"
THAI_CONSISTS_OF = "ประกอบด้วย"
THAI_MAIN = "หลัก"
THAI_BASIC = "พื้นฐาน"
THAI_AS_FOLLOWS = "ดังนี้"
THAI_INCLUDE = "ได้แก่"
THAI_SPLIT = "แบ่ง"
THAI_OUT = "ออก"
THAI_AS = "เป็น"
THAI_HAS = "มี"
THAI_TYPE = "ประเภท"
THAI_KIND = "แบบ"
THAI_GROUP = "กลุ่ม"
THAI_DO_DUTY = "ทำหน้าที่"
THAI_HAS_DUTY = "มีหน้าที่"
THAI_CASE = "ในกรณีที่"
THAI_IF = "หาก"
THAI_WHEN = "เมื่อ"
THAI_MUST = "ต้อง"
THAI_SHOULD = "ควร"
THAI_MAY = "อาจ"
THAI_WHAT = "อะไร"
THAI_WHAT_SOME = "อะไรบ้าง"
THAI_HOW_MANY_TYPES = "แบ่งออกเป็นกี่ประเภท"
THAI_HOW_TO_DO = "ต้องดำเนินการอย่างไร"
THAI_IMPORTANT_LIST_Q = "รายการสำคัญที่กล่าวถึงมีอะไรบ้าง"
THAI_CONDITION_Q = "เงื่อนไขหรือกรณีที่กล่าวถึงคืออะไร"

def normalize_text(text: str) -> str:
    if not isinstance(text, str): return ""
    text = text.replace("\u200b", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()

def clean_faq_text(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"<page_number>\d+</page_number>", " ", text)
    text = re.sub(r"^[\-\u2013]?\d+[\-\u2013]?\s*", "", text)
    return re.sub(r"\s+", " ", text).strip(" -\u2013|:")

def strip_list_marker(text: str) -> str:
    text = clean_faq_text(text)
    return re.sub(r"^[\-\u2013\u2022*\d\.\(\)\s]+", "", text).strip()

def extract_generated_question_topic(question: str) -> str:
    question = clean_faq_text(question)
    suffixes = [
        f" {THAI_MEANS}{THAI_WHAT}",
        f" {THAI_HAS_COMPONENTS}{THAI_WHAT_SOME}",
        f" {THAI_DO_DUTY}{THAI_WHAT}",
        f" {THAI_HOW_MANY_TYPES}",
    ]
    for suffix in suffixes:
        if question.endswith(suffix):
            return clean_faq_text(question[:-len(suffix)])
    return question

def looks_like_fragment_generated_question(question: str) -> bool:
    question = clean_faq_text(question)
    topic = extract_generated_question_topic(question)
    if len(topic) < 4: return True
    bad_topic_terms = ["วันที่เผยแพร่", "ผู้อ่าน", "หมวดหมู่", "GROWTH", "ELDC", "DPS", "research and consulting"]
    if any(term.lower() in topic.lower() for term in bad_topic_terms): return True
    if re.search(r"[A-Za-z]{3,}\s+[A-Za-z]{3,}\s+[A-Za-z]{3,}", topic): return True
    if re.search(r"^[\u0e30\u0e32\u0e33\u0e34-\u0e3a\u0e47-\u0e4e]", topic): return True
    fragment_prefixes = ("กแล้ว", "วล", "มือชื่อ", "กงาน", "รือ", "ษฎีกา", "ก์", "ป ", "อก", "ง ", "รรม")
    if topic.startswith(fragment_prefixes): return True
    clean_starts = ("ETDA", "Digital", "e-", "ระบบ", "บริการ", "การ", "ธุรกรรม", "เอกสาร", "ใบ", "ผู้", "หน่วยงาน", "แพลตฟอร์ม", "ลายมือ", "คำนิยาม", "คำ", "ข้อ", "มาตรา", "เว็บ", "สัญญา", "เงื่อนไข", "ใบรับรอง", "สิ่งพิมพ์", "หน้าที่")
    return len(topic) > 70 and not topic.startswith(clean_starts)

def get_rule_topic_candidate(prefix: str, max_len: int = 70) -> str:
    prefix = clean_faq_text(prefix)
    for sep in ["|", " - ", " – ", ":", ";", "?", "!", "\n"]:
        if sep in prefix:
            prefix = prefix.split(sep)[-1]
    prefix = strip_list_marker(re.sub(r"^[\-\u2013\u2022\d\.\(\)\s]+", "", prefix).strip())
    bad_inside_terms = ["โดย", "มาตรา", "แบ่ง", "ได้แก่", "ส่วนที่", "กล่าว", "ภายใน", "วันที่เผยแพร่", "ผู้อ่าน", "หมวดหมู่"]
    if any(term in prefix for term in bad_inside_terms): return ""
    if re.search(r"[0-9\u0e50-\u0e59]{4}", prefix): return ""
    if looks_like_fragment_generated_question(f"{prefix} {THAI_MEANS}{THAI_WHAT}"): return ""
    if len(prefix) < 4 or len(prefix) > max_len: return ""
    return prefix

def split_sentences_thai(text: str) -> list[str]:
    text = clean_faq_text(text)
    parts = re.split(r"(?<=[.!?])\s+|(?=\(\d+\))|(?=\d+\.\s)|(?=[\-\u2013\u2022]\s)|" + rf"(?=\s(?:{THAI_MUST}|{THAI_SHOULD}|{THAI_MAY})\s)", text)
    return [clean_faq_text(p) for p in parts if len(clean_faq_text(p)) > 20]

def build_faq(question: str, answer: str, faq_type: str, filename: str) -> dict:
    return {
        "category": f"Rule: {faq_type}",
        "question": clean_faq_text(question),
        "answer": clean_faq_text(answer),
        "filename": filename,
        "source_type": "Rule-based"
    }

def generate_definition_questions(sentence: str, filename: str) -> list[dict]:
    qas = []
    sentence = clean_faq_text(sentence)
    for marker in [THAI_MEANS, THAI_IS]:
        pattern = rf"(.+?)\s*{marker}\s*(.{{10,500}})"
        for m in re.finditer(pattern, sentence):
            term = get_rule_topic_candidate(m.group(1), max_len=70)
            definition = clean_faq_text(m.group(2))
            if term and len(definition) >= 10:
                qas.append(build_faq(f"{term} {THAI_MEANS}{THAI_WHAT}", definition, "Definition", filename))
    return qas

def generate_component_questions(sentence: str, filename: str) -> list[dict]:
    qas = []
    patterns = [
        rf"(.+?)\s*{THAI_HAS_COMPONENTS}(?:{THAI_MAIN}|{THAI_BASIC})?(?:.*?)(?:{THAI_AS_FOLLOWS}|{THAI_INCLUDE})\s*(.{{10,700}})",
        rf"(.+?)\s*{THAI_CONSISTS_OF}\s*(.{{10,700}})",
    ]
    for pattern in patterns:
        m = re.search(pattern, sentence)
        if m:
            topic = get_rule_topic_candidate(m.group(1), max_len=80)
            answer = clean_faq_text(m.group(2))
            if topic and len(answer) >= 10:
                qas.append(build_faq(f"{topic} {THAI_HAS_COMPONENTS}{THAI_WHAT_SOME}", answer, "Components", filename))
    return qas

def generate_type_questions(sentence: str, filename: str) -> list[dict]:
    qas = []
    patterns = [
        rf"(.+?)\s*{THAI_SPLIT}(?:{THAI_OUT})?{THAI_AS}\s*(\d+)\s*(?:{THAI_TYPE}|{THAI_KIND}|{THAI_GROUP})\s*(?:{THAI_INCLUDE}|{THAI_IS})?\s*(.{{10,700}})",
        rf"(.+?)\s*{THAI_HAS}\s*(\d+)\s*(?:{THAI_TYPE}|{THAI_KIND}|{THAI_GROUP})\s*(?:{THAI_INCLUDE}|{THAI_IS})?\s*(.{{10,700}})",
    ]
    for pattern in patterns:
        m = re.search(pattern, sentence)
        if m:
            topic = get_rule_topic_candidate(m.group(1), max_len=80)
            number = clean_faq_text(m.group(2))
            items = clean_faq_text(m.group(3))
            if topic and len(items) >= 10:
                qas.append(build_faq(f"{topic} {THAI_HOW_MANY_TYPES}", f"{number} {THAI_TYPE} {THAI_INCLUDE} {items}", "Types", filename))
    return qas

def generate_function_questions(sentence: str, filename: str) -> list[dict]:
    qas = []
    patterns = [
        rf"(.+?)\s*{THAI_DO_DUTY}\s*(.{{10,500}})",
        rf"(.+?)\s*{THAI_HAS_DUTY}\s*(.{{10,500}})",
    ]
    for pattern in patterns:
        m = re.search(pattern, sentence)
        if m:
            topic = get_rule_topic_candidate(m.group(1), max_len=80)
            function = clean_faq_text(m.group(2))
            if topic and len(function) >= 10:
                qas.append(build_faq(f"{topic} {THAI_DO_DUTY}{THAI_WHAT}", function, "Function", filename))
    return qas

def generate_condition_questions(sentence: str, filename: str) -> list[dict]:
    qas = []
    patterns = [
        rf"(?:{THAI_CASE}|{THAI_IF}|{THAI_WHEN})\s*(.{{8,220}}?)(?:\s+({THAI_MUST}|{THAI_SHOULD}|{THAI_MAY})\s+)(.{{10,500}})",
        rf"((?:{THAI_CASE}|{THAI_IF}|{THAI_WHEN}).{{20,500}})",
    ]
    for pattern in patterns:
        m = re.search(pattern, sentence)
        if not m:
            continue
        if len(m.groups()) == 3 and m.group(2):
            condition = clean_faq_text(m.group(1))
            modal = clean_faq_text(m.group(2))
            action = clean_faq_text(m.group(3))
            if len(condition) >= 8 and len(action) >= 10:
                qas.append(build_faq(f"{THAI_IF}{condition} {THAI_HOW_TO_DO}", f"{modal}{action}", "Condition", filename))
        else:
            condition_text = clean_faq_text(m.group(1))
            if 30 <= len(condition_text) <= 500:
                qas.append(build_faq(THAI_CONDITION_Q, condition_text, "Condition", filename))
    return qas

def generate_list_questions(chunk_text: str, filename: str) -> list[dict]:
    items = re.findall(r"\(\d+\)\s*([^()]{20,350})", chunk_text)
    clean_items = [clean_faq_text(x) for x in items]
    clean_items = [x for x in clean_items if 20 <= len(x) <= 350]
    if 2 <= len(clean_items) <= 12:
        return [build_faq(THAI_IMPORTANT_LIST_Q, " | ".join(clean_items), "Numbered List", filename)]
    return []

def extract_faqs_rules(text: str, filename: str) -> List[Dict[str, str]]:
    generated = []
    for sent in split_sentences_thai(text):
        generated.extend(generate_definition_questions(sent, filename))
        generated.extend(generate_component_questions(sent, filename))
        generated.extend(generate_type_questions(sent, filename))
        generated.extend(generate_function_questions(sent, filename))
        generated.extend(generate_condition_questions(sent, filename))
    generated.extend(generate_list_questions(text, filename))
    
    # Filter out empty or broken ones
    valid = []
    for q in generated:
        if len(q['question']) > 5 and len(q['answer']) > 5:
            valid.append(q)
            
    return valid
