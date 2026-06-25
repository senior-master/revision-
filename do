import json
import os
import requests
import time

# Ensure your key is set in your environment: export OPENROUTER_API_KEY="your-key"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "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")
URL = "https://openrouter.ai/api/v1/chat/completions"

# Prompt shifted to Anatomy & Physiology: Cardiovascular System (Heart)
TEST_PROMPT = """You are an expert Nigerian Nursing Tutor and NMCN CBT/FQE examiner.

Generate revision material for:
Course: Anatomy and Physiology
Unit: lymphatic system 
Topi: lymphatic system 
Curriculum Path: Anatomy and Physiology > lymphatic system 

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

def call_free_router():
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://localhost:3000",
        "X-Title": "Anatomy Exam Tester"
    }
    body = {
        # Using the universal free router to dynamically grab available free models
        "model": "openrouter/free",
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "temperature": 0.4
    }
    
    r = requests.post(URL, headers=headers, json=body, timeout=45)
    r.raise_for_status()
    response_json = r.json()
    
    # Extract which model the router actually paired us with
    dispatched_model = response_json.get("model", "Unknown Free Model")
    content = response_json["choices"][0]["message"]["content"].strip()
    return dispatched_model, content

def analyze_output(run_number, model_name, raw_text):
    print("\n" + "=" * 80)
    print(f" ANALYSIS FOR RUN #{run_number}: {model_name} ")
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

print("Starting 5-run analysis using the universal openrouter/free gateway...")

for run in range(1, 9):
    print(f"\n🚀 Dispatching free-tier generation test #{run}...")
    try:
        actual_model_used, raw_output = call_free_router()
        analyze_output(run, actual_model_used, raw_output)
        
        # Short cooldown to avoid aggressive rate limiting between iterations
        if run < 9:
            print("⏳ Pausing 3 seconds to keep rate limits happy...")
            time.sleep(3)
            
    except Exception as e:
        print(f"❌ Failed to execute run #{run}: {e}")

print("\n Evaluation Run Finished.")

