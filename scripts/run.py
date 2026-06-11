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

# ─── Topic type normalizer — maps 52 types down to 10 ─────────────────────────
TYPE_MAP = {
    # disease group
    "disease":            "disease",
    "condition":          "disease",
    "disease_group":      "disease",
    "condition_group":    "disease",
    "complication":       "disease",
    "pathophysiology":    "disease",
    "cause":              "disease",

    # procedure group
    "procedure":          "procedure",
    "process":            "procedure",
    "method":             "procedure",
    "practice":           "procedure",
    "control":            "procedure",
    "rehabilitation":     "procedure",
    "emergency":          "procedure",
    "management":         "procedure",
    "nursing_management": "procedure",
    "prevention":         "procedure",
    "assessment":         "procedure",

    # concept group
    "concept":                    "concept",
    "theory":                     "concept",
    "history":                    "concept",
    "legal":                      "concept",
    "ethics":                     "concept",
    "comparison":                 "concept",
    "classification":             "concept",
    "need":                       "concept",
    "role":                       "concept",
    "service":                    "concept",
    "social_issue":               "concept",
    "policy":                     "concept",
    "system":                     "concept",
    "facility":                   "concept",
    "healthcare_system":          "concept",
    "academic_professional_skill":"concept",
    "communication_counselling":  "concept",
    "skill":                      "concept",
    "tool":                       "concept",
    "technology":                 "concept",
    "instrument":                 "concept",

    # organ group
    "organ":     "organ",
    "anatomy":   "organ",

    # physiology group
    "physiology":            "physiology",
    "physiological_process": "physiology",

    # drug group
    "drug":       "drug",
    "drug_class": "drug_class",

    # diagnostic group
    "diagnostic":      "diagnostic",
    "diagnostic_tool": "diagnostic_tool",

    # equipment group
    "equipment": "equipment",

    # special
    "diet":          "concept",
    "design":        "concept",
    "special_group": "concept",
    "harmful_practice": "disease",
}

# ─── Type guidance for the 10 normalized types ────────────────────────────────
TYPE_GUIDANCE = {
    "disease":   "may need: Overview, Causes/Risk Factors, Pathophysiology (stepwise mechanism), Clinical Manifestations (early vs late), Diagnosis (labs + clinical criteria), Treatment (medical + surgical), Nursing Management (prioritized interventions + rationales), Prevention (primary/secondary/tertiary), Complications (acute vs chronic).",
    "drug":      "may need: Drug Class, Mechanism of Action (stepwise receptor/biochemical effect), Indications (primary + off-label), Adverse Effects (common vs severe), Contraindications, Nursing Responsibilities (before/during/after), Patient Education, Dosage Notes.",
    "drug_class":"may need: Overview, Shared Mechanism of Action, Key Examples, Indications, Class Adverse Effects, Contraindications, Nursing Considerations (monitoring + safety patterns).",
    "organ":     "may need: Overview, Gross Structure, Microscopic Anatomy, Functions (physiological roles), Physiology (how it works), Clinical Relevance (disease states), Nursing Considerations (assessment + monitoring).",
    "physiology":"may need: Overview, Step-by-step Mechanism/Process, Regulatory Factors (hormonal/neural/chemical), Clinical Significance (what abnormalities mean), Nursing Implications (assessment + intervention).",
    "procedure": "may need: Purpose/Indications, Equipment Needed, Patient Preparation, Steps (sequential + clear), Post-procedure Care, Complications (signs + management), Nursing Responsibilities.",
    "diagnostic":"may need: Purpose, Principle, Procedure (stepwise), Normal Values/Findings, Abnormal Findings (clinical meaning), Nursing Responsibilities (before/during/after).",
    "diagnostic_tool": "may need: Overview, Principle (how it works), Indications, Procedure (stepwise), Findings Interpretation (normal vs abnormal), Nursing Responsibilities (safety + preparation + monitoring).",
    "equipment": "may need: Definition/Overview, Components, Indications, How to Use (stepwise), Safety Considerations, Nursing Responsibilities (maintenance + patient safety).",
    "concept":   "may need: Definition (precise), Principles, Classification/Types, Importance, Nursing Relevance, Clinical Application, Legal/Ethical Implications if applicable.",
}

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

# ─── Build path string ────────────────────────────────────────────────────────
def build_path(course, unit, topic):
    """Return a curriculum path string regardless of whether topic has one."""
    path_raw = topic.get("path", topic.get("context", ""))

    if isinstance(path_raw, list) and path_raw:
        return " > ".join(path_raw)
    if isinstance(path_raw, str) and path_raw.strip():
        return path_raw.strip()

    # Auto-generate from course → unit → topic
    return f"{course['course_name']} > {unit['unit_name']} > {topic['title']}"

