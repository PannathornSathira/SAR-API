# backend/verify_backend.py

import os
import sys
from dotenv import load_dotenv

# Ensure backend folder is in path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from app.vector_store import create_collection, get_vector_store, get_collections, client
from app.retrieval import retrieve_and_rerank
from app.agents import rewrite_query, synthesize_answer
from langchain_core.documents import Document

TEST_COLLECTION = "verify_test_faq_collection"

def run_tests():
    print("=== SAR API Service Verification Script ===")
    
    # 1. Check API Key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found in environment. Exiting.")
        return
    print("✅ OpenAI API Key detected.")
    
    # 2. Test Qdrant Connection
    try:
        qdrant_version = client.info().version
        print(f"✅ Qdrant connection successful. Qdrant version: {qdrant_version}")
    except Exception as e:
        print(f"❌ Error: Cannot connect to Qdrant at {os.getenv('QDRANT_URL', 'http://localhost:6333')}: {e}")
        return

    # 3. Create Collection (Hybrid setup: Dense + Sparse)
    print(f"\n[Test 1] Creating collection: '{TEST_COLLECTION}'...")
    try:
        create_collection(TEST_COLLECTION)
        registered_collections = get_collections()
        assert TEST_COLLECTION in registered_collections, "Collection not found in registry"
        print(f"✅ Collection created and verified in registry.")
    except Exception as e:
        print(f"❌ Error creating collection: {e}")
        return

    # 4. Ingest Mock FAQ pairs
    print(f"\n[Test 2] Ingesting Mock FAQ pairs into '{TEST_COLLECTION}'...")
    mock_faqs = [
        {
            "category": "การขอใบอนุญาต",
            "question": "การขอใบอนุญาตประกอบธุรกิจบริการ Digital ID มีอายุกี่ปี",
            "answer": "การขอใบอนุญาตประกอบธุรกิจบริการ Digital ID มีอายุการใช้งานทั้งหมด 5 ปี นับตั้งแต่วันที่ได้รับการอนุมัติ"
        },
        {
            "category": "การลงนามอิเล็กทรอนิกส์",
            "question": "ลายมือชื่ออิเล็กทรอนิกส์เขียนตามกฎหมายไทยคืออะไร",
            "answer": "ลายมือชื่ออิเล็กทรอนิกส์ตาม พ.ร.บ. ว่าด้วยธุรกรรมทางอิเล็กทรอนิกส์ หมายถึง อักษร อักขระ ตัวเลข หรือสัญลักษณ์อื่นใดที่สร้างขึ้นในรูปแบบอิเล็กทรอนิกส์ซึ่งนำมาใช้ประกอบกับข้อมูลอิเล็กทรอนิกส์เพื่อแสดงความสัมพันธ์ระหว่างบุคคลกับข้อมูลดังกล่าว"
        }
    ]
    
    try:
        docs = []
        for faq in mock_faqs:
            page_content = f"คำถาม: {faq['question']}\nคำตอบ: {faq['answer']}"
            metadata = {
                "category": faq["category"],
                "original_question": faq["question"],
                "answer": faq["answer"],
                "source_file": "mock_test_file.docx"
            }
            docs.append(Document(page_content=page_content, metadata=metadata))
            
        store = get_vector_store(TEST_COLLECTION)
        store.add_documents(docs)
        print(f"✅ Ingested {len(docs)} document cards successfully.")
    except Exception as e:
        print(f"❌ Ingestion failed: {e}")
        return

    # Wait a moment for Qdrant indexing
    import time
    time.sleep(1)

    # 5. RAG Pipeline Query Tests
    print("\n[Test 3] Running query-time RAG pipeline...")
    
    test_cases = [
        {
            "name": "Exact Match (Thai Question)",
            "query": "ใบอนุญาต Digital ID มีอายุการใช้งานกี่ปี",
            "chat_history": []
        },
        {
            "name": "Related Match (Thai Question)",
            "query": "ช่วยอธิบายความหมายของลายมือชื่อตามกฎหมายไทยหน่อย",
            "chat_history": []
        },
        {
            "name": "No Match (Fallback Output)",
            "query": "วันนี้ฝนจะตกที่กรุงเทพไหมครับ",
            "chat_history": []
        }
    ]
    
    for case in test_cases:
        print(f"\n--- Running Case: {case['name']} ---")
        print(f"Query: '{case['query']}'")
        
        try:
            # A. Query Rewrite
            rewritten = rewrite_query(case["query"], case["chat_history"])
            
            # B. Retrieval & Rerank
            contexts, score = retrieve_and_rerank(TEST_COLLECTION, rewritten)
            print(f"Reranker Highest Score: {score:.4f}")
            
            # C. Synthesize
            response, match_type = synthesize_answer(rewritten, contexts, score)
            print(f"Match Type: {match_type.upper()}")
            print(f"Response: {response}")
            
            # Basic Assertions
            if case["name"] == "Exact Match (Thai Question)":
                assert score >= 0.525, "Expected exact match score (>=0.525)"
                assert "5 ปี" in response, "Expected response to mention 5 years"
            elif case["name"] == "No Match (Fallback Output)":
                assert score < 0.30, "Expected low score (<0.30)"
                assert "นอกเหนือขอบเขต" in response, "Expected fallback message"
                
            print(f"✅ Case '{case['name']}' passed.")
            
        except Exception as e:
            print(f"❌ Case '{case['name']}' failed with error: {e}")
            import traceback
            traceback.print_exc()

    # 6. Cleaning Up
    print(f"\n[Test 4] Cleaning up collection '{TEST_COLLECTION}'...")
    try:
        client.delete_collection(TEST_COLLECTION)
        registry = get_collections()
        if TEST_COLLECTION in registry:
            registry.remove(TEST_COLLECTION)
            from app.vector_store import save_registry
            save_registry(registry)
        print("✅ Cleaned up successfully.")
    except Exception as e:
        print(f"⚠️ Failed to clean up collection: {e}")

    print("\n=== Verification Complete ===")

if __name__ == "__main__":
    run_tests()
