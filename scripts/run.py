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

# ─── Topic type normalizer — maps all types down to 10 ────────────────────────
TYPE_MAP = {
    "disease": "disease", "condition": "disease", "disease_group": "disease",
    "condition_group": "disease", "complication": "disease",
    "pathophysiology": "disease", "cause": "disease", "harmful_practice": "disease",
    "procedure": "procedure", "process": "procedure", "method": "procedure",
    "practice": "procedure", "control": "procedure", "rehabilitation": "procedure",
    "emergency": "procedure", "management": "procedure",
    "nursing_management": "procedure", "prevention": "procedure",
    "assessment": "procedure",
    "concept": "concept", "theory": "concept", "history": "concept",
    "legal": "concept", "ethics": "concept", "comparison": "concept",
    "classification": "concept", "need": "concept", "role": "concept",
    "service": "concept", "social_issue": "concept", "policy": "concept",
    "system": "concept", "facility": "concept", "healthcare_system": "concept",
    "academic_professional_skill": "concept", "communication_counselling": "concept",
    "skill": "concept", "tool": "concept", "technology": "concept",
    "instrument": "concept", "diet": "concept", "design": "concept",
    "special_group": "concept",
    "organ": "organ", "anatomy": "organ",
    "physiology": "physiology", "physiological_process": "physiology",
    "drug": "drug", "drug_class": "drug_class",
    "diagnostic": "diagnostic", "diagnostic_tool": "diagnostic_tool",
    "equipment": "equipment",
}

