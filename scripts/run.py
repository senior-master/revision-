import os
import json
import time
import random
import urllib.request
import urllib.error
import requests
from datetime import datetime

# ─── Config from GitHub Secrets ───────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

# ─── Gemini config ────────────────────────────────────────────────────────────
MODEL_NAME = "gemini-3.5-flash-lite"


_API_KEYS = None
_CURRENT_KEY_INDEX = 0

# ─── Emoji pool ───────────────────────────────────────────────────────────────
ALLOWED_EMOJIS = [
    "😀","😃","😄","😁","😆","😅","🤣","😂","🙂","🙃","😉","😊","😇",
    "🥰","😍","🤩","😘","😗","☺","😚","😋","😛","🤑","🤗","🤭","🤫",
    "🤔","🤨","🙄","😏","😒","🤥","😪","😴","😷","🤒","🤕","🤮","🤧",
    "🥶","🤓","😎","🥳","🤠","🤯","😲","😮","😟","🥺","😰","😢","😭",
    "😫","🥱","😤","😡","🤬","😈","👺","👹","🤡","☠","💀","👻","👽",
    "🙈","🙉","🙊","💘","💝","💖","💗","💞","💕","💟","❣","💔","❤",
    "🧡","💛","💚","💙","💜","🤎","🖤","🤍","💯","💥","💫","👋","🤚",
    "🖐","✋","🖖","👌","🤏","✌","🤞","🤟","🤘","🤙","👈","👉","👆",
    "🖕","👇","☝️","👍","👎","✊","👊","🤛","🤜","👏","🙌","👐","🤲",
    "🤝","🙏","✍","👀","🧠","💃","🥇","🏅","🏆","🎉","🎊","🧨","🎭",
    "🏁","🚩","🇳🇬"
]


def _load_api_keys():
    multi = os.environ.get("GEMINI_API_KEYS", "")
    keys = [k.strip() for k in multi.split(",") if k.strip()]
    if not keys:
        single = os.environ.get("GEMINI_API_KEY", "").strip()
        if single:
            keys = [single]
    if not keys:
        raise RuntimeError(
            "No Gemini API key(s) found. Set GEMINI_API_KEYS (comma-separated) "
            "or GEMINI_API_KEY."
        )
    return keys


def _get_keys():
    global _API_KEYS
    if _API_KEYS is None:
        _API_KEYS = _load_api_keys()
    return _API_KEYS