# ─── Generate content with Groq ───────────────────────────────────────────────
def generate_content(course, unit, topic):
    raw_type     = topic.get("topic_type", "concept")
    topic_type   = TYPE_MAP.get(raw_type, "concept")
    guidance     = TYPE_GUIDANCE.get(topic_type, TYPE_GUIDANCE["concept"])
    path_str     = build_path(course, unit, topic)

    # Build coverage string
    coverage_raw = topic.get("coverage", [])
    if isinstance(coverage_raw, list) and coverage_raw:
        coverage_str = "\n".join(f"  - {item}" for item in coverage_raw)
    elif isinstance(coverage_raw, str) and coverage_raw.strip():
        coverage_str = coverage_raw.strip()
    else:
        coverage_str = ""

    # Compose context block
    context_block = (
        f"Course: {course['course_name']}\n"
        f"Unit: {unit['unit_name']}\n"
        f"Topic: {topic['title']}\n"
        f"Curriculum Path: {path_str}"
    )
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
      "explanation": "<explanation>"
    }},
    {{
      "question": "<MCQ question>",
      "options": ["<A>", "<B>", "<C>", "<D>"],
      "correct_index": 1,
      "explanation": "<explanation>"
    }},
    {{
      "question": "<MCQ question>",
      "options": ["<A>", "<B>", "<C>", "<D>"],
      "correct_index": 2,
      "explanation": "<explanation>"
    }}
  ]
}}

════════════════════════════════
LECTURE NOTE RULES

The "Suggested Topic Type" is GUIDANCE ONLY.
If the topic does not perfectly fit the suggested type, use your own judgment.
Structure the note the way a knowledgeable nurse educator would teach this topic.

Suggested headings for type "{topic_type}":
{guidance}

Rules:
- Treat suggested headings as a CHECKLIST — include only what actually applies to THIS topic
- Do not use the exact suggested heading name if a better name fits — rename freely
- Skip any heading that would be empty or forced for this topic
- Add headings not in the list if they improve understanding
- Minimum 4 sections per note
- Each section: 3-6 sentences of high-yield exam content
- No filler, no motivational language, no repetition
- Explain the WHY and HOW behind every fact — not just what, but why it matters and how it works
- Include specific values, numbers, classifications where relevant
- Include pathophysiology where applicable
- Explain the reasoning behind nursing actions
- If "Topics to Cover" is listed above, address EVERY item somewhere in the note
- Use the Curriculum Path to understand scope and context

Priority for FQE:
Definitions • Classifications • Pathophysiology • Functions • Causes • Risk factors •
Signs & symptoms • Nursing responsibilities • Nursing priorities • Complications •
Prevention • Patient education • Emergency management • Clinical decision-making •
Normal vs abnormal values • Drug calculations • Legal/ethical implications

════════════════════════════════
MCQ RULES — exactly 3 questions, strictly different levels:

Q1 — Direct recall: key definition, classification, or fact
Q2 — Application: realistic nursing/patient/community scenario
Q3 — Higher-order: nursing judgment, prioritization, best action, complication recognition

════════════════════════════════
DISTRACTOR RULES

- All 4 options from the same subject area
- Incorrect options must be plausible to an unprepared student
- No obviously wrong options
- Correct answer position varies across Q1, Q2, Q3
- Correct answer must not stand out by length or phrasing

════════════════════════════════
CHARACTER LIMITS

Question: max 280 characters
Each option: max 90 characters
Explanation: max 180 characters — must be at least 2 sentences, not 1 line

════════════════════════════════
DEPTH RULES

- Go beyond surface definitions
- Explain mechanisms step by step
- Explain why nursing actions are taken, not just what they are
- A student reading this should UNDERSTAND the topic, not just memorize it

════════════════════════════════
SELF-REVIEW BEFORE RETURNING

Check lecture note:
- Every section has minimum 3 substantive sentences?
- WHY and HOW explained throughout?
- No vague or filler sentences?
- All "Topics to Cover" items addressed?
- Content accurate for Nigerian FQE?

Check each MCQ:
- Question stem logically consistent with options?
- Correct answer actually answers the question?
- No circular reasoning (symptom used as both stem and option)?
- All 4 options equally plausible?
- Q2 scenario realistic?
- Q3 genuinely higher-order?
- Correct answer position varies across Q1/Q2/Q3?

Fix ALL issues found. Return ONLY the final corrected JSON.
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
                print(f"JSON parse error attempt {attempt+1}: {je}\nRaw: {text[:400]}")
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
    for ch in ['_', '*', '`', '[']:
        text = text.replace(ch, f"\\{ch}")
    return text

def send_lecture_note(course, unit, topic, content):
    note = content["lecture_note"]
    lines = []

    lines.append(f"{note['emoji']} *{escape_md(topic['title'].upper())}*")
    lines.append(f"📘 _{escape_md(course['course_name'])}_  •  _{escape_md(unit['unit_name'])}_")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    for section in note["sections"]:
        lines.append(f"\n*{escape_md(section['heading'])}*")
        lines.append(escape_md(section["content"]))

    lines.append("\n━━━━━━━━━━━━━━━━━━━━")
    lines.append("🧠 *Test yourself — 3 questions below!*")

    tg("sendMessage", {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": "\n".join(lines),
        "parse_mode": "Markdown"
    })

def send_poll_with_spoiler(poll, index):
    question    = poll["question"][:280]
    options     = [opt[:90] for opt in poll["options"]]
    explanation = poll["explanation"][:180]

    tg("sendPoll", {
        "chat_id": TELEGRAM_CHAT_ID,
        "question": f"Q{index}: {question}"[:300],
        "options": options,
        "type": "quiz",
        "correct_option_id": poll["correct_index"],
        "explanation": explanation,
        "is_anonymous": True
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
            "text": "🎉 *Congratulations!* You have completed all topics in your curriculum! Time to review weak areas! 💪",
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
