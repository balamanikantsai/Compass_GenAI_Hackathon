from flask import render_template, url_for, flash, redirect, request, jsonify, current_app
from app.career_advisor import bp
from flask_login import current_user, login_required
import google.generativeai as genai
import os
from app import db
from app.models import CareerPlan, DailyTask, ChatSession, ChatMessage
from datetime import datetime
import re
import json
from PyPDF2 import PdfReader

# Configure Google Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
    except Exception as e:
        print(f"Error initializing Gemini model '{GEMINI_MODEL}': {e}")
        model = None
else:
    print("GEMINI_API_KEY not found. AI features will be limited.")
    model = None

def _enforce_single_question(text: str) -> str:
    try:
        if not text:
            return text
        used = False
        out = []
        buf = []
        for ch in text:
            if ch == '?':
                if not used:
                    used = True
                    buf.append('?')
                else:
                    buf.append('.')
            else:
                buf.append(ch)
        out = ''.join(buf)
        return out
    except Exception:
        return text


def get_ai_response(user_input, user_profile, chat_session):
    if not model:
        return "AI features are not configured. Please set GEMINI_API_KEY."

    # Build conversation history for memory (all previous messages in this session)
    history_lines = []
    try:
        if chat_session and getattr(chat_session, 'id', None):
            prior = ChatMessage.query.filter_by(session_id=chat_session.id).order_by(ChatMessage.timestamp.asc()).all()
            for m in prior:
                role = 'User' if m.sender == 'user' else 'AI'
                history_lines.append(f"{role}: {m.content}")
    except Exception as e:
        # If history fetch fails, continue without
        print('Warning: failed to load chat history:', e)

    # System/style prompt with strict brevity and behavior rules
    style_rules = (
        "You are an AI career advisor and mentor. Be clear, friendly, and encouraging—like a helpful guide. "
        "Respond concisely in plain text. Keep replies less than 5 lines unless a plan overview truly needs more. "
        "Prefer short sentences and tight bullet points. Avoid code blocks unless explicitly requested.\n\n"
        "Behavior & goals:\n"
        "- Greet warmly and set a collaborative, motivating tone.\n"
        "- Detect the user's language from their latest message and reply in that language where feasible.\n"
        "- Quickly understand the user's experience level and context (one concise question at a time only if essential). Do NOT ask the user to choose the number of days or content formats.\n"
        "- Propose an appropriate plan duration yourself (based on breadth, depth, and typical time to learn), then explain the high-level roadmap in skills/modules (e.g., for ML: Supervised/Unsupervised/Semi-supervised, MLOps & Deployment, Current Trends), not micro-topics.\n"
        "- Recommend specific top-quality resources (courses and books) by name/platform/author; no generic 'YouTube or books?' questions. 1–2 curated picks per module is enough.\n"
        "- When the user seems ready, briefly summarize their context and propose scheduling this plan. If they confirm, say you're creating it now and it will appear in the Tracker. Do not mention any buttons.\n"
        "- After progress begins, suggest resume improvements where impactful (brief).\n"
        "- Ask at most one question per reply."
    )

    profile_bits = []
    if user_profile:
        if user_profile.get('name'):
            profile_bits.append(f"Name: {user_profile.get('name')}")
        if user_profile.get('user_type'):
            profile_bits.append(f"User Type: {user_profile.get('user_type')}")
        if user_profile.get('interests'):
            profile_bits.append(f"Interests: {user_profile.get('interests')}")

    conversation_block = "\n".join(history_lines) if history_lines else "(No prior messages)"

    prompt = (
        f"{style_rules}\n\n" +
        (f"User Profile: {'; '.join(profile_bits)}\n\n" if profile_bits else "") +
        f"Conversation so far:\n{conversation_block}\n\n" +
        f"Current user message: {user_input}\n\n" +
        "Your reply (<= 5 lines unless a domain explanation is needed):"
    )

    try:
        generation_config = {
            "max_output_tokens": 220,
            "temperature": 0.6,
            "top_p": 0.9,
            "top_k": 40,
        }
        try:
            response = model.generate_content(prompt, generation_config=generation_config)
        except TypeError:
            response = model.generate_content(prompt)
        text = (getattr(response, 'text', None) or '').strip()
        text = _enforce_single_question(text)
        return text
    except Exception as e:
        print(f"Error generating content from Gemini: {e}")
        return "I apologize, but I'm having trouble connecting to the AI at the moment. Please try again later."


