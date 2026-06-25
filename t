import json
import os
import requests

# Ensure your key is set in your environment: export OPENROUTER_API_KEY="your-key"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "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")
URL = "https://openrouter.ai/api/v1/chat/completions"

# Prompt shifted to Anatomy & Physiology: Cardiovascular System (Heart)
TEST_PROMPT = """You are an expert Nigerian Nursing Tutor and NMCN CBT/FQE examiner.

Generate revision material for:
Course: Anatomy and Physiology
Unit: Cardiovascular System
Topic: The Anatomy and Physiology of the Heart
Curriculum Path: Anatomy and Physiology > Cardiovascular System > The Heart

Return ONLY valid JSON:
{
  "lecture_note": {
    "emoji": "<emoji>",
    "sections": [
      {"heading": "<heading>", "content": "<content>"}
    ]
  }
}

STRICT RULES:
- Minimum 4 sections, maximum 8
- Each section: 3-6 sentences of specific, exam-relevant content
- NO generic openers like "The heart is an important organ..."
- NO conclusion section
- NO filler sentences
- NO "Nurses should be aware..." without specifics
- Every sentence must state a specific fact, value, nursing action, or mechanism
- Include specific physiological values, structural paths, and clinical relevance
- Return ONLY valid JSON, no markdown, no code fences
"""

# ─── 100% Free OpenRouter Models Only ──────────────────────────────────────
# Filtered explicitly for top performing free models to avoid 402 payment errors.
MODELS = [
    {"name": "DeepSeek: R1 (Reasoning - Free)",    "id": "deepseek/deepseek-r1:free"},
    {"name": "Meta: Llama 3.3 70B (Free)",         "id": "meta-llama/llama-3.3-70b-instruct:free"},
    {"name": "Google: Gemma 3 27B (Free)",         "id": "google/gemma-3-27b-it:free"},
    {"name": "Alibaba: Qwen 2.5 72B (Free)",       "id": "qwen/qwen-2.5-72b-instruct:free"},
    {"name": "Mistral: Mistral 7B (Free)",         "id": "mistralai/mistral-7b-instruct:free"},
]

def call_model(model_id):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://localhost:3000",
        "X-Title": "Anatomy Exam Tester"
    }
    body = {
        "model": model_id,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "temperature": 0.3
    }
    
    # 45-second timeout to handle high-demand free tiers safely
    r = requests.post(URL, headers=headers, json=body, timeout=45)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

def analyze_output(model_name, raw_text):
    print("\n" + "=" * 80)
    print(f" ANALYSIS FOR: {model_name} ")
    print("=" * 80)
    
    has_fences = "```" in raw_text
    print(f"[Rule Check] Strictly No Markdown Fences: {'❌ FAILED' if has_fences else '✅ PASSED'}")
    
    try:
        clean_text = raw_text
        if has_fences:
            clean_text = raw_text.split("```")[1]
            if clean_text.startswith("json"):
                clean_text = clean_text[4:]
            clean_text = clean_text.strip()
            
        data = json.loads(clean_text)
        sections = data.get("lecture_note", {}).get("sections", [])
        
        print(f"[Rule Check] Valid Structural JSON: ✅ PASSED")
        print(f"[Rule Check] Total Sections Generated: {len(sections)} (Target: 4-8)")
        
        print("\n--- Parsed Structural Content ---")
        print(f"Emoji Selected: {data.get('lecture_note', {}).get('emoji', 'None')}")
        for idx, sec in enumerate(sections, 1):
            heading = sec.get("heading", "No Heading Specified")
            content = sec.get("content", "")
            sentence_count = len([s for s in content.split('.') if s.strip()])
            print(f"  Section {idx}: {heading} ({sentence_count} sentences)")
            
    except Exception as e:
        print(f"[Rule Check] Valid Structural JSON: ❌ FAILED (Error: {e})")

    print("\n--- RAW MODEL OUTPUT ---")
    print(raw_text)
    print("-" * 80)


if not OPENROUTER_API_KEY:
    print("❌ Error: Please set your OPENROUTER_API_KEY environment variable first.")
    exit(1)

print("Starting cross-model anatomy prompt analysis across 5 free model endpoints...")

for m in MODELS:
    print(f"\n🚀 Dispatching request to {m['name']}...")
    try:
        raw_output = call_model(m["id"])
        analyze_output(m["name"], raw_output)
    except Exception as e:
        print(f"❌ Failed to execute {m['name']}: {e}")

print("\n Evaluation Run Finished.")
