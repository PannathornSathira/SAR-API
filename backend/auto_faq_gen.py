"""
Automate new FAQ generation from an old FAQ file and a source document.

Examples:
    python automate_faq_generation.py --old-faq "EDTA  FAQ.xlsx" --source "Source/report.pdf"
    python automate_faq_generation.py --input-dir Source --output-dir Output
    python automate_faq_generation.py "EDTA  FAQ.xlsx" "faq_search_results_cleaned.csv"
"""

from __future__ import annotations

import argparse
import csv as csv_module
import html
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm

try:
    from pythainlp.tokenize import word_tokenize
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: pythainlp. Install dependencies with:\n"
        "python -m pip install pymupdf pythainlp rank-bm25 pandas scikit-learn openpyxl tqdm"
    ) from exc


FAQ_EXTENSIONS = {".csv", ".xlsx", ".xls"}
SOURCE_EXTENSIONS = {".pdf", ".json", ".csv", ".docx", ".doc"}


def normalize_text(text: str) -> str:
    if pd.isna(text):
        return ""
    text = str(text)
    text = text.replace("\u200b", "")
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def thai_tokenize(text: str) -> list[str]:
    text = normalize_text(text)
    return [t.strip() for t in word_tokenize(text, engine="newmm") if t.strip()]


def extract_pdf_pages(pdf_path: Path) -> list[dict]:
    try:
        import fitz
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: pymupdf. Install dependencies with:\n"
            "python -m pip install pymupdf pythainlp rank-bm25 pandas scikit-learn openpyxl tqdm"
        ) from exc

    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = normalize_text(page.get_text("text"))
        if text:
            pages.append({"page": i + 1, "source_label": pdf_path.name, "source_url": "", "text": text})
    doc.close()
    return pages


def extract_docx_text(docx_path: Path) -> str:
    """Extract text from a .docx file without requiring python-docx."""
    text_parts = []
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    with zipfile.ZipFile(docx_path) as docx_zip:
        xml_names = [
            "word/document.xml",
            "word/footnotes.xml",
            "word/endnotes.xml",
        ]
        for xml_name in xml_names:
            if xml_name not in docx_zip.namelist():
                continue
            root = ET.fromstring(docx_zip.read(xml_name))
            for paragraph in root.findall(".//w:p", namespace):
                paragraph_parts = []
                for node in paragraph.iter():
                    tag = node.tag.rsplit("}", 1)[-1]
                    if tag == "t" and node.text:
                        paragraph_parts.append(node.text)
                    elif tag == "tab":
                        paragraph_parts.append("\t")
                    elif tag in {"br", "cr"}:
                        paragraph_parts.append("\n")
                paragraph_text = normalize_text("".join(paragraph_parts))
                if paragraph_text:
                    text_parts.append(paragraph_text)

    return normalize_text("\n".join(text_parts))