def _user_consented_to_plan(user_input: str) -> bool:
    if not user_input:
        return False
    s = user_input.lower()
    negatives = ["don't", "do not", "not now", "later", "no", "cancel", "stop", "wait"]
    if any(n in s for n in negatives):
        return False
    affirmatives = [
        "yes", "yep", "yeah", "ok", "okay", "sure", "please", "go ahead", "generate", "create", "proceed", "do it",
        "start the plan", "make the plan", "sounds good", "looks good", "let's do it", "let us do it", "let's start", "start now",
        "i agree", "agree", "approved", "confirm", "confirmed", "let's proceed", "proceed with plan", "ready"
    ]
    return any(a in s for a in affirmatives)


def _extract_goal_days_from_history(history_text: str, user_profile: dict | None) -> tuple[str | None, int | None]:
    if not model:
        return None, None
    prompt = (
        "From the following conversation, infer the user's primary career goal and an optional desired duration in days if mentioned. "
        "Return ONLY JSON: {\n  \"goal\": string,\n  \"days\": number|null\n}. If duration is not stated, use null for days.\n\n"
        f"Conversation:\n{history_text}\n\n"
        + (f"User Profile: {json.dumps(user_profile or {}, ensure_ascii=False)}\n" if user_profile else "")
    )
    try:
        try:
            resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        except TypeError:
            resp = model.generate_content(prompt)
        raw = (getattr(resp, 'text', None) or '').strip()
        if raw.startswith('```'):
            raw = raw.strip('`').strip()
            if raw.lower().startswith('json'):
                raw = raw[4:].strip()
        data = json.loads(raw)
        goal = (data.get('goal') or '').strip() or None
        days = data.get('days')
        if isinstance(days, str):
            try:
                days = int(days)
            except Exception:
                days = None
        if isinstance(days, (int, float)):
            try:
                days = int(days)
                days = max(1, min(60, days))
            except Exception:
                days = None
        else:
            days = None
        return goal, days
    except Exception:
        return None, None

