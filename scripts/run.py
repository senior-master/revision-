import os
import json
import time
import requests
from datetime import datetime, date

# ─── Config from GitHub Secrets ───────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
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
    type_guidance = {
        "disease": " may need: Overview, Causes/Risk Factors, Pathophysiology (mechanism clearly explained stepwise), Clinical Manifestations (early vs late), Diagnosis (labs + clinical criteria), Treatment (medical + surgical if applicable), Nursing Management (prioritized interventions, rationales where needed), Prevention (primary/secondary/tertiary), Complications (acute vs chronic). Ensure clinical clarity and exam-focused phrasing.",
        "drug": "may need: Drug Class, Mechanism of Action (stepwise receptor/biochemical effect), Indications (primary + off-label if relevant), Adverse Effects (common vs severe), Contraindications, Nursing Responsibilities (before/during/after administration), Patient Education (clear, practical instructions), Dosage Notes (standard ranges if known, otherwise general guidance).",
        "organ": "may need: Overview, Gross Structure, Microscopic Anatomy (if applicable), Functions (physiological roles clearly separated), Physiology (how it works in systems), Clinical Relevance (what goes wrong in disease), Nursing Considerations (assessment + monitoring focus).",
        "procedure": "may need: Purpose/Indications, Equipment Needed (complete checklist style), Preparation (patient + environment), Steps (sequential, numbered, clear), Post-procedure Care (monitoring + safety), Complications (what can go wrong + signs), Nursing Responsibilities (critical thinking + prevention focus).",
        "theory": "may need: Overview, Author/Origin, Key Concepts (clearly defined), Components/Stages (structured breakdown), Principles (core rules or assumptions), Application to Nursing Practice (real clinical use cases), Limitations (weaknesses or criticisms).",
        "concept": "may need: Definition (precise), Principles, Classification/Types (if applicable), Importance, Nursing Relevance (clinical reasoning connection), Clinical Application (how it appears in real patient care).",
        "physiology":"may need: Overview, Mechanism/Process (step-by-step biological process), Regulatory Factors (hormonal/neural/chemical control), Clinical Significance (what abnormalities imply), Nursing Implications (assessment, monitoring, intervention relevance).",
        "diagnostic":"may need: Purpose, Principle, Procedure (clear stepwise explanation), Normal Values/Findings, Abnormal Findings (interpretation meaning), Nursing Responsibilities (before/during/after test care).",
        "diagnostic_tool": " may need: Overview, Principle (how tool works), Indications, Procedure (stepwise), Findings Interpretation (normal vs abnormal meaning), Nursing Responsibilities (safety + preparation + monitoring).",
        "equipment": "may need: Definition/Overview, Components (parts clearly listed), Indications (when used), How to Use (stepwise operational guide), Safety Considerations, Nursing Responsibilities (maintenance + patient safety).",
        "drug_class": "may need: Overview, Mechanism of Action (shared class mechanism), Examples (common drugs), Indications, Adverse Effects (class effects), Nursing Considerations (monitoring patterns + safety rules).",
        "healthcare_system": " may need: Definition, Structure (levels clearly separated), Functions, Key Components, Nursing Role (system-level responsibilities), Challenges (real-world constraints).",
        "communication_counselling": "may need: Definition, Principles, Types/Techniques (clearly separated), Barriers, Nursing Application (clinical scenarios), Therapeutic Use (patient outcomes + practice relevance).",
        "academic_professional_skill": "may need: Definition, Importance, Key Components, Steps/Process (actionable sequence), Nursing Application (how it is used in practice).",
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
        coverage_str = "\n".join(f" - {item}" for item in coverage_raw)
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
        
    prompt = f"""You are an expert Nigerian Nursing Tutor and Nursing & Midwifery Council (NMC) CBT examiner. Your task is to generate detailed, exam-focused revision material for a student preparing for the Final Qualifying Examination (FQE). {context_block} Suggested Topic Type: {topic_type} ════════════════════════════════ OUTPUT SCHEMA Return ONLY this JSON object — no markdown, no code fences, no text outside JSON: {{ "lecture_note": {{ "emoji": "", "sections": [ {{"heading": "", "content": ""}} ] }}, "polls": [ {{ "question": "", "options": ["", "", "", ""], "correct_index": 0, "explanation": "" }}, {{ "question": "", "options": ["", "", "", ""], "correct_index": 1, "explanation": "" }}, {{ "question": "", "options": ["", "", "", ""], "correct_index": 2, "explanation": "" }} ], "exam_trap": {{ "mistake": "", "correction": "" }} }} ════════════════════════════════ LECTURE NOTE RULES The "Suggested Topic Type" is GUIDANCE ONLY. If the topic does not fit the suggested type, use your judgment and generate the most appropriate headings. You are a tutor — structure the note the way a knowledgeable nurse would teach it. Suggested heading structure for type "{topic_type}": {guidance} General rules: - The suggested headings for your topic type are a CHECKLIST, not a template - 
Don't Strictly use mentioned suggested heading name(you can change name or use yours), you can decide independently., -EACH suggested heading, ask yourself: "Does this heading actually apply to this specific topic?" - If YES → include it - If NO → discard it completely, do not force it - If a heading would be empty or irrelevant for this topic, skip it - If an important heading is missing from the suggestions, add it yourself - The final note must feel naturally structured for THIS topic, not copy-pasted from a template - Each section: 3-6 concise sentences of high-yield exam content Make at least 4 or more sections for The topic - No filler, no motivational language, no repetition - If "Topics to Cover" is provided above, ensure EVERY item listed is addressed somewhere in the note - If the curriculum path is provided, use it to understand the topic's context and scope Priority content for FQE: Definitions • Classifications • Pathophysiology • Functions • Causes • Risk factors • Signs & symptoms • Nursing responsibilities • Nursing priorities • Complications • Prevention • Patient education • Emergency management • Clinical decision-making • Normal vs abnormal values • Drug calculations • Legal/ethical implications, Etc. ════════════════════════════════ MCQ RULES Exactly 3 questions — strictly different difficulty levels: Q1 — Direct recall: test a key definition, classification, or fact Q2 — Application: short nursing/patient/community scenario requiring knowledge application Q3 — Higher-order: Nursing judgment, best action, complication recognition, prioritization, and ETC. ════════════════════════════════ DISTRACTOR RULES - All 4 options must belong to the same subject area - Incorrect options must be plausible — a student who has not studied could easily pick them - Do NOT use obviously wrong options - Correct answer position must vary across Q1, Q2, Q3 (do not always put it at index 0) - Correct answer should not stand out by length or phrasing ════════════════════════════════ CHARACTER LIMITS Question: max 280 characters Each option: max 90 characters Explanation: max 180 characters Dont send too little or just 1 line Explanation ════════════════════════════════ EXAM TRAP The single most likely mistake a student makes on this topic in a CBT exam. State the mistake clearly. Then give the accurate correction. This is often more memorable than an extra paragraph of notes. ════════════════════════════════ DEPTH RULES Do not produce shallow or surface-level notes. For every section, go beyond the basic definition: - Explain the WHY behind every fact (why does it happen, why does it matter) - Explain the HOW (how does the mechanism work, how does the nurse respond) - Include specific values, numbers, classifications where relevant - Include pathophysiology where applicable, not just signs and symptoms - For nursing topics, explain the reasoning behind each nursing action - A student reading your note should understand the topic, not just memorise it - Think like a lecturer who wants students to truly understand, not just pass - Do your work smart ════════════════════════════════ SELF-REVIEW — DO THIS BEFORE RETURNING OUTPUT You MUST review both the lecture note and the MCQs before returning the final JSON. LECTURE NOTE REVIEW: - Is every section substantive? (minimum 3 solid sentences of real content) - Did I explain the WHY and HOW, not just state facts? - Are there any vague or filler sentences? If yes, replace them with specific facts - Did I cover all items listed under "Topics to Cover" if provided? - Is the content accurate and relevant to Nigerian nursing FQE? - Would a student who reads this note be able to answer exam questions on this topic? - Any other issue with the content? MCQ REVIEW — check each question: - Is the question stem logically consistent with all options? - Is the correct answer actually the answer to the question asked? - Am I using a symptom, sign, or finding as both the question stem AND an answer option? (circular reasoning — fix it) - Are all 4 options from the same subject area and equally plausible? - Does the scenario in Q2 reflect a realistic clinical/community situation? - Does Q3 genuinely test higher-order thinking, not just recall? - Is the correct answer position varied across Q1, Q2, Q3? - Would a well-prepared student find each question fair and unambiguous? -Any other issue found in the content? -Fix ALL issues and logical problems found before returning. -Only return the final corrected JSON. """
    
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
    lines.append(f"📘 _{escape_md(course['course_name'])}_ • _{escape_md(unit['unit_name'])}_")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    
    # Sections
    for section in note["sections"]:
        lines.append(f"\n*{escape_md(section['heading'])}*")
        lines.append(escape_md(section["content"]))
        
    # Exam trap
    if trap:
        lines.append("\n━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ *Confused?*")
        lines.append(f"❌ {escape_md(trap['mistake'])}")
        lines.append(f"✅ {escape_md(trap['correction'])}")
        
    lines.append("\n━━━━━━━━━━━━━━━━━━━━")
    lines.append("🧠 *Test yourself — 3 questions below!*")
    
    message = "\n".join(lines)
    tg("sendMessage", {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    })

def send_poll_with_spoiler(poll, index):
    question = poll["question"][:280]
    options = [opt[:90] for opt in poll["options"]]
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
