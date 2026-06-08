import os
import json
import requests
from datetime import datetime, date

# ─── Config from GitHub Secrets ───────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_KEY     = os.environ["GEMINI_API_KEY"]

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
)

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

        # Advance pointers for next run
        state["topic_pointers"][unit_id] = t_idx + 1
        state["course_pointer"] = (c_idx + 1) % total_courses

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

    prompt = f"""You are an expert nursing tutor preparing study material for a nursing student 
revising for the Final Qualifying Examination (FQE) in Nigeria.

Course: {course['course_name']}
Unit: {unit['unit_name']}
Topic: {topic['title']}
Topic Type: {topic_type}

Your task is to produce a JSON object with exactly this structure:

{{
  "lecture_note": {{
    "emoji": "<one relevant emoji>",
    "sections": [
      {{"heading": "<section heading>", "content": "<clear, concise explanation>"}}
    ]
  }},
  "polls": [
    {{
      "question": "<MCQ question>",
      "options": ["<option A>", "<option B>", "<option C>", "<option D>"],
      "correct_index": <0-3>,
      "explanation": "<why the correct answer is right, and why others are wrong — 2-3 sentences>"
    }},
    {{
      "question": "<MCQ question>",
      "options": ["<option A>", "<option B>", "<option C>", "<option D>"],
      "correct_index": <0-3>,
      "explanation": "<explanation>"
    }},
    {{
      "question": "<MCQ question>",
      "options": ["<option A>", "<option B>", "<option C>", "<option D>"],
      "correct_index": <0-3>,
      "explanation": "<explanation>"
    }}
  ]
}}

Rules:
- Lecture note sections must follow this structure for a {topic_type}: {structure}
- Keep each section content concise but complete (3-6 sentences max)
- All 3 poll questions must be different aspects of the topic
- Options must be plausible (not obviously wrong)
- correct_index is 0 for A, 1 for B, 2 for C, 3 for D
- Output ONLY valid JSON. No markdown, no backticks, no extra text.
"""

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4}
    }

    response = requests.post(GEMINI_URL, json=body, timeout=30)
    response.raise_for_status()
    raw = response.json()
    text = raw["candidates"][0]["content"]["parts"][0]["text"].strip()

    # Strip markdown code fences if Gemini adds them
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    return json.loads(text)

# ─── Send to Telegram ─────────────────────────────────────────────────────────
def tg(method, payload):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def send_lecture_note(course, unit, topic, content):
    note = content["lecture_note"]
    lines = []

    # Header
    lines.append(f"{note['emoji']} *{topic['title'].upper()}*")
    lines.append(f"📘 _{course['course_name']}_  •  _{unit['unit_name']}_")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    # Sections
    for section in note["sections"]:
        lines.append(f"\n*{section['heading']}*")
        lines.append(section["content"])

    lines.append("\n━━━━━━━━━━━━━━━━━━━━")
    lines.append("🧠 *Test yourself — 3 questions below\\!*")

    message = "\n".join(lines)

    tg("sendMessage", {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    })

def send_poll_with_spoiler(poll, index):
    options = poll["options"]
    correct_letter = ["A", "B", "C", "D"][poll["correct_index"]]
    explanation = poll["explanation"]

    # Send the poll
    tg("sendPoll", {
        "chat_id": TELEGRAM_CHAT_ID,
        "question": f"Q{index}: {poll['question']}",
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