def generate_career_plan_with_ai(user_profile, career_goal, days: int | None = None):
    if not model:
        return None
    user_profile = user_profile or {}

    duration_clause = (
        f"Create a personalized learning plan with exactly {days} days. " if days else
        "Create a personalized learning plan with an appropriate number of days based on the user's current experience and the goal. "
    )

    base_prompt = f"""
As an AI career advisor, {duration_clause}Goal: '{career_goal}'.
Include day-wise tasks and relevant resources (links to credible articles, courses, or books).
Consider the user's profile:
Name: {user_profile.get('name', 'N/A')}, User Type: {user_profile.get('user_type', 'N/A')}, Interests: {user_profile.get('interests', 'N/A')}.

Output format requirements (STRICT):
- Return ONLY application/json with a top-level JSON array.
- Do NOT include markdown fences, labels, or any prose.
- Each array item MUST be an object with EXACT keys: 'day' (1-based integer), 'task' (string), 'resources' (array of strings).
- 'day' increments sequentially starting at 1; no gaps or duplicates.
- Use real, accessible resource URLs or clear source names.
     - Frame tasks as skill modules and outcomes (e.g., for ML: Supervised/Unsupervised/Semi-supervised learning, MLOps & Deployment, Current Trends), not micro-algorithm lists. 
     - Recommend specific top-quality resources (courses and books) by platform/author; do not ask the user to choose formats or number of days.
"""
    if days:
        base_prompt += f"\nThe top-level array MUST contain exactly {days} items (one per day)."

    def _call_model(prompt_text: str):
        gen_cfg = {"max_output_tokens": 1400, "response_mime_type": "application/json"}
        try:
            resp = model.generate_content(prompt_text, generation_config=gen_cfg)
        except TypeError:
            resp = model.generate_content(prompt_text)
        raw_text = (getattr(resp, 'text', None) or '').strip()
        if not raw_text and getattr(resp, 'candidates', None):
            try:
                parts = []
                for cand in resp.candidates:
                    for part in getattr(cand.content, 'parts', []) or []:
                        if hasattr(part, 'text') and part.text:
                            parts.append(part.text)
                raw_text = "\n".join(parts).strip()
            except Exception:
                pass
        return raw_text

    def _extract_json_array(text: str):
        if not text:
            return None
        t = text.strip()
        # Fenced JSON block
        if t.startswith('```'):
            try:
                inner = t.strip('`').strip()
                if inner.lower().startswith('json'):
                    inner = inner[4:].strip()
                return json.loads(inner)
            except Exception:
                pass
        # Try to extract a balanced top-level JSON array
        def find_balanced_array(s: str):
            depth = 0
            in_str = False
            esc = False
            start_idx = -1
            for i, ch in enumerate(s):
                if in_str:
                    if esc:
                        esc = False
                    elif ch == '\\':
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                else:
                    if ch == '"':
                        in_str = True
                        continue
                    if ch == '[':
                        if depth == 0:
                            start_idx = i
                        depth += 1
                    elif ch == ']':
                        depth -= 1
                        if depth == 0 and start_idx != -1:
                            return s[start_idx:i+1]
            return None

        candidate = find_balanced_array(t)
        if candidate:
            try:
                return json.loads(candidate)
            except Exception:
                # Attempt to remove trailing commas
                try:
                    candidate2 = re.sub(r',\s*([\]}])', r'\1', candidate)
                    return json.loads(candidate2)
                except Exception:
                    pass
        # Fallback: parse partial array of complete objects if output is truncated
        def _parse_partial_array(s: str):
            start = s.find('[')
            if start == -1:
                return None
            i = start
            n = len(s)
            in_str = False
            esc = False
            depth_brace = 0
            obj_start = -1
            items = []
            while i < n:
                ch = s[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == '\\':
                        esc = True
                    elif ch == '"':
                        in_str = False
                else:
                    if ch == '"':
                        in_str = True
                    elif ch == '{':
                        if depth_brace == 0:
                            obj_start = i
                        depth_brace += 1
                    elif ch == '}':
                        if depth_brace > 0:
                            depth_brace -= 1
                            if depth_brace == 0 and obj_start != -1:
                                frag = s[obj_start:i+1]
                                try:
                                    obj = json.loads(frag)
                                    items.append(obj)
                                except Exception:
                                    pass
                                obj_start = -1
                i += 1
            return items if items else None

        partial_items = _parse_partial_array(t)
        if partial_items:
            return partial_items
        # If it is a dict with a plan field
        try:
            obj = json.loads(t)
            if isinstance(obj, dict):
                for key in ('plan', 'days', 'schedule'):
                    if key in obj and isinstance(obj[key], list):
                        return obj[key]
                # Some models return mapping day->entry
                if 'days' in obj and isinstance(obj['days'], dict):
                    seq = []
                    for k in sorted(obj['days'].keys(), key=lambda x: int(re.sub(r'[^0-9]', '', x) or 0)):
                        seq.append(obj['days'][k])
                    return seq
        except Exception:
            pass
        return None

    try:
        prompt = base_prompt
        raw = _call_model(prompt)

        data = None
        # Direct parse (array)
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                data = parsed
            elif isinstance(parsed, dict):
                for key in ('plan', 'days', 'schedule'):
                    if key in parsed and isinstance(parsed[key], list):
                        data = parsed[key]
                        break
        except Exception:
            pass
        # Fallback extraction
        if data is None:
            data = _extract_json_array(raw)

        if (not isinstance(data, list)) or (not data):
            # Retry once with stricter wording if we have a target days count
            if days:
                retry_prompt = base_prompt + " Ensure the JSON array has exactly " + str(days) + " items. No comments, no extra keys."
                raw = _call_model(retry_prompt)
                data = None
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        data = parsed
                except Exception:
                    pass
                if data is None:
                    data = _extract_json_array(raw)
            if not isinstance(data, list) or not data:
                raise ValueError('Model did not return a valid JSON array for the plan')

        # Normalize items (accept common key variants)
        def _normalize_list(items):
            out = []
            for item in items or []:
                try:
                    if not isinstance(item, dict):
                        continue
                    lower_map = {str(k).strip().lower(): v for k, v in item.items()}
                    # day
                    day_val = lower_map.get('day') or lower_map.get('day_number') or lower_map.get('daynum') or lower_map.get('index') or lower_map.get('step')
                    if isinstance(day_val, str):
                        m = re.search(r"\d+", day_val)
                        day = int(m.group()) if m else None
                    elif isinstance(day_val, (int, float)):
                        day = int(day_val)
                    else:
                        day = None
                    # task / description
                    task_val = (
                        lower_map.get('task') or lower_map.get('tasks') or lower_map.get('activity') or lower_map.get('activities') or
                        lower_map.get('objective') or lower_map.get('focus') or lower_map.get('description') or lower_map.get('summary')
                    )
                    if isinstance(task_val, list):
                        task = "; ".join([str(x).strip() for x in task_val if x])
                    else:
                        task = (str(task_val).strip() if task_val else '')
                    # resources
                    res_val = (
                        lower_map.get('resources') or lower_map.get('links') or lower_map.get('materials') or
                        lower_map.get('references') or lower_map.get('sources') or lower_map.get('urls') or lower_map.get('resource_links')
                    )
                    resources = res_val if isinstance(res_val, list) else ([str(res_val)] if res_val else [])
                    if not isinstance(resources, list):
                        resources = [str(resources)] if resources else []
                    resources = [str(r).strip() for r in resources if r]
                    if day is None:
                        day = len(out) + 1
                    if task:
                        out.append({'day': day, 'task': task, 'resources': resources})
                except Exception:
                    continue
            return out

        normalized = _normalize_list(data)
        # If exact days requested, enforce count by trimming or re-numbering
        if days:
            # Deduplicate by day number and ensure sequential numbering starting at 1
            dedup = {}
            for it in normalized:
                if it['day'] not in dedup:
                    dedup[it['day']] = it
            normalized = [dedup[d] for d in sorted(dedup.keys())]
            for idx, it in enumerate(normalized, start=1):
                it['day'] = idx
            if len(normalized) > days:
                normalized = normalized[:days]
            # If we still have fewer items than requested, try to fetch the missing tail (once)
            if len(normalized) < days:
                start_day = len(normalized) + 1
                cont_prompt = (
                    base_prompt +
                    f" Provide ONLY the JSON array items for days {start_day} through {days}. "
                    f"Start numbering at day {start_day}. No prose, no wrappers—just the array items."
                )
                raw_tail = _call_model(cont_prompt)
                tail = None
                try:
                    parsed_tail = json.loads(raw_tail)
                    if isinstance(parsed_tail, list):
                        tail = parsed_tail
                except Exception:
                    pass
                if tail is None:
                    tail = _extract_json_array(raw_tail)
                if isinstance(tail, list) and tail:
                    tail_norm = _normalize_list(tail)
                    for it in tail_norm:
                        if it['day'] not in dedup:
                            dedup[it['day']] = it
                    normalized = [dedup[d] for d in sorted(dedup.keys())]
                    for idx, it in enumerate(normalized, start=1):
                        it['day'] = idx
                    if len(normalized) > days:
                        normalized = normalized[:days]

        # Final sanity check; do not fail if we have at least one valid item
        if not normalized:
            raise ValueError('No valid plan items were returned')
        return normalized
    except Exception as e:
        preview = ''
        try:
            preview = (raw[:200] + '...') if raw else ''
        except Exception:
            pass
        print("Error generating career plan from Gemini:", e, "\nRaw preview:", preview)
        return None

def tailor_resume_with_ai(user_resume_content, job_description, user_profile):
    if not model:
        return None

    prompt_parts = [
        "You are an expert resume analyst and career coach. Return ONLY a JSON object (no markdown) with the following shape: ",
        "{ \"summary\": string, \"edits\": [ { \"section\": string, \"original\": string, \"suggested\": string, \"reason\": string } ] }.",
        "- `section`: the resume section (e.g., Summary, Experience, Education, Skills).",
        "- `original`: the exact sentence or bullet from the resume to improve.",
        "- `suggested`: a rewritten version aligned to the job description and best practices.",
        "- `reason`: brief rationale (keywords added, quantified impact, clarity, ATS, etc.)."
    ]

    if user_profile:
        prompt_parts.append(f"The user's name is {user_profile.get('name', 'there')}. ")
        if user_profile.get('user_type'):
            prompt_parts.append(f"They are a {user_profile.get('user_type')}. ")
        if user_profile.get('interests'):
            prompt_parts.append(f"Their interests include: {user_profile.get('interests')}. ")

    prompt_parts.append(
        f"\n\nJob Description:\n{job_description}\n\nUser Resume Text:\n{user_resume_content}\n\n"
        "Ensure edits are sentence-level and actionable. Output strictly valid JSON."
    )

    try:
        # Prefer JSON response
        generation_config = {"response_mime_type": "application/json"}
        try:
            resp = model.generate_content(" ".join(prompt_parts), generation_config=generation_config)
        except TypeError:
            resp = model.generate_content(" ".join(prompt_parts))

        raw = (getattr(resp, 'text', None) or '').strip()
        if raw.startswith('```'):
            raw = raw.strip('`').strip()
            if raw.lower().startswith('json'):
                raw = raw[4:].strip()
        data = json.loads(raw)
        # normalize to expected shape
        edits = data.get('edits') or []
        normalized_edits = []
        for e in edits:
            section = (e.get('section') or '').strip()
            original = (e.get('original') or '').strip()
            suggested = (e.get('suggested') or '').strip()
            reason = (e.get('reason') or '').strip()
            if section and suggested:
                normalized_edits.append({
                    'section': section,
                    'original': original,
                    'suggested': suggested,
                    'reason': reason
                })
        # backward-compat: if older 'points' shape, convert minimally
        if not normalized_edits and data.get('points'):
            for p in data['points']:
                heading = (p.get('heading') or '').strip()
                details = (p.get('details') or '').strip()
                if heading and details:
                    normalized_edits.append({
                        'section': heading,
                        'original': '',
                        'suggested': details,
                        'reason': ''
                    })
        return {
            'summary': (data.get('summary') or '').strip(),
            'edits': normalized_edits
        }
    except Exception as e:
        print('Error tailoring resume with Gemini:', e)
        return None

def _load_extracted_resume_text(user_id: int) -> str:
    try:
        user_data_dir = os.path.join(current_app.instance_path, 'user_data')
        json_path = os.path.join(user_data_dir, f"user_{user_id}_resume.json")
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as jf:
                data = json.load(jf)
                txt = (data or {}).get('extracted_text') or ''
                if txt:
                    return txt
    except Exception:
        pass
    return ''

def _extract_text_from_pdf(path: str) -> str:
    try:
        reader = PdfReader(path)
        parts = []
        for p in reader.pages:
            try:
                parts.append(p.extract_text() or '')
            except Exception:
                parts.append('')
        return "\n".join(parts)
    except Exception:
        return ''

@bp.route('/chat')
@login_required
def chat_with_ai():
    chat_sessions = ChatSession.query.filter_by(user_id=current_user.id).all()
    session_id = request.args.get('session_id')
    if session_id:
         try:
             session_id = int(session_id)
         except ValueError:
             flash('Invalid session ID', 'danger')
             session_id = None
    messages = []
    if session_id:
        messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp).all()
    return render_template('career_advisor/chat.html', title='AI Career Advisor', chat_sessions=chat_sessions,session_id = session_id, messages = messages)

