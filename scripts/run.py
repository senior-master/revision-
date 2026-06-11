import os
import json
import time
import requests
from datetime import datetime, date

# ─── Config from GitHub Secrets ───────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
GROQ_API_KEY       = os.environ["GROQ_API_KEY"]

GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# ─── Load files ───────────────────────────────────────────────────────────────
with open("curriculum.json", "r") as f:
    curriculum_data = json.load(f)

with open("state.json", "r") as f:
    state = json.load(f)

courses = curriculum_data["curriculum"]

# ─── Find next topic ──────────────────────────────────────────────────────────
def get_next_topic():
    total_courses = len(courses)
    attempts = 0

    while attempts < total_courses:
        c_idx = state["course_pointer"] % total_courses
        course = courses[c_idx]
        course_id = course["course_id"]
        units = course["units"]

        u_idx = state["unit_pointers"].get(course_id, 0)
        if u_idx >= len(units):
            state["course_pointer"] = (c_idx + 1) % total_courses
            attempts += 1
            continue

        unit = units[u_idx]
        unit_id = unit["unit_id"]
        topics = unit["topics"]

        t_idx = state["topic_pointers"].get(unit_id, 0)
        if t_idx >= len(topics):
            state["unit_pointers"][course_id] = u_idx + 1
            state["topic_pointers"][unit_id] = 0
            attempts += 1
            continue

        topic = topics[t_idx]
        state["topic_pointers"][unit_id] = t_idx + 1

        return course, unit, topic

    return None, None, None

