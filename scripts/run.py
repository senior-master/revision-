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
            # Course fully done, move to next
            state["course_pointer"] = (c_idx + 1) % total_courses
            attempts += 1
            continue

        unit = units[u_idx]
        unit_id = unit["unit_id"]
        topics = unit["topics"]

        t_idx = state["topic_pointers"].get(unit_id, 0)
        if t_idx >= len(topics):
            # Unit done, move to next unit
            state["unit_pointers"][course_id] = u_idx + 1
            state["topic_pointers"][unit_id] = 0
            attempts += 1
            continue

        topic = topics[t_idx]

        # Advance topic pointer only — stay on same course until it's done
        state["topic_pointers"][unit_id] = t_idx + 1

        return course, unit, topic

    return None, None, None  # All topics exhausted

# ─── Generate content with Gemini ─────────────────────────────────────────────
def generate_content(course, unit, topic):
    topic_type = topic["topic_type"]

    type_instructions = {
        "disease":   "Definition, Causes, Signs & Symptoms, Pathophysiology, Treatment, Nursing Interventions",
        "drug":      "Drug Class, Mechanism of Action, Indications, Side Effects, Nursing Considerations, Dosage Notes",
        "organ":     "Definition/Overview, Structure, Functions, Clinical Relevance for Nurses",
        "procedure": "Definition, Indications/Purpose, Step-by-step Process, Nursing Role, Possible Complications",
        "theory":    "Definition, Key Concepts, Explanation, Clinical/Nursing Relevance",
        "concept":   "Definition, Key Points, Practical Examples, Nursing Application",
    }

    structure = type_instructions.get(topic_type, type_instructions["concept"])

    prompt = f"""You are an expert Nigerian Nursing Tutor and Nursing & Midwifery Council CBT examiner.

Your task is to generate concise, exam-focused revision material for a student preparing for the Final Qualifying Examination (FQE).

Course: {course['course_name']}
Unit: {unit['unit_name']}
Topic: {topic['title']}
Topic Type: {topic_type}

The output MUST be a valid JSON object matching EXACTLY this schema:

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
      "correct_index": 0,
      "explanation": "<brief explanation>"
    }},
    {{
      "question": "<MCQ question>",
      "options": ["<A>", "<B>", "<C>", "<D>"],
      "correct_index": 0,
      "explanation": "<brief explanation>"
    }}
  ],
  "exam_trap": {{
    "mistake": "<common mistake students make on this topic>",
    "correction": "<the correct understanding>"
  }}
}}

========================
LECTURE NOTE RULES

Do NOT use fixed headings. Choose the most appropriate headings for the topic type. you are free to add yours if applicable.

Expected emphasis for topic type "{topic_type}":
{structure}

Typical heading examples by type:
- Disease: Overview, Causes/Risk Factors, Pathophysiology, Clinical Manifestations, Diagnosis, Treatment, Nursing Management, Prevention
- Drug: Drug Class, Mechanism of Action, Indications, Adverse Effects, Contraindications, Nursing Responsibilities, Patient Education
- Procedure: Purpose, Indications, Preparation, Steps, Complications, Nursing Responsibilities
- Organ: Overview, Structure, Functions, Clinical Relevance
- Theory: Overview, Key Concepts, Components/Stages, Relevance to Nursing
- Concept: Overview, Principles, Classification, Importance, Nursing Relevance

Use only headings/subheadings actually needed. You may use different headings if more appropriate.

Each section:
- 2-5 concise sentences
- High-yield exam facts only
- No motivational language, no filler

Prioritize: definitions, classifications, functions, causes, risk factors, signs/symptoms,
nursing responsibilities, nursing priorities, prevention, complications, patient education,
emergency management, clinical decision-making.

========================
MCQ RULES — 3 questions at different difficulty levels:

Q1: Direct recall of a high-yield fact
Q2: Application — short nursing/patient/community scenario
Q3: Higher-order — prioritization, nursing judgment, best action, complication recognition

Do NOT produce three recall questions.

========================
DISTRACTOR RULES

- Incorrect options must be plausible, same subject area
- No obviously wrong answers
- Correct answer should not be predictable by length or wording
- Randomize correct answer position across the 3 questions

========================
LIMITS

- Question: max 280 characters
- Each option: max 90 characters
- Explanation: max 180 characters
- correct_index: 0=A, 1=B, 2=C, 3=D

========================
EXAM TRAP RULES

- mistake: one common misconception or error students make about this topic in exams
- correction: the accurate understanding in one clear sentence
- This should be the single most exam-relevant trap for this topic

========================
OUTPUT RULES

Return ONLY valid JSON. No markdown, no code fences, no comments, no text outside the JSON.
"""

    # Retry up to 3 times with backoff for rate limit errors
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

            # Strip markdown code fences if model adds them
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            try:
                return json.loads(text)
            except json.JSONDecodeError as je:
                print(f"JSON parse error: {je}\nRaw text: {text[:300]}")
                if attempt < 2:
                    time.sleep(10)
                    continue
                raise

        except json.JSONDecodeError:
            raise
        except Exception as e:
            if "429" in str(e) and attempt < 2:
                wait = 30 * (attempt + 1)
                print(f"Rate limited. Waiting {wait}s before retry {attempt + 2}/3...")
                time.sleep(wait)
            else:
                raise