@bp.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    user_input = request.json.get('message')
    session_id = request.json.get('session_id')

    if not user_input:
        return jsonify({'error': 'No message provided'}), 400

    user_profile_data = None
    if current_user.is_authenticated and current_user.profile:
        user_profile_data = {
            'name': current_user.profile.name,
            'interests': current_user.profile.interests,
            'user_type': current_user.profile.user_type
        }

    # Get or create chat session
    if session_id:
        try:
            chat_session = ChatSession.query.get(session_id)
            if not chat_session or chat_session.user_id != current_user.id:
                return jsonify({'error': 'Invalid session ID'}), 400
        except Exception as e:
            return jsonify({'error': f'Error finding session: {e}'}), 500

    else:
        chat_session = ChatSession(user_id=current_user.id)
        db.session.add(chat_session)
        db.session.commit()
        session_id = chat_session.id # this code is added

    ai_response = get_ai_response(user_input, user_profile_data, chat_session)

    # Store messages in the database
    user_message = ChatMessage(session_id=chat_session.id, sender='user', content=user_input)
    ai_message = ChatMessage(session_id=chat_session.id, sender='ai', content=ai_response)
    db.session.add(user_message)
    db.session.add(ai_message)
    db.session.commit()

    # If user consented to generate a plan, extract goal/days and create it automatically
    plan_generated = False
    if _user_consented_to_plan(user_input):
        # Build conversation text
        msgs = ChatMessage.query.filter_by(session_id=chat_session.id).order_by(ChatMessage.timestamp.asc()).all()
        convo = "\n".join([f"{m.sender.upper()}: {m.content}" for m in msgs])
        goal, days = _extract_goal_days_from_history(convo, user_profile_data)
        if goal:
            plan_data = generate_career_plan_with_ai(user_profile_data, goal, days)
            if plan_data:
                try:
                    # Deactivate existing active plan
                    existing_active_plan = CareerPlan.query.filter_by(user_id=current_user.id, is_active=True).first()
                    if existing_active_plan:
                        existing_active_plan.is_active = False
                        db.session.commit()

                    new_plan = CareerPlan(
                        user_id=current_user.id,
                        career_goal=goal,
                        created_date=datetime.utcnow(),
                        last_updated=datetime.utcnow(),
                        is_active=True
                    )
                    db.session.add(new_plan)
                    db.session.commit()

                    for day_task in plan_data:
                        task = DailyTask(
                            career_plan_id=new_plan.id,
                            day_number=day_task['day'],
                            task_description=day_task['task'],
                            resources=json.dumps(day_task.get('resources') or [])
                        )
                        db.session.add(task)
                    db.session.commit()

                    chat_session.has_career_plan = True
                    db.session.commit()
                    plan_generated = True
                    # Optionally append a short note
                    note = "\n\nPlan created in your Tracker."
                    ai_footer = ChatMessage(session_id=chat_session.id, sender='ai', content=note.strip())
                    db.session.add(ai_footer)
                    db.session.commit()
                    ai_response = (ai_response + note).strip()
                except Exception as e:
                    db.session.rollback()

    return jsonify({'response': ai_response, 'session_id': chat_session.id, 'plan_generated': plan_generated})