# ─── Type context hints (NOT heading templates — just thinking guidance) ───────
TYPE_HINTS = {
    "disease":        "This is a disease/condition. Key examinable areas typically include: aetiology, pathophysiology, clinical features, diagnosis, medical/nursing management, complications, prevention.",
    "drug":           "This is a specific drug. Key examinable areas typically include: drug class, mechanism of action, indications, adverse effects, contraindications, nursing responsibilities, patient education.",
    "drug_class":     "This is a drug class/group. Key examinable areas typically include: shared mechanism, class examples, indications, class adverse effects, nursing monitoring patterns.",
    "organ":          "This is an organ or anatomical structure. Key examinable areas typically include: structure, location, functions, physiological roles, clinical relevance, nursing assessment focus.",
    "physiology":     "This is a physiological process. Key examinable areas typically include: step-by-step mechanism, regulatory factors, normal values, clinical significance of abnormalities, nursing implications.",
    "procedure":      "This is a nursing/clinical procedure or process. Key examinable areas typically include: purpose, indications, equipment, preparation, steps, post-procedure care, complications, nursing responsibilities.",
    "diagnostic":     "This is a diagnostic test or investigation. Key examinable areas typically include: purpose, principle, normal values, abnormal findings and their meaning, nursing responsibilities before/during/after.",
    "diagnostic_tool":"This is a diagnostic device or tool. Key examinable areas typically include: principle of operation, indications, how to use, findings interpretation, nursing responsibilities.",
    "equipment":      "This is clinical equipment. Key examinable areas typically include: components, indications, correct usage, safety considerations, nursing responsibilities.",
    "concept":        "This is a concept, theory, principle, or professional topic. Key examinable areas typically include: definition, principles, classification, importance, nursing application, clinical or legal relevance.",
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
    path_raw = topic.get("path", topic.get("context", ""))
    if isinstance(path_raw, list) and path_raw:
        return " > ".join(path_raw)
    if isinstance(path_raw, str) and path_raw.strip():
        return path_raw.strip()
    return f"{course['course_name']} > {unit['unit_name']} > {topic['title']}"

# ─── Generate content with Groq ───────────────────────────────────────────────
def generate_content(course, unit, topic):
    raw_type   = topic.get("topic_type", "concept")
    topic_type = TYPE_MAP.get(raw_type, "concept")
    type_hint  = TYPE_HINTS.get(topic_type, TYPE_HINTS["concept"])
    path_str   = build_path(course, unit, topic)

    coverage_raw = topic.get("coverage", [])
    if isinstance(coverage_raw, list) and coverage_raw:
        coverage_str = "\n".join(f"  - {item}" for item in coverage_raw)
    elif isinstance(coverage_raw, str) and coverage_raw.strip():
        coverage_str = coverage_raw.strip()
    else:
        coverage_str = ""

    context_block = (
        f"Course: {course['course_name']}\n"
        f"Unit: {unit['unit_name']}\n"
        f"Topic: {topic['title']}\n"
        f"Curriculum Path: {path_str}"
    )
    if coverage_str:
        context_block += f"\nTopics to Cover:\n{coverage_str}"

    prompt = f"""You are an expert Nigerian Nursing Tutor, Nurse Educator, and Nursing & Midwifery Council (NMCN) CBT/FQE examiner.

Your task is to generate accurate, exam-focused nursing revision material from the curriculum topic provided.

════════════════════════════════
COURSE CONTEXT

{context_block}
Suggested Topic Type: {topic_type}
Type Guidance: {type_hint}

════════════════════════════════
OUTPUT FORMAT

Return ONLY valid JSON — no markdown, no code fences, no commentary:

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
BEFORE WRITING — THINK FIRST (do not include this in output):

1. What are the core examinable concepts of this specific topic?
2. What do students commonly confuse or get wrong about this topic?
3. What are the priority nursing responsibilities for this topic?
4. What would an NMCN examiner most likely test on this topic?
5. What is the best structure to teach THIS topic clearly?

Use your answers to guide what you write. Do not reveal this planning.

════════════════════════════════
HEADING RULES

Choose headings freely — there is no fixed template.

Use only headings that genuinely help explain THIS topic.
Rename headings if a better name fits.
Add headings when needed.
Skip headings that do not apply to this topic.
Avoid empty or near-empty sections.

The Type Guidance above shows what is typically examinable for this topic type.
Use it as a thinking aid — not as a heading list to copy.

════════════════════════════════
CONTENT RULES

Write like a skilled nurse educator teaching this topic to final-year students.

Focus on:
- Exam relevance — what is likely to be tested
- Clinical relevance — what matters at the bedside
- Nursing relevance — what the nurse must know and do
- Mechanisms — how and why things happen
- Decision-making — how nurses should respond

Avoid ALL of the following — strictly banned:
- Generic opening sentences that restate the topic title
- Sentences like "Learning X is crucial for nurses..." or "Understanding X is important because..."
- Sentences like "Nurses should be aware of X" without saying what X specifically is
- Motivational or encouraging statements of any kind
- Conclusion sections — revision notes have no conclusion
- Filler sentences that explain why a topic matters without actually teaching it
- Repeating the same point across different sections
- Obvious beginner-level facts with no exam value
- Vague nursing statements without specific clinical detail

BANNED sentence patterns — never write anything like these:
"[Topic] is an important aspect of nursing care."
"Learning about [topic] is crucial for nurses to provide quality care."
"Understanding [topic] helps nurses improve patient outcomes."
"In conclusion, [topic] is a critical part of nursing."
"Nurses should be sensitive to patient needs and incorporate them into care plans."
"[Topic] plays a significant role in maintaining health."

REQUIRED — every sentence must do one of these:
- State a specific fact, value, classification, or mechanism
- Describe a concrete nursing action with its rationale
- Explain a cause-effect relationship
- Describe a clinical sign, symptom, or finding
- Give a specific intervention, drug, dose range, or procedure step

Bad: "Blood is a vital fluid that circulates through the body."
Good: "Blood comprises plasma (~55%) and formed elements (~45%). Plasma transports nutrients, hormones, clotting factors, and waste. Formed elements include erythrocytes (O2 transport), leukocytes (immunity), and thrombocytes (haemostasis)."

Bad: "Nurses should promote rest and sleep as it is important for recovery."
Good: "Cluster nursing activities to allow 90-minute uninterrupted sleep cycles. Offer earplugs, dim lighting after 9PM, and schedule non-urgent medications outside sleep hours. Avoid waking patients for routine observations unless clinically indicated."

════════════════════════════════
DEPTH RULES

Explain concepts — do not just list facts.

Where relevant:
- Explain the mechanism (how it works)
- Explain the relationship (how parts connect)
- Explain cause and effect (what leads to what)
- Explain clinical significance (why it matters)
- Explain nursing rationale (why the nurse does this)

If you are not certain of a mechanism, describe what is established.
Do not invent mechanisms, values, or guidelines.

Include specific values, classifications, stages, and percentages where established and relevant.

════════════════════════════════
STRUCTURE RULES

Minimum: 4 sections
Maximum: 8 sections

Each section:
- Must contain substantive content (3-6 sentences)
- Must teach something useful and exam-relevant
- Must not repeat content from another section
- Must not open by restating the heading as a sentence

The note should read like a concise, focused lecture — not a dictionary entry.

════════════════════════════════
CURRICULUM COVERAGE

If "Topics to Cover" are listed above:
Every item must be addressed somewhere in the note.
Do not skip any listed item.
Use the Curriculum Path to understand the scope and context of this topic.

════════════════════════════════
EXAM PRIORITIES

Prioritize content commonly tested in NMCN CBT, FQE, and nursing school examinations.

Emphasize where relevant:
Definitions • Classifications • Functions • Causes • Risk factors •
Clinical manifestations • Pathophysiology • Diagnosis • Treatment •
Nursing management • Prevention • Complications • Patient education •
Emergency management • Professional responsibilities • Legal and ethical considerations •
Normal and abnormal values • Drug calculations • Nigerian health context

════════════════════════════════
MCQ GENERATION — exactly 3 questions:

Q1 — Direct recall: test a key definition, classification, value, or fact
Q2 — Application: realistic nursing/patient/community scenario with enough detail to justify one answer
Q3 — Clinical judgment: prioritization, complication recognition, best nursing action, or decision-making

Difficulty increases from Q1 to Q3.

════════════════════════════════
MCQ QUALITY RULES

Every question must have ONE clearly best answer.
Avoid questions where two options could reasonably both be correct.
Provide enough clinical detail in scenarios to justify the correct answer.
Do not create trick questions or deliberately misleading stems.

For prioritization questions, apply ABCDE principles:
Airway → Breathing → Circulation → Disability → Exposure
The correct answer must reflect the highest priority threat to patient safety.

════════════════════════════════
DISTRACTOR RULES

All 4 options must belong to the same clinical category:
- Causes with causes
- Types with types
- Nursing actions with nursing actions
- Drugs with drugs
- Values with values

Incorrect options must be plausible — representing common mistakes or partially correct alternatives.
Avoid obviously wrong answers.
Correct answer must not stand out by length, detail, or phrasing.
Correct answer position must vary: Q1, Q2, Q3 should not all have the same index.

════════════════════════════════
CHARACTER LIMITS

Question: max 280 characters
Each option: max 90 characters
Explanation: max 180 characters

Explanation must address:
- Why the correct answer is correct
- Why the other options are less appropriate

════════════════════════════════
NIGERIAN CONTEXT

Where relevant, align with:
- NMCN expectations and scope of practice
- Primary Health Care principles
- Safe Motherhood and IMNCI guidelines
- Nigerian healthcare system structure

Do not invent Nigerian statistics, laws, or policies.

════════════════════════════════
SELF-REVIEW BEFORE RETURNING

Verify every item before returning:

Lecture note:
✓ No generic opening sentences
✓ No filler or repetition
✓ Mechanisms explained where relevant
✓ Nursing rationale included
✓ All "Topics to Cover" items addressed
✓ Content is accurate and exam-focused
✓ Headings fit this specific topic
✓ 4-8 sections present

MCQs:
✓ Q1 tests recall, Q2 tests application, Q3 tests judgment
✓ Each question has ONE clearly best answer
✓ No circular reasoning (symptom as both stem and answer option)
✓ All 4 options in same clinical category
✓ Scenarios have enough detail to justify correct answer
✓ Correct answer position varies across Q1/Q2/Q3
✓ Explanations address correct and incorrect options
✓ Character limits respected

JSON:
✓ Valid JSON structure
✓ No markdown or code fences
✓ No text outside the JSON object

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

def send_progress(done, total, recent_topics):
    percent   = round((done / total) * 100, 1) if total > 0 else 0
    remaining = total - done
    bar_filled = int(percent / 5)
    bar = "🟩" * bar_filled + "⬜" * (20 - bar_filled)

    recent_lines = "".join(f"  • {escape_md(t)}\n" for t in recent_topics)

    msg = (
        f"📊 *Revision Summary — Every 10 Topics*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📚 *Last 10 topics covered:*\n"
        f"{recent_lines}"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{bar}\n"
        f"✅ *{done}* done  •  ⏳ *{remaining}* remaining  •  *{percent}%*\n"
        f"Keep pushing — every topic counts! 💪"
    )
    tg("sendMessage", {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
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

    # Progress summary every 10 topics
    total_topics = curriculum_data["meta"].get("total_topics", 0)
    if total_topics > 0 and state["total_sent"] % 10 == 0:
        recent_ids = state["completed_topics"][-10:]
        id_to_title = {
            t["topic_id"]: t["title"]
            for c in courses
            for u in c["units"]
            for t in u["topics"]
        }
        recent_titles = [id_to_title.get(tid, tid) for tid in recent_ids]
        send_progress(state["total_sent"], total_topics, recent_titles)

    save_state()
    print(f"Done. Total sent: {state['total_sent']}")

if __name__ == "__main__":
    main()