def _request_once(system_prompt, user_prompt):
    global _CURRENT_KEY_INDEX
    keys = _get_keys()

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }
    data = json.dumps(payload).encode("utf-8")

    last_error_text = None
    attempts = 0
    start_index = _CURRENT_KEY_INDEX
    resp_body = None

    while attempts < len(keys):
        key_index = (start_index + attempts) % len(keys)
        api_key = keys[key_index]
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{MODEL_NAME}:generateContent?key={api_key}"
        )
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                resp_body = json.loads(resp.read().decode("utf-8"))
            _CURRENT_KEY_INDEX = key_index
            break
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            is_quota_error = e.code == 429
            if not is_quota_error:
                try:
                    status = json.loads(body_text).get("error", {}).get("status", "")
                    is_quota_error = status == "RESOURCE_EXHAUSTED"
                except Exception:
                    pass
            if is_quota_error:
                print(f"⚠️  Key #{key_index+1}/{len(keys)} hit quota. Trying next key...")
                last_error_text = body_text
                attempts += 1
                continue
            raise RuntimeError(f"Gemini API HTTP {e.code}: {body_text[:500]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e}")
    else:
        raise RuntimeError(
            f"All {len(keys)} Gemini key(s) hit quota. Last error: {last_error_text}"
        )

    try:
        return resp_body["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError):
        raise ValueError(f"Unexpected Gemini response: {json.dumps(resp_body)[:500]}")


def call_gemini(system_prompt, user_prompt, _is_retry=False):
    raw_text = _request_once(system_prompt, user_prompt)
    try:
        return json.loads(raw_text, strict=False)
    except json.JSONDecodeError as e:
        if not _is_retry:
            print("⚠️  Malformed JSON, retrying once...")
            return call_gemini(system_prompt, user_prompt, _is_retry=True)
        raise ValueError(f"Invalid JSON after retry: {e}\nRaw: {raw_text[:500]}")


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

TYPE_HINTS = {
    "disease":        "Key examinable areas: aetiology, pathophysiology, clinical features, diagnosis, medical/nursing management, complications, prevention.",
    "drug":           "Key examinable areas: drug class, mechanism of action, indications, adverse effects, contraindications, nursing responsibilities, patient education.",
    "drug_class":     "Key examinable areas: shared mechanism, class examples, indications, class adverse effects, nursing monitoring patterns.",
    "organ":          "Key examinable areas: structure, location, functions, physiological roles, clinical relevance, nursing assessment focus.",
    "physiology":     "Key examinable areas: step-by-step mechanism, regulatory factors, normal values, clinical significance of abnormalities, nursing implications.",
    "procedure":      "Key examinable areas: purpose, indications, equipment, preparation, steps, post-procedure care, complications, nursing responsibilities.",
    "diagnostic":     "Key examinable areas: purpose, principle, normal values, abnormal findings and their meaning, nursing responsibilities before/during/after.",
    "diagnostic_tool":"Key examinable areas: principle of operation, indications, how to use, findings interpretation, nursing responsibilities.",
    "equipment":      "Key examinable areas: components, indications, correct usage, safety considerations, nursing responsibilities.",
    "concept":        "Key examinable areas: definition, principles, classification, importance, nursing application, clinical or legal relevance.",
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


# ─── Randomize poll options ───────────────────────────────────────────────────
def randomize_poll(poll):
    options = poll["options"]
    answer = poll["answer"].strip()

    if len(options) != 4:
        raise ValueError(f"Poll must contain exactly 4 options: {poll}")

    normalized_options = [str(option).strip() for option in options]

    matching_indexes = [
        i for i, option in enumerate(normalized_options)
        if option == answer
    ]

    if len(matching_indexes) != 1:
        raise ValueError(
            f"Could not uniquely match answer '{answer}' "
            f"to options: {normalized_options}"
        )

    correct_option = normalized_options[matching_indexes[0]]

    # Give every option a different randomly selected emoji.
    emojis = random.sample(ALLOWED_EMOJIS, 4)

    option_pairs = list(zip(normalized_options, emojis))

    # Shuffle option position independently of Gemini.
    random.shuffle(option_pairs)

    poll["options"] = [
        f"{emoji}{option}"
        for option, emoji in option_pairs
    ]

    for index, (option, emoji) in enumerate(option_pairs):
        if option == correct_option:
            poll["correct_index"] = index
            break

    del poll["answer"]

    return poll


# ─── Generate content ─────────────────────────────────────────────────────────
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

    system_prompt = """You are an expert Nurse Educator.

Your task is to generate professional, exam-focused nursing revision material. don't mention exam in your content though.

OUTPUT FORMAT — return ONLY valid JSON:
{
  "lecture_note": {
    "emoji": "<one relevant emoji>",
    "sections": [
      {"heading": "<heading>", "content": "<content>"}
    ]
  },
  "polls": [
    {
      "question": "<Q>",
      "options": ["<option 1>","<option 2>","<option 3>","<option 4>"],
      "answer": "<exact text of the correct option>",
      "explanation": "<explanation>"
    },
    {
      "question": "<Q>",
      "options": ["<option 1>","<option 2>","<option 3>","<option 4>"],
      "answer": "<exact text of the correct option>",
      "explanation": "<explanation>"
    },
    {
      "question": "<Q>",
      "options": ["<option 1>","<option 2>","<option 3>","<option 4>"],
      "answer": "<exact text of the correct option>",
      "explanation": "<explanation>"
    }
  ]
}

IMPORTANT:
- Do NOT add emojis to options.
- Do NOT label options A, B, C, or D.
- Return only the actual option text.
- The "answer" field must contain the exact text of the correct option.
- Do NOT return a correct_index.
- Python will handle option ordering, emoji selection, emoji assignment, and correct answer position."""

    user_prompt = f"""Generate revision material for:

{context_block}

════════════════════════════════
BEFORE WRITING — THINK FIRST (do not include in output):

What is the best structure to teach THIS topic?

════════════════════════════════
HEADING RULES
- Choose headings freely — no fixed template
- Use only headings that genuinely help explain THIS topic
- Dont include summary or conclusion headings at end as the whole content is for revision purpose.
- Provide 3 to 5 headings depending on topic depth. but prioritize based on relavance.
════════════════════════════════
CONTENT RULES
Write like a skilled nurse educator teaching 100 level students.
Use simple understandabele English not hard one o.

STRICTLY BANNED — never write anything like:
- "[Topic] is an important aspect of nursing care."
- "Learning about [topic] is crucial for nurses..."
- "Understanding [topic] helps nurses improve patient outcomes."
- "In conclusion, [topic] is a critical part of nursing."
- "Nurses should be sensitive to patient needs..."
- "[Topic] plays a significant role in maintaining health."
- Any conclusion section
- Any motivational or filler statements
- Vague nursing statements without specific clinical detail
- No filler
- No filler

Bad: "Blood is a vital fluid that circulates through the body."
Good: "Blood is a viscous fluid connective tissue comprises plasma (~55%) and formed elements (~45%). Plasma transports nutrients, hormones, clotting factors, and waste. Formed elements include erythrocytes (O2 transport), leukocytes (immunity), and thrombocytes (haemostasis)."

════════════════════════════════
DEPTH RULES
- Explain mechanisms step by step
- Include specific values, classifications, stages, percentages, etc
- Explain nursing rationale — not just what, but why
- Do not invent mechanisms or values
- Do not invent mechanisms or values

════════════════════════════════
STRUCTURE
- Minimum 3 sections, maximum 5
- Each section: 3-5 substantive sentences
- Each section should be max 60 words
- No section opens by restating its heading
- If "Topics to Cover" listed above — address EVERY item

════════════════════════════════
══════════════════════
MCQ RULES — exactly 3 questions

OPTION RULES:
- Exactly 4 options per question.
- Return ONLY the option text.
- Do NOT add emojis.
- Do NOT label options A, B, C, or D.
- All 4 options must be in the same clinical category (causes with causes, actions with actions).
- Incorrect options must be plausible — common mistakes or partial alternatives.
- Correct answer must not stand out by length or phrasing.
- The "answer" field must contain the exact text of the correct option.
- Do NOT provide a correct_index.
- Do NOT determine or suggest the position of the correct answer.
- Python will randomly shuffle the options and assign emojis after generation.

LIMITS:
- Question: 5-10 words
- Each option: max 7 words
- Explanation: max 120 characters — explain why correct AND why others are wrong

════════════════════════════════
SELF-REVIEW BEFORE RETURNING:
✓ No banned filler sentences anywhere
✓ Every sentence states a specific fact, action, or mechanism
✓ No conclusion section
✓ 3-5 sections present, each substantive
✓ All "Topics to Cover" items addressed
✓ One clearly best answer per question
✓ The answer exactly matches one option
✓ All 4 options in same category
✓ No A, B, C, or D labels
✓ No emojis in options
✓ No correct_index
✓ Valid JSON, no markdown, no text outside JSON"""

    result = call_gemini(system_prompt, user_prompt)

    # Validate structure
    if "lecture_note" not in result or "polls" not in result:
        raise ValueError("Missing lecture_note or polls in response")
    if len(result.get("polls", [])) < 3:
        raise ValueError(f"Only {len(result.get('polls', []))} polls returned")
    if len(result["lecture_note"].get("sections", [])) < 2:
        raise ValueError("Too few sections in lecture note")

    # Python handles all option randomization and emoji assignment.
    result["polls"] = [
        randomize_poll(poll)
        for poll in result["polls"][:3]
    ]

    return result


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