@bp.route('/api/load_messages/<int:session_id>')
@login_required
def load_messages(session_id):
    try:
        chat_session = ChatSession.query.get(session_id)
        if not chat_session or chat_session.user_id != current_user.id:
            return jsonify({'error': 'Invalid session ID'}), 400

        messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp).all()
        message_list = [{'sender': m.sender, 'content': m.content} for m in messages]
        return jsonify({'messages': message_list})
    except Exception as e:
        return jsonify({'error': f'Error loading messages: {e}'}), 500


@bp.route('/api/chat_session/<int:session_id>/rename', methods=['POST'])
@login_required
def rename_chat_session(session_id):
    try:
        chat_session = ChatSession.query.get_or_404(session_id)
        if chat_session.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Forbidden'}), 403
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'Name required'}), 400
        if len(name) > 100:
            name = name[:100]
        chat_session.session_name = name
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/chat_session/<int:session_id>/delete', methods=['POST'])
@login_required
def delete_chat_session(session_id):
    try:
        chat_session = ChatSession.query.get_or_404(session_id)
        if chat_session.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Forbidden'}), 403
        # Delete messages first to avoid FK issues
        ChatMessage.query.filter_by(session_id=session_id).delete(synchronize_session=False)
        db.session.delete(chat_session)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/chat_session/<int:session_id>/autoname', methods=['POST'])