# ─── Generate content with Groq ───────────────────────────────────────────────
def generate_content(course, unit, topic):
    topic_type = topic.get("topic_type", "concept")

    # Guidance per type — Groq uses these as suggestions, not strict rules
    type_guidance = {
        "disease":   "Overview, Causes/Risk Factors, Pathophysiology, Clinical Manifestations, Diagnosis, Treatment, Nursing Management, Prevention, Complications",
        "drug":      "Drug Class, Mechanism of Action, Indications, Adverse Effects, Contraindications, Nursing Responsibilities, Patient Education, Dosage Notes",
        "organ":     "Overview, Structure, Anatomy, Functions, Physiology, Clinical Relevance, Nursing Considerations",
        "procedure": "Purpose/Indications, Equipment Needed, Preparation, Steps, Post-procedure Care, Complications, Nursing Responsibilities",
        "theory":    "Overview, Author/Origin, Key Concepts, Components/Stages/Principles, Application to Nursing Practice, Limitations",
        "concept":   "Definition, Key Principles, Classification/Types, Importance, Nursing Relevance, Clinical Application",
        "physiology":"Overview, Mechanism/Process, Regulatory Factors, Clinical Significance, Nursing Implications",
        "diagnostic":"Purpose, Principle, Procedure, Normal Values/Findings, Abnormal Findings, Nursing Responsibilities",
        "diagnostic_tool": "Overview, Principle, Indications, Procedure, Findings Interpretation, Nursing Responsibilities",
        "equipment": "Definition/Overview, Components, Indications, How to Use, Safety Considerations, Nursing Responsibilities",
        "drug_class": "Overview, Mechanism of Action, Examples, Indications, Adverse Effects, Nursing Considerations",
        "healthcare_system": "Definition, Structure, Functions, Key Components, Nursing Role, Challenges",
        "communication_counselling": "Definition, Principles, Types/Techniques, Barriers, Nursing Application, Therapeutic Use",
        "academic_professional_skill": "Definition, Importance, Key Components, Steps/Process, Nursing Application",
    }

    guidance = type_guidance.get(topic_type, type_guidance["concept"])

    # Build path string for context
    path_raw = topic.get("path", topic.get("context", ""))
    if isinstance(path_raw, list):
        path_str = " > ".join(path_raw)
    else:
        path_str = str(path_raw) if path_raw else ""

    # Build coverage string
    coverage_raw = topic.get("coverage", [])
    if isinstance(coverage_raw, list) and coverage_raw:
        coverage_str = "\n".join(f"  - {item}" for item in coverage_raw)
    elif isinstance(coverage_raw, str) and coverage_raw:
        coverage_str = coverage_raw
    else:
        coverage_str = ""

    # Compose context block
    context_block = f"Course: {course['course_name']}\nUnit: {unit['unit_name']}\nTopic: {topic['title']}"
    if path_str:
        context_block += f"\nCurriculum Path: {path_str}"
    if coverage_str:
        context_block += f"\nTopics to Cover:\n{coverage_str}"

    prompt = f"""You are an expert Nigerian Nursing Tutor and Nursing & Midwifery Council (NMC) CBT examiner.

Your task is to generate detailed, exam-focused revision material for a student preparing for the Final Qualifying Examination (FQE).

{context_block}
Suggested Topic Type: {topic_type}

════════════════════════════════
OUTPUT SCHEMA

Return ONLY this JSON object — no markdown, no code fences, no text outside JSON:

{{
  "lecture_note": {{
    "emoji": "<one relevant emoji>",
    "sections": [
      {{"heading": "<heading>", "content": "<content>"}}
    ]
  }},
  "polls": [
    {{
      "question": "<MCQ question>",
      "options": ["<A>", "<B>", "<C>", "<D>"],
      "correct_index": 0,
      "explanation": "<brief explanation>"
    }},
    {{
      "question": "<MCQ question>",
      "options": ["<A>", "<B>", "<C>", "<D>"],
      "correct_index": 1,
      "explanation": "<brief explanation>"
    }},
    {{
      "question": "<MCQ question>",
      "options": ["<A>", "<B>", "<C>", "<D>"],
      "correct_index": 2,
      "explanation": "<brief explanation>"
    }}
  ],
  "exam_trap": {{
    "mistake": "<single most common student mistake on this topic>",
    "correction": "<accurate correction in one clear sentence>"
  }}
}}

════════════════════════════════
LECTURE NOTE RULES

The "Suggested Topic Type" is GUIDANCE ONLY.
If the topic does not fit the suggested type, use your judgment and generate the most appropriate headings.
You are a tutor — structure the note the way a knowledgeable nurse would teach it.

Suggested heading structure for type "{topic_type}":
{guidance}

General rules:
- The suggested headings for your topic type are a CHECKLIST, not a template
- For EACH suggested heading, ask yourself: "Does this heading actually apply to this specific topic?"
- If YES → include it
- If NO → discard it completely, do not force it
- If a heading would be empty or irrelevant for this topic, skip it
- If an important heading is missing from the suggestions, add it yourself
- The final note must feel naturally structured for THIS topic, not copy-pasted from a template
- Each section: 3-6 concise sentences of high-yield exam content
- No filler, no motivational language, no repetition
- If "Topics to Cover" is provided above, ensure EVERY item listed is addressed somewhere in the note
- If the curriculum path is provided, use it to understand the topic's context and scope

Priority content for FQE:
Definitions • Classifications • Pathophysiology • Functions • Causes • Risk factors •
Signs & symptoms • Nursing responsibilities • Nursing priorities • Complications •
Prevention • Patient education • Emergency management • Clinical decision-making •
Normal vs abnormal values • Drug calculations • Legal/ethical implications

════════════════════════════════
MCQ RULES

Exactly 3 questions — strictly different difficulty levels:

Q1 — Direct recall: test a key definition, classification, or fact
Q2 — Application: short nursing/patient/community scenario requiring knowledge application  
Q3 — Higher-order: prioritization, nursing judgment, best action, or complication recognition

════════════════════════════════
DISTRACTOR RULES

- All 4 options must belong to the same subject area
- Incorrect options must be plausible — a student who has not studied could easily pick them
- Do NOT use obviously wrong options
- Correct answer position must vary across Q1, Q2, Q3 (do not always put it at index 0)
- Correct answer should not stand out by length or phrasing

════════════════════════════════
CHARACTER LIMITS

Question: max 280 characters
Each option: max 90 characters
Explanation: max 180 characters

════════════════════════════════
EXAM TRAP

The single most likely mistake a student makes on this topic in a CBT exam.
State the mistake clearly. Then give the accurate correction.
This is often more memorable than an extra paragraph of notes.
"""

    for attempt in range(3):
        try:
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            body = {
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4
            }
            response = requests.post(GROQ_URL, headers=headers, json=body, timeout=60)
            response.raise_for_status()

            text = response.json()["choices"][0]["message"]["content"].strip()

            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            try:
                return json.loads(text)
            except json.JSONDecodeError as je:
                print(f"JSON parse error on attempt {attempt+1}: {je}\nRaw: {text[:400]}")
                if attempt < 2:
                    time.sleep(10)
                    continue
                raise

        except json.JSONDecodeError:
            raise
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                wait = 30 * (attempt + 1)
                print(f"Rate limited. Waiting {wait}s before retry {attempt+2}/3...")
                time.sleep(wait)
            else:
                raise