# ─── Send to Telegram ─────────────────────────────────────────────────────────
def tg(method, payload):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def escape_md(text):
    """Escape special Markdown v1 characters to prevent Telegram parse errors."""
    for ch in ['_', '*', '`', '[']:
        text = text.replace(ch, f"\\{ch}")
    return text

def send_lecture_note(course, unit, topic, content):
    note = content["lecture_note"]
    trap = content.get("exam_trap")
    lines = []

    # Header
    lines.append(f"{note['emoji']} *{topic['title'].upper()}*")
    lines.append(f"📘 _{escape_md(course['course_name'])}_  •  _{escape_md(unit['unit_name'])}_")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    # Sections
    for section in note["sections"]:
        lines.append(f"\n*{escape_md(section['heading'])}*")
        lines.append(escape_md(section["content"]))

    # Exam trap
    if trap:
        lines.append("\n━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ *COMMON CONFUSION*")
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
    # Telegram poll options: max 100 chars each, question max 300 chars
    question = poll["question"][:300]
    options  = [opt[:100] for opt in poll["options"]]
    explanation = poll["explanation"][:200]

    tg("sendPoll", {
        "chat_id": TELEGRAM_CHAT_ID,
        "question": f"Q{index}: {question}"[:300],
        "options": options,
        "type": "quiz",
        "correct_option_id": poll["correct_index"],
        "explanation": explanation,
        "is_anonymous": False
    })

def send_progress_footer(course, unit, topic):
    total_topics = curriculum_data["meta"]["total_topics"]
    done = state["total_sent"]
    percent = round((done / total_topics) * 100, 1) if total_topics > 0 else 0

    target = date(2025, 9, 30)
    days_left = (target - date.today()).days

    msg = (
        f"\n📊 *Progress*: {done}/{total_topics} topics ({percent}%)\n"
        f"📅 *Days left until Sep 30*: {days_left}\n"
        f"✅ Keep going — you've got this\\! 💪"
    )
    tg("sendMessage", {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    })

# ─── Save state back to file ──────────────────────────────────────────────────
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

    print(f"Generating: [{course['course_id']}] {topic['title']}")

    content = generate_content(course, unit, topic)

    send_lecture_note(course, unit, topic, content)

    for i, poll in enumerate(content["polls"], 1):
        send_poll_with_spoiler(poll, i)

    state["total_sent"] = state.get("total_sent", 0) + 1
    state["completed_topics"].append(topic["topic_id"])

    send_progress_footer(course, unit, topic)
    save_state()

    print(f"Done. Total sent: {state['total_sent']}")

if __name__ == "__main__":
    main()