@login_required
def autoname_chat_session(session_id):
    try:
        chat_session = ChatSession.query.get_or_404(session_id)
        if chat_session.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Forbidden'}), 403

        # Build a short context from the last few messages
        msgs = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.timestamp.desc()).limit(8).all()
        context = "\n".join(reversed([m.content for m in msgs]))

        if not model:
            return jsonify({'success': False, 'error': 'AI not configured'}), 500

        prompt = (
            "Create a concise 3-6 word title for this chat that captures the main topic. "
            "No quotes, no punctuation at the end. Title case.\n\nConversation:\n" + context
        )
        try:
            resp = model.generate_content(prompt)
            title = (resp.text or '').strip().splitlines()[0][:100]
        except Exception as e:
            return jsonify({'success': False, 'error': f'AI error: {e}'}), 500

        if not title:
            return jsonify({'success': False, 'error': 'No title generated'}), 500

        chat_session.session_name = title
        db.session.commit()
        return jsonify({'success': True, 'name': title})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/tracker')
@login_required
def career_tracker():
    # check has_career_plan flag from ChatSession, then allow 
    #chat_session = ChatSession.query.filter_by(user_id=current_user.id, has_career_plan = True).first()
    career_plan = CareerPlan.query.filter_by(user_id = current_user.id).first()
    if not career_plan:
        flash('Please generate career path from chat window to get a personalized career plan.', 'danger')
        return redirect(url_for('career_advisor.chat_with_ai'))

    current_plan = CareerPlan.query.filter_by(user_id=current_user.id, is_active=True).first()
    return render_template('career_advisor/tracker.html', title='Career Tracker', current_plan=current_plan)

