import requests 
import json

# ─── Test topic (same for all models) ────────────────────────────────────────
TEST_PROMPT = """You are an expert Nigerian Nursing Tutor and NMCN CBT/FQE examiner.

Generate revision material for:
Course: Foundation of Nursing I
Unit: Basic Client/Patient Care
Topic: Personal Hygiene in Nursing
Curriculum Path: Foundation of Nursing I > Basic Client/Patient Care > Personal Hygiene

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
- NO generic openers like "Personal hygiene is important for nurses..."
- NO conclusion section
- NO filler sentences
- NO "Nurses should be aware..." without specifics
- Every sentence must state a specific fact, value, nursing action, or mechanism
- Include specific nursing steps, assessment points, and clinical relevance
- Return ONLY valid JSON, no markdown, no code fences
"""

# ─── Models to test ───────────────────────────────────────────────────────────
MODELS = {
    "groq_llama3.3_70b": {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY"
    },
    "groq_llama3.1_8b": {
        "provider": "groq",
        "model": "llama-3.1-8b-instant",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY"
    },
    "groq_mixtral": {
        "provider": "groq",
        "model": "mixtral-8x7b-32768",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY"
    },
    "gemini_flash": {
        "provider": "gemini",
        "model": "gemini-2.0-flash",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        "key_env": "GEMINI_API_KEY"
    },
    "openrouter_mistral": {
        "provider": "openrouter",
        "model": "mistralai/mistral-7b-instruct:free",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key_env": "OPENROUTER_API_KEY"
    },
    "openrouter_llama": {
        "provider": "openrouter",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key_env": "OPENROUTER_API_KEY"
    },
}

import os

def call_groq_or_openrouter(config, api_key):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    body = {
        "model": config["model"],
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "temperature": 0.4
    }
    r = requests.post(config["url"], headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

def call_gemini(config, api_key):
    url = f"{config['url']}?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": TEST_PROMPT}]}],
        "generationConfig": {"temperature": 0.4}
    }
    r = requests.post(url, json=body, timeout=30)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

def clean_json(text):
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()

def score_response(text, model_name):
    """Simple scoring based on filler detection and content quality."""
    score = 100
    penalties = []

    filler_patterns = [
        "is important for nurses",
        "plays a crucial role",
        "is essential for",
        "in conclusion",
        "nurses should be aware",
        "understanding this topic",
        "learning about",
        "is a critical aspect",
        "is significant",
        "it is important to note",
    ]

    text_lower = text.lower()
    for pattern in filler_patterns:
        if pattern in text_lower:
            score -= 15
            penalties.append(f"FILLER: '{pattern}'")

    # Check section count
    try:
        parsed = json.loads(clean_json(text))
        sections = parsed.get("lecture_note", {}).get("sections", [])
        count = len(sections)
        if count < 4:
            score -= 20
            penalties.append(f"Too few sections: {count}")
        elif count > 8:
            score -= 5
            penalties.append(f"Too many sections: {count}")
        else:
            penalties.append(f"Sections: {count} ✓")
    except:
        score -= 30
        penalties.append("INVALID JSON")

    return score, penalties

print("=" * 60)
print("MODEL COMPARISON TEST")
print("Topic: Personal Hygiene in Nursing")
print("=" * 60)

results = {}

for name, config in MODELS.items():
    api_key = os.environ.get(config["key_env"], "")
    if not api_key:
        print(f"\n[{name}] SKIPPED — no API key ({config['key_env']})")
        continue

    print(f"\n[{name}] Testing...")
    try:
        if config["provider"] == "gemini":
            text = call_gemini(config, api_key)
        else:
            text = call_groq_or_openrouter(config, api_key)

        score, penalties = score_response(text, name)
        results[name] = {"score": score, "text": text, "penalties": penalties}

        print(f"  Score: {score}/100")
        for p in penalties:
            print(f"  {p}")

        # Show first section content
        try:
            parsed = json.loads(clean_json(text))
            sections = parsed["lecture_note"]["sections"]
            print(f"  First section heading: '{sections[0]['heading']}'")
            print(f"  First sentence: '{sections[0]['content'][:120]}...'")
        except:
            print(f"  Raw (first 200): {text[:200]}")

    except Exception as e:
        print(f"  ERROR: {e}")

# ─── Final ranking ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("RANKING")
print("=" * 60)
if results:
    ranked = sorted(results.items(), key=lambda x: x[1]["score"], reverse=True)
    for i, (name, data) in enumerate(ranked, 1):
        print(f"{i}. {name}: {data['score']}/100")
else:
    print("No results — add API keys as environment variables")

print("\nTo run with keys:")
print("GROQ_API_KEY=xxx GEMINI_API_KEY=xxx OPENROUTER_API_KEY=xxx python3 test_models.py")
