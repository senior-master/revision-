import json
import os
import requests
import time

# Ensure your key is set in your environment: export OPENROUTER_API_KEY="your-key"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "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")
URL = "https://openrouter.ai/api/v1/chat/completions"

# Target Topic: Anatomy & Physiology of the Heart
TEST_PROMPT = """You are an expert Nigerian Nursing Tutor and NMCN CBT/FQE examiner.

Generate revision material for:
Course: Anatomy and Physiology
Unit: community health nursing 
Topic: malaria 
Curriculum Path: epidemiology and control of commucable disease/ malaria


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

# Hardcoded precise IDs for your custom ranked list
TARGET_MODELS = [
    {"name": "OpenAI: GPT-OSS 120B", "id": "openai/gpt-oss-120b:free"},
    {"name": "DeepSeek: R1 (Free Distill Qwen 32B)", "id": "deepseek/deepseek-r1-distill-qwen-32b:free"},
    {"name": "Poolside: Laguna M.1", "id": "poolside/laguna-m.1-20260312:free"},
    {"name": "Google: Gemma 4 31B", "id": "google/gemma-4-31b-it-20260402:free"},
    {"name": "Nvidia: Nemotron 30B Reasoning", "id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning-20260428:free"},
    {"name": "OpenAI: GPT-OSS 20B", "id": "openai/gpt-oss-20b:free"}
]

def call_targeted_model(model_id):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://localhost:3000",
        "X-Title": "Targeted Board Review Generator"
    }
    body = {
        "model": model_id,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "temperature": 0.3
    }
    
    response = requests.post(URL, headers=headers, json=body, timeout=45)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()

def verify_and_display(model_name, raw_text):
    print("\n" + "=" * 80)
    print(f" TARGET RUN OUTPUT: {model_name} ")
    print("=" * 80)
    
    has_fences = "```" in raw_text
    print(f"[Schema Check] Strictly No Markdown Fences: {'❌ FAILED' if has_fences else '✅ PASSED'}")
    
    try:
        clean_text = raw_text
        if has_fences:
            clean_text = raw_text.split("```")[1]
            if clean_text.startswith("json"):
                clean_text = clean_text[4:]
            clean_text = clean_text.strip()
            
        data = json.loads(clean_text)
        sections = data.get("lecture_note", {}).get("sections", [])
        print(f"[Schema Check] Valid Structural JSON: ✅ PASSED")
        print(f"[Schema Check] Total Sections: {len(sections)}")
        
    except Exception as e:
        print(f"[Schema Check] Valid Structural JSON: ❌ FAILED (Error: {e})")

    print("\n--- RAW DATA RECEIVED ---")
    print(raw_text)
    print("-" * 80)


if not OPENROUTER_API_KEY:
    print("❌ Error: Export your OPENROUTER_API_KEY prior to script execution.")
    exit(1)

print(f"Commencing parallel execution batch across {len(TARGET_MODELS)} ranked endpoints...")

for model in TARGET_MODELS:
    print(f"\n📡 Requesting payload from {model['name']}...")
    try:
        raw_output = call_targeted_model(model["id"])
        verify_and_display(model["name"], raw_output)
    except Exception as e:
        print(f"❌ Critical Endpoint Failure for {model['name']}: {e}")
        
    # Standard spacing delay between batch hits
    time.sleep(2)

print("\nAll targeted outputs gathered. Paste the results here, and we will construct the robust multi-retry fallback system.")