@bp.route('/generate_plan', methods=['POST'])
@login_required
def generate_plan():
    career_goal = request.form.get('career_goal')
    days_raw = request.form.get('days')
    session_id = request.form.get('session_id')  # optional from chat page

    if not career_goal:
        flash('Please provide a career goal.', 'danger')
        return redirect(url_for('career_advisor.career_tracker'))

    chat_session = None
    if session_id:
        try:
            chat_session = ChatSession.query.get(int(session_id))
        except Exception:
            chat_session = None
        if not chat_session or chat_session.user_id != current_user.id:
            flash('Invalid session ID.', 'danger')
            return redirect(url_for('career_advisor.chat_with_ai'))

    # Deactivate any existing active plan for the user
    existing_active_plan = CareerPlan.query.filter_by(user_id=current_user.id, is_active=True).first()
    if existing_active_plan:
        existing_active_plan.is_active = False
        db.session.commit()

    user_profile_data = None
    if current_user.is_authenticated and current_user.profile:
        user_profile_data = {
            'name': current_user.profile.name,
            'interests': current_user.profile.interests,
            'user_type': current_user.profile.user_type
        }
    
    days = None
    if days_raw:
        try:
            days = max(1, min(60, int(days_raw)))
        except Exception:
            days = None

    plan_data = generate_career_plan_with_ai(user_profile_data, career_goal, days)

    if plan_data:
        new_plan = CareerPlan(
            user_id=current_user.id,
            career_goal=career_goal,
            created_date=datetime.utcnow(),
            last_updated=datetime.utcnow(),
            is_active=True
        )
        db.session.add(new_plan)
        db.session.commit()

        for day_task in plan_data:
            task = DailyTask(
                career_plan_id=new_plan.id,
                day_number=day_task['day'],
                task_description=day_task['task'],
                resources=json.dumps(day_task.get('resources') or []) # Store resources as JSON string
            )
            db.session.add(task)
        db.session.commit()

        # Set has_career_plan to True in chat session, if applicable
        if chat_session:
            chat_session.has_career_plan = True
            db.session.commit()

        flash('Your personalized career plan has been generated!', 'success')
    else:
        flash('Failed to generate career plan. Please try again.', 'danger')

    return redirect(url_for('career_advisor.career_tracker'))