# ─── Telegram helpers ─────────────────────────────────────────────────────────
def tg(method, payload):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    r = requests.post(url, json=payload, timeout=15)
    if not r.ok:
        print(f"Telegram error [{method}]: {r.status_code} — {r.text}")
        r.raise_for_status()
    return r.json()

def escape_md(text):
    """Escape Markdown v1 special chars for Telegram."""
    for ch in ['_', '*', '`', '[']:
        text = text.replace(ch, f"\\{ch}")
    return text

def send_lecture_note(course, unit, topic, content):
    note = content["lecture_note"]
    trap = content.get("exam_trap")
    lines = []

    # Header
    lines.append(f"{note['emoji']} *{escape_md(topic['title'].upper())}*")
    lines.append(f"📘 _{escape_md(course['course_name'])}_  •  _{escape_md(unit['unit_name'])}_")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    # Sections
    for section in note["sections"]:
        lines.append(f"\n*{escape_md(section['heading'])}*")
        lines.append(escape_md(section["content"]))

    # Exam trap
    if trap:
        lines.append("\n━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ *COMMON EXAM TRAP*")
        lines.append(f"❌ {escape_md(trap['mistake'])}")
        lines.append(f"✅ {escape_md(trap['correction'])}")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━")
    lines.append("🧠 *Test yourself — 3 questions below\\!*")

    message = "\n".join(lines)

    tg("sendMessage", {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    })

def send_poll_with_spoiler(poll, index):
    question   = poll["question"][:280]
    options    = [opt[:90] for opt in poll["options"]]
    explanation = poll["explanation"][:180]

    tg("sendPoll", {
        "chat_id": TELEGRAM_CHAT_ID,
        "question": f"Q{index}: {question}"[:300],
        "options": options,
        "type": "quiz",
        "correct_option_id": poll["correct_index"],
        "explanation": explanation,
        "is_anonymous": False
    })

# ─── Save state ───────────────────────────────────────────────────────────────
def save_state():
    state["last_run"] = datetime.utcnow().isoformat()
    with open("state.json", "w") as f:
        json.dump(state, f, indent=2)

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    course, unit, topic = get_next_topic()

    if not course:
        tg("sendMessage", {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": "🎉 *Congratulations\\!* You have completed all topics in your curriculum\\! Time to review weak areas\\! 💪",
            "parse_mode": "Markdown"
        })
        return

    print(f"[{course['course_id']}] {unit['unit_name']} > {topic['title']}")

    content = generate_content(course, unit, topic)

    send_lecture_note(course, unit, topic, content)

    for i, poll in enumerate(content["polls"], 1):
        send_poll_with_spoiler(poll, i)

    state["total_sent"] = state.get("total_sent", 0) + 1
    state["completed_topics"].append(topic["topic_id"])

    save_state()
    print(f"Done. Total sent: {state['total_sent']}")

if __name__ == "__main__":
    main()