def extract_doc_text_with_converter(doc_path: Path) -> str:
    """Extract legacy .doc text with common command-line converters when present."""
    converters = [
        ("antiword", [str(doc_path)]),
        ("catdoc", [str(doc_path)]),
    ]
    for command, args in converters:
        executable = shutil.which(command)
        if not executable:
            continue
        result = subprocess.run(
            [executable, *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0 and result.stdout:
            for encoding in ["utf-8", "cp874", "tis-620", "latin1"]:
                try:
                    text = result.stdout.decode(encoding)
                    return normalize_text(text)
                except UnicodeDecodeError:
                    continue
            return normalize_text(result.stdout.decode("utf-8", errors="ignore"))
    return ""


def extract_doc_text_with_word(doc_path: Path) -> str:
    """Extract legacy .doc text through Microsoft Word COM automation on Windows."""
    if os.name != "nt":
        return ""
    try:
        import win32com.client
    except ImportError:
        return ""

    word = None
    document = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        document = word.Documents.Open(str(doc_path.resolve()), ReadOnly=True)
        return normalize_text(document.Content.Text)
    except Exception:
        return ""
    finally:
        if document is not None:
            document.Close(False)
        if word is not None:
            word.Quit()


def extract_word_document(source_path: Path) -> list[dict]:
    ext = source_path.suffix.lower()
    if ext == ".docx":
        text = extract_docx_text(source_path)
    elif ext == ".doc":
        text = extract_doc_text_with_converter(source_path) or extract_doc_text_with_word(source_path)
        if not text:
            raise RuntimeError(
                "Could not extract text from legacy .doc file. Install antiword/catdoc, "
                "run on Windows with Microsoft Word available, or convert the file to .docx."
            )
    else:
        raise ValueError(f"Unsupported Word file type: {ext}")

    text = normalize_text(text)
    if not text:
        return []
    return [{"page": 1, "source_label": source_path.name, "source_url": "", "text": text}]


def repair_mojibake(text: str) -> str:
    if not isinstance(text, str):
        return ""
    suspicious = ("à", "â", "Ã", "ï»¿")
    if not any(mark in text for mark in suspicious):
        return text
    try:
        return text.encode("cp1252", errors="strict").decode("utf-8", errors="strict")
    except Exception:
        return text


def clean_json_content(text: str) -> str:
    text = repair_mojibake(text)
    text = html.unescape(text)
    text = re.sub(r"<\s*(br|p|div|li|tr|table|/table|/tr)\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<\s*/?t[dh][^>]*>", " | ", text, flags=re.I)
    text = re.sub(r"<\s*page_number[^>]*>(.*?)<\s*/\s*page_number\s*>", r" page \1 ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[*_`#]+", " ", text)
    return normalize_text(text)


def first_existing_column(df: pd.DataFrame, candidates: list[str]):
    normalized_columns = {str(col).strip().lower(): col for col in df.columns}
    for candidate in candidates:
        column = normalized_columns.get(candidate.lower())
        if column is not None:
            return column
    return None


def value_from_row(row: pd.Series, column) -> str:
    if column is None:
        return ""
    value = row.get(column, "")
    if pd.isna(value):
        return ""
    return str(value).strip()


def read_csv_flexible(csv_path: Path, sniff_separator: bool = True) -> pd.DataFrame:
    field_size_limit = sys.maxsize
    while True:
        try:
            csv_module.field_size_limit(field_size_limit)
            break
        except OverflowError:
            field_size_limit //= 10

    encodings = ["utf-8-sig", "utf-8", "cp874", "tis-620", "latin1"]
    last_error = None
    for enc in encodings:
        try:
            kwargs = {"encoding": enc}
            if sniff_separator:
                kwargs.update({"sep": None, "engine": "python"})
            df = pd.read_csv(csv_path, **kwargs)
            df.columns = [str(col).replace("\ufeff", "").strip().strip('"') for col in df.columns]
            return df
        except UnicodeDecodeError as exc:
            last_error = exc
    raise RuntimeError(f"Could not read CSV file: {csv_path}. Last error: {last_error}")


def load_csv_documents(csv_path: Path) -> list[dict]:
    df = read_csv_flexible(csv_path, sniff_separator=True)
    text_candidates = [
        "content", "text", "body", "html", "document", "doc", "source_text",
        "chunk_text", "source_chunk_text", "retrieved_doc_1", "retrieved_doc",
        "answer", "question_expand", "question",
    ]
    url_candidates = ["source_url", "url", "page_url", "retrieved_url_1", "link", "href"]
    label_candidates = ["source_label", "title", "page_title", "name", "file", "filename"]
    page_candidates = ["page", "page_number", "source_page"]

    normalized_columns = {str(col).strip().lower(): col for col in df.columns}
    text_columns = [normalized_columns[c.lower()] for c in text_candidates if c.lower() in normalized_columns]
    url_column = first_existing_column(df, url_candidates)
    label_column = first_existing_column(df, label_candidates)
    page_column = first_existing_column(df, page_candidates)

    if not text_columns:
        excluded_columns = {col for col in [url_column, label_column, page_column] if col is not None}
        excluded_columns.update(
            col for col in df.columns
            if any(token in str(col).lower() for token in ["url", "link", "href"])
        )
        text_columns = [col for col in df.columns if col not in excluded_columns]

    documents = []
    for i, row in df.iterrows():
        raw_text = "\n".join(value_from_row(row, col) for col in text_columns if value_from_row(row, col))
        text = clean_json_content(raw_text)
        if not text:
            continue
        source_url = value_from_row(row, url_column)
        source_label = value_from_row(row, label_column) or source_url or f"csv_record_{i + 1}"
        documents.append({
            "page": value_from_row(row, page_column) or i + 1,
            "source_label": source_label,
            "source_url": source_url,
            "text": text,
        })
    return documents


def load_json_documents(json_path: Path) -> list[dict]:
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    records = data.get("documents") or data.get("items") or data.get("data") or [data] if isinstance(data, dict) else data

    documents = []
    for i, item in enumerate(records):
        if not isinstance(item, dict):
            continue
        raw_text = item.get("content") or item.get("text") or item.get("body") or item.get("html") or ""
        text = clean_json_content(raw_text)
        if text:
            source_url = item.get("url", "")
            documents.append({
                "page": i + 1,
                "source_label": source_url or f"json_record_{i + 1}",
                "source_url": source_url,
                "text": text,
            })
    return documents


def load_source_documents(source_path: Path) -> list[dict]:
    ext = source_path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf_pages(source_path)
    if ext in {".docx", ".doc"}:
        return extract_word_document(source_path)
    if ext == ".json":
        return load_json_documents(source_path)
    if ext == ".csv":
        return load_csv_documents(source_path)
    raise ValueError(f"Unsupported source file type: {ext}. Use .pdf, .docx, .doc, .json, or .csv.")


def clean_chunk_overlap(text: str, overlap_chars: int) -> str:
    text = normalize_text(text)
    if overlap_chars <= 0 or len(text) <= overlap_chars:
        return ""

    tail = text[-overlap_chars:]
    boundary_patterns = [
        r"(?<=[.!?])\s+",
        r"\s+(?=\(?\d+[\).]\s*)",
        r"\s+(?=[\-\u2013\u2022]\s*)",
        r"\s+(?=(?:ETDA|Digital|e-|\u0e04\u0e33\u0e16\u0e32\u0e21|\u0e27\u0e31\u0e19\u0e17\u0e35\u0e48|\u0e2b\u0e21\u0e27\u0e14|\u0e23\u0e30\u0e1a\u0e1a|\u0e1a\u0e23\u0e34\u0e01\u0e32\u0e23|\u0e01\u0e32\u0e23|\u0e1c\u0e39\u0e49|\u0e43\u0e1a|\u0e40\u0e2d\u0e01\u0e2a\u0e32\u0e23))",
    ]
    for pattern in boundary_patterns:
        for match in re.finditer(pattern, tail):
            candidate = tail[match.end():].strip()
            if 40 <= len(candidate) <= overlap_chars:
                return candidate
    return ""


def split_text_into_chunks(pages: list[dict], max_chars: int = 1200, overlap_chars: int = 200) -> list[dict]:
    chunks = []
    for page_obj in pages:
        page_num = page_obj["page"]
        source_label = page_obj.get("source_label", page_num)
        source_url = page_obj.get("source_url", "")
        paragraphs = re.split(r"(?<=[.!?])\s+|\n+", page_obj["text"])
        paragraphs = [normalize_text(p) for p in paragraphs if normalize_text(p)]
        current = ""

        for para in paragraphs:
            if len(current) + len(para) <= max_chars:
                current += " " + para
            else:
                if current.strip():
                    chunks.append({
                        "chunk_id": len(chunks),
                        "page": page_num,
                        "source_label": source_label,
                        "source_url": source_url,
                        "text": current.strip(),
                    })
                overlap = clean_chunk_overlap(current, overlap_chars)
                current = f"{overlap} {para}" if overlap else para

        if current.strip():
            chunks.append({
                "chunk_id": len(chunks),
                "page": page_num,
                "source_label": source_label,
                "source_url": source_url,
                "text": current.strip(),
            })
    return chunks


def detect_faq_columns(df: pd.DataFrame):
    df = df.dropna(axis=1, how="all")
    lower_cols = {str(c).lower().strip(): c for c in df.columns}
    question_candidates = [
        "original_question", "faq_question", "question", "questions", "q",
        "\u0e04\u0e33\u0e16\u0e32\u0e21", "question_th", "generated_question", "faq",
    ]
    answer_candidates = [
        "answer_content", "faq_answer", "answer", "answers", "a",
        "\u0e04\u0e33\u0e15\u0e2d\u0e1a", "answer_th", "generated_answer", "response",
    ]

    question_col = next((lower_cols[c] for c in question_candidates if c in lower_cols), None)
    answer_col = next((lower_cols[c] for c in answer_candidates if c in lower_cols), None)

    if question_col is None or answer_col is None:
        text_columns = []
        for col in df.columns:
            normalized = df[col].apply(normalize_text)
            non_empty = normalized[normalized != ""]
            avg_len = non_empty.str.len().mean() if len(non_empty) else 0
            if avg_len >= 8:
                text_columns.append(col)
        if question_col is None and text_columns:
            question_col = text_columns[0]
        if answer_col is None:
            answer_choices = [c for c in text_columns if c != question_col]
            if answer_choices:
                answer_col = answer_choices[0]

    if question_col is None or answer_col is None:
        raise ValueError(
            "Could not auto-detect FAQ question/answer columns. Rename columns to "
            "question/answer, faq_question/faq_answer, or original_question/answer_content."
        )
    return question_col, answer_col


def normalize_faq_frame(df: pd.DataFrame, source_sheet: str = "") -> pd.DataFrame:
    df = df.dropna(axis=1, how="all")
    if df.empty or len(df.columns) == 0:
        return pd.DataFrame(columns=["question", "answer", "source_sheet"])

    question_col, answer_col = detect_faq_columns(df)
    optional_columns = [c for c in ["Group", "group", "category", "Category"] if c in df.columns]
    df = df[[question_col, answer_col] + optional_columns].copy()
    df = df.rename(columns={question_col: "question", answer_col: "answer"})
    df["question"] = df["question"].apply(normalize_text)
    df["answer"] = df["answer"].apply(normalize_text)
    df["source_sheet"] = source_sheet
    df = df[(df["question"] != "") | (df["answer"] != "")]
    return df.reset_index(drop=True)


def load_faq_source(source_path: Path) -> pd.DataFrame:
    ext = source_path.suffix.lower()
    if ext in [".xlsx", ".xls"]:
        sheet_map = pd.read_excel(source_path, sheet_name=None)
        frames = [
            normalize_faq_frame(sheet_df, source_sheet=sheet_name)
            for sheet_name, sheet_df in sheet_map.items()
            if not sheet_df.dropna(axis=1, how="all").empty
        ]
        if not frames:
            raise RuntimeError("No usable FAQ sheets found in Excel file.")
        return pd.concat(frames, ignore_index=True)

    if ext == ".csv":
        return normalize_faq_frame(read_csv_flexible(source_path, sniff_separator=False))

    raise ValueError(f"Unsupported old FAQ file type: {ext}. Use .csv, .xlsx, or .xls.")


class Retriever:
    def __init__(self, chunks_df: pd.DataFrame):
        self.chunks_df = chunks_df
        self.chunk_texts = chunks_df["text"].tolist()
        self.tokenized_chunks = [thai_tokenize(text) for text in self.chunk_texts]
        self.bm25 = BM25Okapi(self.tokenized_chunks)
        self.tfidf_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1)
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(self.chunk_texts)

    @staticmethod
    def minmax_scale(scores):
        scores = np.array(scores, dtype=float)
        if scores.max() == scores.min():
            return np.zeros_like(scores)
        return (scores - scores.min()) / (scores.max() - scores.min())

    def retrieve(self, question: str, answer: str, top_k: int = 3, bm25_weight: float = 0.55, tfidf_weight: float = 0.45):
        query = normalize_text(f"{question} {answer}")
        bm25_scores = self.bm25.get_scores(thai_tokenize(query))
        bm25_scores_scaled = self.minmax_scale(bm25_scores)
        query_vec = self.tfidf_vectorizer.transform([query])
        tfidf_scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        tfidf_scores_scaled = self.minmax_scale(tfidf_scores)
        final_scores = bm25_weight * bm25_scores_scaled + tfidf_weight * tfidf_scores_scaled

        results = []
        for idx in np.argsort(final_scores)[::-1][:top_k]:
            row = self.chunks_df.iloc[idx]
            results.append({
                "chunk_id": int(row["chunk_id"]),
                "page": row["page"],
                "source_label": row.get("source_label", row["page"]),
                "source_url": row.get("source_url", ""),
                "score": float(final_scores[idx]),
                "bm25_score": float(bm25_scores_scaled[idx]),
                "tfidf_score": float(tfidf_scores_scaled[idx]),
                "chunk_text": row["text"],
            })
        return results


THAI_MEANS = "\u0e2b\u0e21\u0e32\u0e22\u0e16\u0e36\u0e07"
THAI_IS = "\u0e04\u0e37\u0e2d"
THAI_HAS_COMPONENTS = "\u0e21\u0e35\u0e2d\u0e07\u0e04\u0e4c\u0e1b\u0e23\u0e30\u0e01\u0e2d\u0e1a"
THAI_CONSISTS_OF = "\u0e1b\u0e23\u0e30\u0e01\u0e2d\u0e1a\u0e14\u0e49\u0e27\u0e22"
THAI_MAIN = "\u0e2b\u0e25\u0e31\u0e01"
THAI_BASIC = "\u0e1e\u0e37\u0e49\u0e19\u0e10\u0e32\u0e19"
THAI_AS_FOLLOWS = "\u0e14\u0e31\u0e07\u0e19\u0e35\u0e49"
THAI_INCLUDE = "\u0e44\u0e14\u0e49\u0e41\u0e01\u0e48"
THAI_SPLIT = "\u0e41\u0e1a\u0e48\u0e07"
THAI_OUT = "\u0e2d\u0e2d\u0e01"
THAI_AS = "\u0e40\u0e1b\u0e47\u0e19"
THAI_HAS = "\u0e21\u0e35"
THAI_TYPE = "\u0e1b\u0e23\u0e30\u0e40\u0e20\u0e17"
THAI_KIND = "\u0e41\u0e1a\u0e1a"
THAI_GROUP = "\u0e01\u0e25\u0e38\u0e48\u0e21"
THAI_DO_DUTY = "\u0e17\u0e33\u0e2b\u0e19\u0e49\u0e32\u0e17\u0e35\u0e48"
THAI_HAS_DUTY = "\u0e21\u0e35\u0e2b\u0e19\u0e49\u0e32\u0e17\u0e35\u0e48"
THAI_CASE = "\u0e43\u0e19\u0e01\u0e23\u0e13\u0e35\u0e17\u0e35\u0e48"
THAI_IF = "\u0e2b\u0e32\u0e01"
THAI_WHEN = "\u0e40\u0e21\u0e37\u0e48\u0e2d"
THAI_MUST = "\u0e15\u0e49\u0e2d\u0e07"
THAI_SHOULD = "\u0e04\u0e27\u0e23"
THAI_MAY = "\u0e2d\u0e32\u0e08"
THAI_WHAT = "\u0e2d\u0e30\u0e44\u0e23"
THAI_WHAT_SOME = "\u0e2d\u0e30\u0e44\u0e23\u0e1a\u0e49\u0e32\u0e07"
THAI_HOW_MANY_TYPES = "\u0e41\u0e1a\u0e48\u0e07\u0e2d\u0e2d\u0e01\u0e40\u0e1b\u0e47\u0e19\u0e01\u0e35\u0e48\u0e1b\u0e23\u0e30\u0e40\u0e20\u0e17"
THAI_HOW_TO_DO = "\u0e15\u0e49\u0e2d\u0e07\u0e14\u0e33\u0e40\u0e19\u0e34\u0e19\u0e01\u0e32\u0e23\u0e2d\u0e22\u0e48\u0e32\u0e07\u0e44\u0e23"
THAI_IMPORTANT_LIST_Q = "\u0e23\u0e32\u0e22\u0e01\u0e32\u0e23\u0e2a\u0e33\u0e04\u0e31\u0e0d\u0e17\u0e35\u0e48\u0e01\u0e25\u0e48\u0e32\u0e27\u0e16\u0e36\u0e07\u0e21\u0e35\u0e2d\u0e30\u0e44\u0e23\u0e1a\u0e49\u0e32\u0e07"
THAI_CONDITION_Q = "\u0e40\u0e07\u0e37\u0e48\u0e2d\u0e19\u0e44\u0e02\u0e2b\u0e23\u0e37\u0e2d\u0e01\u0e23\u0e13\u0e35\u0e17\u0e35\u0e48\u0e01\u0e25\u0e48\u0e32\u0e27\u0e16\u0e36\u0e07\u0e04\u0e37\u0e2d\u0e2d\u0e30\u0e44\u0e23"


def clean_faq_text(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"<page_number>\d+</page_number>", " ", text)
    text = re.sub(r"^[\-\u2013]?\d+[\-\u2013]?\s*", "", text)
    return re.sub(r"\s+", " ", text).strip(" -\u2013|:")


def normalize_question_key(text: str) -> str:
    text = clean_faq_text(text).lower()
    text = re.sub(r"^[\-\u2013\u2022*\d\.\(\)\s]+", "", text)
    text = re.sub(r"[?？!！.,;:：\"'`“”‘’\[\]{}()<>|/\\\-\u2013\u2014_]+", " ", text)
    return re.sub(r"\s+", "", text)


def strip_list_marker(text: str) -> str:
    text = clean_faq_text(text)
    return re.sub(r"^[\-\u2013\u2022*\d\.\(\)\s]+", "", text).strip()


def looks_like_bad_source_question(text: str) -> bool:
    text = clean_faq_text(text)
    return bool(re.fullmatch(r"G\d+|\d+|[A-Z]{1,4}\d*", text, flags=re.I)) or len(text) < 8


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
    if len(topic) < 4:
        return True

    bad_topic_terms = [
        "\u0e27\u0e31\u0e19\u0e17\u0e35\u0e48\u0e40\u0e1c\u0e22\u0e41\u0e1e\u0e23\u0e48",
        "\u0e1c\u0e39\u0e49\u0e2d\u0e48\u0e32\u0e19",
        "\u0e2b\u0e21\u0e27\u0e14\u0e2b\u0e21\u0e39\u0e48",
        "GROWTH", "ELDC", "DPS", "research and consulting",
    ]
    if any(term.lower() in topic.lower() for term in bad_topic_terms):
        return True
    if re.search(r"[A-Za-z]{3,}\s+[A-Za-z]{3,}\s+[A-Za-z]{3,}", topic):
        return True
    if re.search(r"^[\u0e30\u0e32\u0e33\u0e34-\u0e3a\u0e47-\u0e4e]", topic):
        return True

    fragment_prefixes = (
        "\u0e01\u0e41\u0e25\u0e49\u0e27", "\u0e27\u0e25", "\u0e21\u0e37\u0e2d\u0e0a\u0e37\u0e48\u0e2d",
        "\u0e01\u0e07\u0e32\u0e19", "\u0e23\u0e37\u0e2d", "\u0e29\u0e0e\u0e35\u0e01\u0e32", "\u0e01\u0e4c",
        "\u0e1b ", "\u0e2d\u0e01", "\u0e07 ", "\u0e23\u0e23\u0e21",
    )
    if topic.startswith(fragment_prefixes):
        return True

    clean_starts = (
        "ETDA", "Digital", "e-", "\u0e23\u0e30\u0e1a\u0e1a", "\u0e1a\u0e23\u0e34\u0e01\u0e32\u0e23",
        "\u0e01\u0e32\u0e23", "\u0e18\u0e38\u0e23\u0e01\u0e23\u0e23\u0e21", "\u0e40\u0e2d\u0e01\u0e2a\u0e32\u0e23",
        "\u0e43\u0e1a", "\u0e1c\u0e39\u0e49", "\u0e2b\u0e19\u0e48\u0e27\u0e22\u0e07\u0e32\u0e19",
        "\u0e41\u0e1e\u0e25\u0e15\u0e1f\u0e2d\u0e23\u0e4c\u0e21", "\u0e25\u0e32\u0e22\u0e21\u0e37\u0e2d",
        "\u0e04\u0e33\u0e19\u0e34\u0e22\u0e32\u0e21", "\u0e04\u0e33", "\u0e02\u0e49\u0e2d",
        "\u0e21\u0e32\u0e15\u0e23\u0e32", "\u0e40\u0e27\u0e47\u0e1a", "\u0e2a\u0e31\u0e0d\u0e0d\u0e32",
        "\u0e40\u0e07\u0e37\u0e48\u0e2d\u0e19\u0e44\u0e02", "\u0e43\u0e1a\u0e23\u0e31\u0e1a\u0e23\u0e2d\u0e07",
        "\u0e2a\u0e34\u0e48\u0e07\u0e1e\u0e34\u0e21\u0e1e\u0e4c", "\u0e2b\u0e19\u0e49\u0e32\u0e17\u0e35\u0e48",
    )
    return len(topic) > 70 and not topic.startswith(clean_starts)


def split_sentences_thai(text: str) -> list[str]:
    text = clean_faq_text(text)
    parts = re.split(
        r"(?<=[.!?])\s+|"
        r"(?=\(\d+\))|"
        r"(?=\d+\.\s)|"
        r"(?=[\-\u2013\u2022]\s)|"
        rf"(?=\s(?:{THAI_MUST}|{THAI_SHOULD}|{THAI_MAY})\s)",
        text,
    )
    return [clean_faq_text(p) for p in parts if len(clean_faq_text(p)) > 20]


def build_faq(question: str, answer: str, faq_type: str, confidence: float = 0.7) -> dict:
    question = clean_faq_text(question)
    answer = clean_faq_text(answer)
    return {
        "faq_question": question,
        "faq_answer": answer,
        "faq_type": faq_type,
        "generation_confidence": confidence,
        "generated_question": question,
        "generated_answer": answer,
        "rule_type": faq_type,
    }


def get_rule_topic_candidate(prefix: str, max_len: int = 70) -> str:
    prefix = clean_faq_text(prefix)
    for sep in ["|", " - ", " \u2013 ", ":", ";", "?", "!", "\n"]:
        if sep in prefix:
            prefix = prefix.split(sep)[-1]
    prefix = strip_list_marker(re.sub(r"^[\-\u2013\u2022\d\.\(\)\s]+", "", prefix).strip())

    bad_inside_terms = [
        "\u0e42\u0e14\u0e22", "\u0e21\u0e32\u0e15\u0e23\u0e32", "\u0e41\u0e1a\u0e48\u0e07",
        "\u0e44\u0e14\u0e49\u0e41\u0e01\u0e48", "\u0e2a\u0e48\u0e27\u0e19\u0e17\u0e35\u0e48",
        "\u0e01\u0e25\u0e48\u0e32\u0e27", "\u0e20\u0e32\u0e22\u0e43\u0e19",
        "\u0e27\u0e31\u0e19\u0e17\u0e35\u0e48\u0e40\u0e1c\u0e22\u0e41\u0e1e\u0e23\u0e48",
        "\u0e1c\u0e39\u0e49\u0e2d\u0e48\u0e32\u0e19", "\u0e2b\u0e21\u0e27\u0e14\u0e2b\u0e21\u0e39\u0e48",
    ]
    if any(term in prefix for term in bad_inside_terms):
        return ""
    if re.search(r"[0-9\u0e50-\u0e59]{4}", prefix):
        return ""
    if looks_like_fragment_generated_question(f"{prefix} {THAI_MEANS}{THAI_WHAT}"):
        return ""
    if len(prefix) < 4 or len(prefix) > max_len:
        return ""
    return prefix


def generate_definition_questions(sentence: str) -> list[dict]:
    qas = []
    sentence = clean_faq_text(sentence)
    for marker in [THAI_MEANS, THAI_IS]:
        pattern = rf"(.+?)\s*{marker}\s*(.{{10,500}})"
        for m in re.finditer(pattern, sentence):
            term = get_rule_topic_candidate(m.group(1), max_len=70)
            definition = clean_faq_text(m.group(2))
            if term and len(definition) >= 10:
                qas.append(build_faq(f"{term} {THAI_MEANS}{THAI_WHAT}", definition, "definition", 0.82))
    return qas


def generate_component_questions(sentence: str) -> list[dict]:
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
                qas.append(build_faq(f"{topic} {THAI_HAS_COMPONENTS}{THAI_WHAT_SOME}", answer, "components", 0.78))
    return qas


def generate_type_questions(sentence: str) -> list[dict]:
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
                qas.append(build_faq(f"{topic} {THAI_HOW_MANY_TYPES}", f"{number} {THAI_TYPE} {THAI_INCLUDE} {items}", "types", 0.78))
    return qas


def generate_function_questions(sentence: str) -> list[dict]:
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
                qas.append(build_faq(f"{topic} {THAI_DO_DUTY}{THAI_WHAT}", function, "function", 0.76))
    return qas


def generate_condition_questions(sentence: str) -> list[dict]:
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
                qas.append(build_faq(f"{THAI_IF}{condition} {THAI_HOW_TO_DO}", f"{modal}{action}", "condition", 0.72))
        else:
            condition_text = clean_faq_text(m.group(1))
            if 30 <= len(condition_text) <= 500:
                qas.append(build_faq(THAI_CONDITION_Q, condition_text, "condition", 0.55))
    return qas


def generate_list_questions(chunk_text: str) -> list[dict]:
    items = re.findall(r"\(\d+\)\s*([^()]{20,350})", chunk_text)
    clean_items = [clean_faq_text(x) for x in items]
    clean_items = [x for x in clean_items if 20 <= len(x) <= 350]
    if 2 <= len(clean_items) <= 12:
        return [build_faq(THAI_IMPORTANT_LIST_Q, " | ".join(clean_items), "numbered_list", 0.68)]
    return []


def generate_faqs_from_chunk(chunk_text: str) -> list[dict]:
    generated = []
    for sent in split_sentences_thai(chunk_text):
        generated.extend(generate_definition_questions(sent))
        generated.extend(generate_component_questions(sent))
        generated.extend(generate_type_questions(sent))
        generated.extend(generate_function_questions(sent))
        generated.extend(generate_condition_questions(sent))
    generated.extend(generate_list_questions(chunk_text))
    return generated


def build_retrieval_df(faq_df: pd.DataFrame, retriever: Retriever, top_k: int) -> pd.DataFrame:
    retrieval_rows = []
    for i, row in tqdm(faq_df.iterrows(), total=len(faq_df), desc="Retrieving source chunks"):
        matches = retriever.retrieve(row["question"], row["answer"], top_k=top_k)
        for rank, match in enumerate(matches, start=1):
            retrieval_rows.append({
                "faq_id": i,
                "rank": rank,
                "question": row["question"],
                "answer": row["answer"],
                "source_sheet": row.get("source_sheet", ""),
                "matched_page": match["page"],
                "matched_source_label": match.get("source_label", match["page"]),
                "matched_source_url": match.get("source_url", ""),
                "matched_chunk_id": match["chunk_id"],
                "similarity_score": match["score"],
                "bm25_score": match["bm25_score"],
                "tfidf_score": match["tfidf_score"],
                "matched_chunk_text": match["chunk_text"],
            })
    return pd.DataFrame(retrieval_rows)


def build_generated_faq_df(retrieval_df: pd.DataFrame) -> pd.DataFrame:
    top1_df = retrieval_df[retrieval_df["rank"] == 1].copy()
    generated_rows = []
    for _, row in tqdm(top1_df.iterrows(), total=len(top1_df), desc="Generating FAQ rows"):
        for faq in generate_faqs_from_chunk(row["matched_chunk_text"]):
            generated_rows.append({
                "source_question": row["question"],
                "source_answer": row["answer"],
                "source_sheet": row.get("source_sheet", ""),
                "source_page": row["matched_page"],
                "source_label": row.get("matched_source_label", row["matched_page"]),
                "source_url": row.get("matched_source_url", ""),
                "source_chunk_id": row["matched_chunk_id"],
                "source_similarity_score": row["similarity_score"],
                "faq_question": faq["faq_question"],
                "faq_answer": faq["faq_answer"],
                "faq_type": faq["faq_type"],
                "generation_confidence": faq["generation_confidence"],
                "generated_question": faq["generated_question"],
                "generated_answer": faq["generated_answer"],
                "rule_type": faq["rule_type"],
                "source_chunk_text": row["matched_chunk_text"],
            })
    return pd.DataFrame(generated_rows)


def clean_generated_faq(df: pd.DataFrame, old_faq_df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    df["faq_question"] = df["faq_question"].apply(clean_faq_text)
    df["faq_answer"] = df["faq_answer"].apply(clean_faq_text)
    df["question_key"] = df["faq_question"].apply(normalize_question_key)

    old_faq_question_keys = {
        normalize_question_key(q)
        for q in old_faq_df["question"].dropna().astype(str)
        if normalize_question_key(q)
    }
    old_faq_question_keys.update(
        normalize_question_key(q)
        for q in df.get("source_question", pd.Series(dtype=str)).dropna().astype(str)
        if normalize_question_key(q)
    )

    df = df[df["faq_question"].str.len().between(10, 180)]
    df = df[df["faq_answer"].str.len().between(15, 900)]
    df = df[df["question_key"] != ""]
    df = df[~df["question_key"].isin(old_faq_question_keys)]
    df = df.sort_values(["generation_confidence", "source_similarity_score"], ascending=[False, False])
    df = df.drop_duplicates(subset=["question_key"])
    df = df.drop_duplicates(subset=["faq_question", "faq_answer"])
    df = df[~df["faq_answer"].str.fullmatch(r"[\d\W_]+", na=False)]
    df = df[~df["faq_question"].map(looks_like_bad_source_question).astype(bool)]
    df = df[~df["faq_question"].map(looks_like_fragment_generated_question).astype(bool)]

    derived_ok = (
        df["faq_type"].isin(["definition", "components", "types", "function"])
        & df["faq_question"].str.len().between(10, 100)
        & ~df["faq_question"].str.contains(rf"\d+\.\d+|{THAI_AS_FOLLOWS}|^[\-\u2013]", regex=True, na=False)
        & ~df["faq_answer"].str.contains(r"\d+\.\d+", regex=True, na=False)
        & ~df["faq_question"].str.contains(r"^[\u0e30\u0e32\u0e33\u0e34-\u0e3a\u0e47-\u0e4e]", regex=True, na=False)
        & ~df["faq_question"].str.startswith("\u0e1b\u0e4b\u0e32", na=False)
    )
    df = df[derived_ok]
    df["generated_question"] = df["faq_question"]
    df["generated_answer"] = df["faq_answer"]
    df["rule_type"] = df["faq_type"]

    preferred_columns = [
        "faq_question", "faq_answer", "faq_type", "generation_confidence",
        "source_question", "source_answer", "source_sheet", "source_page", "source_label",
        "source_url", "source_chunk_id", "source_similarity_score", "generated_question",
        "generated_answer", "rule_type", "source_chunk_text",
    ]
    return df[[c for c in preferred_columns if c in df.columns]].reset_index(drop=True)


def safe_output_stem(path: Path) -> str:
    name = path.stem.strip()
    name = re.sub(r'[<>:"/\\|?*]+', "_", name)
    return re.sub(r"\s+", " ", name).strip() or "source"


def detect_files(input_dir: Path) -> tuple[Path, Path]:
    files = [p for p in input_dir.iterdir() if p.is_file()]
    faq_candidates = [p for p in files if p.suffix.lower() in FAQ_EXTENSIONS and "generated" not in p.name.lower()]
    source_candidates = [p for p in files if p.suffix.lower() in SOURCE_EXTENSIONS and "generated" not in p.name.lower()]

    excel_faqs = [p for p in faq_candidates if p.suffix.lower() in {".xlsx", ".xls"}]
    old_faq = excel_faqs[0] if len(excel_faqs) == 1 else None
    if old_faq is None:
        named_faqs = [p for p in faq_candidates if "faq" in p.name.lower()]
        if len(named_faqs) == 1:
            old_faq = named_faqs[0]
    if old_faq is None:
        raise ValueError("Could not auto-detect old FAQ file. Pass --old-faq explicitly.")

    source_candidates = [p for p in source_candidates if p.resolve() != old_faq.resolve()]
    non_csv_sources = [p for p in source_candidates if p.suffix.lower() in {".pdf", ".docx", ".doc", ".json"}]
    if len(non_csv_sources) == 1:
        source = non_csv_sources[0]
    elif len(source_candidates) == 1:
        source = source_candidates[0]
    else:
        raise ValueError("Could not auto-detect source file. Pass --source explicitly.")

    return old_faq, source


def run_pipeline(
    old_faq_path: Path,
    source_path: Path,
    output_dir: Path,
    top_k: int = 3,
    max_chars: int = 1200,
    overlap_chars: int = 200,
    write_retrieval: bool = True,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Old FAQ: {old_faq_path}")
    print(f"Source:  {source_path}")

    faq_df = load_faq_source(old_faq_path)
    print(f"Loaded old FAQ rows: {len(faq_df)}")

    source_pages = load_source_documents(source_path)
    print(f"Loaded source records/pages: {len(source_pages)}")
    if not source_pages:
        raise RuntimeError("No text could be extracted from the source file.")

    chunks = split_text_into_chunks(source_pages, max_chars=max_chars, overlap_chars=overlap_chars)
    chunks_df = pd.DataFrame(chunks)
    print(f"Built source chunks: {len(chunks_df)}")
    if chunks_df.empty:
        raise RuntimeError("No chunks were created from the source text.")

    retriever = Retriever(chunks_df)
    retrieval_df = build_retrieval_df(faq_df, retriever, top_k=top_k)
    if write_retrieval:
        retrieval_path = output_dir / f"{safe_output_stem(source_path)}_faq_to_source_retrieval_results.csv"
        retrieval_df.to_csv(retrieval_path, index=False, encoding="utf-8-sig")
        print(f"Saved retrieval review CSV: {retrieval_path}")

    generated_df = build_generated_faq_df(retrieval_df)
    print(f"Generated FAQ count before cleaning: {len(generated_df)}")
    clean_df = clean_generated_faq(generated_df, faq_df)
    print(f"Generated FAQ count after cleaning: {len(clean_df)}")

    output_path = output_dir / f"{safe_output_stem(source_path)}_generated_faq_from_matched_chunks.csv"
    clean_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"Saved new FAQ CSV: {output_path}")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a new FAQ CSV from an old FAQ file and source document.",
    )
    parser.add_argument("paths", nargs="*", help="Optional positional paths: OLD_FAQ SOURCE")
    parser.add_argument("--old-faq", dest="old_faq", help="Old FAQ file (.csv, .xlsx, .xls)")
    parser.add_argument("--source", help="Source file (.pdf, .docx, .doc, .json, .csv)")
    parser.add_argument("--input-dir", default=".", help="Folder to auto-detect dropped files from")
    parser.add_argument("--output-dir", default=".", help="Folder where output CSV files are written")
    parser.add_argument("--top-k", type=int, default=3, help="Number of source chunks to retrieve per old FAQ")
    parser.add_argument("--max-chars", type=int, default=1200, help="Maximum characters per source chunk")
    parser.add_argument("--overlap-chars", type=int, default=200, help="Overlap characters between chunks")
    parser.add_argument("--no-retrieval-csv", action="store_true", help="Only write the final generated FAQ CSV")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    old_faq = Path(args.old_faq) if args.old_faq else None
    source = Path(args.source) if args.source else None

    if len(args.paths) >= 1 and old_faq is None:
        old_faq = Path(args.paths[0])
    if len(args.paths) >= 2 and source is None:
        source = Path(args.paths[1])
    if len(args.paths) > 2:
        raise SystemExit("Too many positional paths. Use: python automate_faq_generation.py OLD_FAQ SOURCE")

    if old_faq is None or source is None:
        detected_old_faq, detected_source = detect_files(Path(args.input_dir))
        old_faq = old_faq or detected_old_faq
        source = source or detected_source

    old_faq = old_faq.resolve()
    source = source.resolve()
    if not old_faq.exists():
        raise SystemExit(f"Old FAQ file not found: {old_faq}")
    if not source.exists():
        raise SystemExit(f"Source file not found: {source}")

    output_path = run_pipeline(
        old_faq_path=old_faq,
        source_path=source,
        output_dir=Path(args.output_dir).resolve(),
        top_k=args.top_k,
        max_chars=args.max_chars,
        overlap_chars=args.overlap_chars,
        write_retrieval=not args.no_retrieval_csv,
    )
    print(f"Done: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