@bp.route('/api/generate_career_plan', methods=['POST'])
@login_required
def api_generate_career_plan():
    try:
        data = request.get_json(silent=True) or {}
        career_goal = data.get('career_goal')
        session_id = data.get('session_id')
        days = data.get('days')

        if not career_goal:
            return jsonify({
                'success': False,
                'error': 'Please provide a career goal.'
            }), 400

        chat_session = None
        if session_id:
            chat_session = ChatSession.query.get(session_id)
            if not chat_session or chat_session.user_id != current_user.id:
                return jsonify({'success': False, 'error': 'Invalid session ID'}), 400

        # Deactivate existing active plan
        existing_active_plan = CareerPlan.query.filter_by(user_id=current_user.id, is_active=True).first()
        if existing_active_plan:
            existing_active_plan.is_active = False
            db.session.commit()

        user_profile_data = None
        if current_user.is_authenticated and current_user.profile:
            user_profile_data = {
                'name': current_user.profile.name,
                'interests': current_user.profile.interests,
                'user_type': current_user.profile.user_type
            }

        # sanitize days
        safe_days = None
        try:
            if days is not None:
                safe_days = max(1, min(60, int(days)))
        except Exception:
            safe_days = None

        plan_data = generate_career_plan_with_ai(user_profile_data, career_goal, safe_days)
        if not plan_data:
            return jsonify({'success': False, 'error': 'Failed to generate career plan. Please try again.'}), 500

        new_plan = CareerPlan(
            user_id=current_user.id,
            career_goal=career_goal,
            created_date=datetime.utcnow(),
            last_updated=datetime.utcnow(),
            is_active=True
        )
        db.session.add(new_plan)
        db.session.commit()

        for day_task in plan_data:
            task = DailyTask(
                career_plan_id=new_plan.id,
                day_number=day_task['day'],
                task_description=day_task['task'],
                resources=json.dumps(day_task.get('resources') or [])
            )
            db.session.add(task)
        db.session.commit()

        if chat_session:
            chat_session.has_career_plan = True
            db.session.commit()

        return jsonify({'success': True, 'plan_id': new_plan.id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/clear_career_plan', methods=['POST'])
@login_required
def api_clear_career_plan():
    try:
        # Clear the user's active plan (either mark inactive or delete)
        active = CareerPlan.query.filter_by(user_id=current_user.id, is_active=True).first()
        if not active:
            return jsonify({'success': True, 'message': 'No active plan to clear.'})
        # Delete associated tasks, then the plan
        DailyTask.query.filter_by(career_plan_id=active.id).delete(synchronize_session=False)
        db.session.delete(active)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/complete_task/<int:task_id>', methods=['POST'])
@login_required
def complete_task(task_id):
    task = DailyTask.query.get_or_404(task_id)
    if task.career_plan.user_id != current_user.id:
        flash('You are not authorized to complete this task.', 'danger')
        return redirect(url_for('career_advisor.career_tracker'))

    task.is_completed = True
    task.completed_date = datetime.utcnow()
    db.session.commit()
    flash('Task marked as complete!', 'success')
    return redirect(url_for('career_advisor.career_tracker'))

@bp.route('/tailor_resume', methods=['GET', 'POST'])
@login_required
def tailor_resume():
    # Gate access: ensure user has uploaded a resume
    if not current_user.profile:
        flash('Please create your profile first.', 'info')
        return redirect(url_for('profile.create_profile'))
    if not current_user.profile.resume_path or not os.path.exists(current_user.profile.resume_path):
        flash('Please upload your resume (PDF) in your profile before using resume tailoring.', 'danger')
        return redirect(url_for('profile.edit_profile'))

    # Also ensure we have some content (either extracted JSON or fallback by extracting now)
    extracted_text = _load_extracted_resume_text(current_user.id)
    if not extracted_text:
        # Attempt to extract directly from the stored PDF
        extracted_text = _extract_text_from_pdf(current_user.profile.resume_path)
        if not extracted_text:
            flash('Your resume could not be processed. Please re-upload your PDF.', 'danger')
            return redirect(url_for('profile.edit_profile'))

    tailoring_suggestions = None
    if request.method == 'POST':
        job_description = request.form.get('job_description')
        if not job_description:
            flash('Please provide a job description.', 'danger')
            return redirect(url_for('career_advisor.tailor_resume'))

        user_profile_data = None
        if current_user.profile:
            user_profile_data = {
                'name': current_user.profile.name,
                'interests': current_user.profile.interests,
                'user_type': current_user.profile.user_type
            }

        tailoring_suggestions = tailor_resume_with_ai(extracted_text, job_description, user_profile_data)
        if not tailoring_suggestions:
            flash('Failed to get resume tailoring suggestions. Please try again.', 'danger')
    return render_template('career_advisor/tailor_resume.html', title='Resume Tailoring', suggestions=tailoring_suggestions)
