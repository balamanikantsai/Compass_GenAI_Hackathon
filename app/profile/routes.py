from flask import render_template, url_for, flash, redirect, request, current_app
from app.profile import bp
from app.models import User, Profile
from app import db
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
import os
import json
from PyPDF2 import PdfReader
import re
from flask import send_file, abort
import google.generativeai as genai

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_pdf_text(path):
    try:
        reader = PdfReader(path)
        texts = []
        for page in reader.pages:
            try:
                texts.append(page.extract_text() or '')
            except Exception:
                texts.append('')
        return '\n'.join(texts)
    except Exception:
        return ''

def save_resume_and_json(user_id, file_storage):
    # Ensure upload dir
    upload_dir = current_app.config.get('RESUME_UPLOAD_FOLDER')
    os.makedirs(upload_dir, exist_ok=True)
    user_data_dir = os.path.join(current_app.instance_path, 'user_data')
    os.makedirs(user_data_dir, exist_ok=True)

    filename = secure_filename(f"user_{user_id}_resume.pdf")
    save_path = os.path.join(upload_dir, filename)
    file_storage.save(save_path)

    # Extract text
    extracted_text = extract_pdf_text(save_path)

    # Save JSON with extracted text and placeholder for parsed AI data
    json_path = os.path.join(user_data_dir, f"user_{user_id}_resume.json")
    data = {
        'extracted_text': extracted_text,
        'ai_parsed': None
    }
    with open(json_path, 'w', encoding='utf-8') as jf:
        json.dump(data, jf, ensure_ascii=False, indent=2)

    # Return relative path to stored resume (inside instance)
    return save_path


@bp.route('/resume/<int:user_id>/download')
@login_required
def download_resume(user_id):
    # Only allow the owner to download their resume
    if current_user.id != user_id:
        abort(403)
    user = User.query.get_or_404(user_id)
    if not user.profile or not user.profile.resume_path:
        abort(404)
    resume_path = user.profile.resume_path
    if not os.path.exists(resume_path):
        abort(404)
    return send_file(resume_path, as_attachment=True)


def parse_resume_with_ai(user_id):
    # Load extracted text JSON and call Gemini to produce structured JSON
    user_data_dir = os.path.join(current_app.instance_path, 'user_data')
    json_path = os.path.join(user_data_dir, f"user_{user_id}_resume.json")
    if not os.path.exists(json_path):
        return None
    with open(json_path, 'r', encoding='utf-8') as jf:
        data = json.load(jf)

    extracted_text = data.get('extracted_text', '')
    if not extracted_text:
        return None

    # If model not configured, skip
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')
    if not GEMINI_API_KEY:
        return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Request JSON-only output when supported by the model
        generation_config = {"response_mime_type": "application/json"}
        try:
            model = genai.GenerativeModel(GEMINI_MODEL, generation_config=generation_config)
        except TypeError:
            # Older SDKs may not support generation_config in constructor; fall back gracefully
            model = genai.GenerativeModel(GEMINI_MODEL)
    except Exception as e:
        print('AI model init failed for resume parsing:', e)
        return None

    prompt = (
        "You are a strict JSON generator. Extract structured fields from the following resume text. "
        "Return ONLY a valid JSON object and nothing else (no markdown, no backticks, no commentary). "
        "Keys required: name (string), email (string), phone (string), skills (array of strings), "
        "education (array of strings), experience (array of objects with keys: role, company, years), summary (string).\n\n"
        "Resume Text:\n" + extracted_text
    )

    def _extract_json_from_text(text: str):
        if not text:
            return None
        t = text.strip()
        # If fenced code block, capture JSON within
        m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", t, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            try:
                return json.loads(candidate)
            except Exception:
                pass
        # If starts with backticks, strip leading/trailing fences conservatively
        if t.startswith('```') and t.endswith('```'):
            inner = t.strip('`').strip()
            # Remove optional leading language tag
            inner = re.sub(r"^(json|JSON)\s+", "", inner)
            try:
                return json.loads(inner)
            except Exception:
                pass
        # Try from first '{' to last '}'
        start = t.find('{')
        end = t.rfind('}')
        if start != -1 and end != -1 and end > start:
            candidate = t[start:end+1]
            try:
                return json.loads(candidate)
            except Exception:
                pass
        # Last resort: return None
        return None
    try:
        response = model.generate_content(prompt)
        # Prefer response.text; if empty, collect text parts from candidates
        parsed_text = (getattr(response, 'text', None) or '').strip()
        if not parsed_text and getattr(response, 'candidates', None):
            texts = []
            try:
                for cand in response.candidates:
                    for part in getattr(cand.content, 'parts', []) or []:
                        if hasattr(part, 'text') and part.text:
                            texts.append(part.text)
            except Exception:
                pass
            parsed_text = "\n".join(texts).strip()

        parsed_json = _extract_json_from_text(parsed_text)
        if parsed_json is None:
            # Try once more by asking the model to reformat strictly as JSON
            strict_prompt = (
                "Reformat the previous extraction as STRICT JSON only. Do not include any text other than the JSON object."
            )
            retry_resp = model.generate_content([prompt, strict_prompt])
            retry_text = (getattr(retry_resp, 'text', None) or '').strip()
            parsed_json = _extract_json_from_text(retry_text)

        if parsed_json is None:
            raise ValueError("Model did not return valid JSON")

        data['ai_parsed'] = parsed_json
        with open(json_path, 'w', encoding='utf-8') as jf:
            json.dump(data, jf, ensure_ascii=False, indent=2)
        return parsed_json
    except Exception as e:
        preview = ''
        try:
            preview = (parsed_text[:200] + '...') if parsed_text else ''
        except Exception:
            pass
        print('Error parsing resume with AI:', e, '\nRaw preview:', preview)
        return None


@bp.route('/parse_resume', methods=['POST'])
@login_required
def parse_resume():
    profile = current_user.profile
    if not profile or not profile.resume_path:
        flash('No resume to parse.', 'danger')
        return redirect(url_for('profile.view_profile'))
    parsed = parse_resume_with_ai(current_user.id)
    if parsed:
        flash('Resume parsed successfully.', 'success')
    else:
        flash('Failed to parse resume. Check AI configuration or try again.', 'danger')
    return redirect(url_for('profile.view_profile'))

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_profile():
    if current_user.profile:
        flash('You already have a profile!', 'info')
        return redirect(url_for('profile.view_profile'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        place = request.form.get('place', '').strip()
        user_type = request.form.get('user_type', '').strip()
        organization_name = request.form.get('organization_name') # New field
        detail_1 = request.form.get('detail_1', '').strip()
        detail_2 = request.form.get('detail_2', '').strip()
        interests = request.form.get('interests')
        hobbies = request.form.get('hobbies')
        additional_info = request.form.get('additional_info')
        resume_file = request.files.get('resume_file')

        # Enforce required fields
        if not name or not user_type:
            flash('Full Name and "I am a" are required fields.', 'danger')
            return redirect(url_for('profile.create_profile'))

        resume_path = None
        if resume_file and resume_file.filename:
            if not allowed_file(resume_file.filename):
                flash('Resume must be a PDF file.', 'danger')
                return redirect(url_for('profile.create_profile'))
            resume_path = save_resume_and_json(current_user.id, resume_file)
            # Parse resume synchronously after upload
            parsed = parse_resume_with_ai(current_user.id)
            if parsed:
                flash('Resume uploaded and parsed successfully.', 'success')
            else:
                flash('Resume uploaded but parsing failed. You can try "Parse Resume" later.', 'warning')

        # Combine details into the model 'details' field as structured text
        combined_details = ''
        if detail_1:
            combined_details += f"{detail_1}\n"
        if detail_2:
            combined_details += f"{detail_2}\n"

        profile = Profile(
            name=name,
            place=place,
            user_type=user_type,
            organization_name=organization_name, # New field
            details=combined_details,
            resume_path=resume_path,
            interests=interests,
            hobbies=hobbies,
            additional_info=additional_info,
            user=current_user
        )
        db.session.add(profile)
        db.session.commit()
        flash('Your profile has been created!', 'success')
        return redirect(url_for('profile.view_profile'))
    return render_template('profile/create_profile.html', title='Create Profile')

@bp.route('/view')
@login_required
def view_profile():
    profile = current_user.profile
    if not profile:
        flash('Please create your profile first.', 'info')
        return redirect(url_for('profile.create_profile'))
    # Load parsed resume JSON if present
    parsed = None
    try:
        user_data_dir = os.path.join(current_app.instance_path, 'user_data')
        json_path = os.path.join(user_data_dir, f"user_{profile.user_id}_resume.json")
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as jf:
                data = json.load(jf)
                parsed = data.get('ai_parsed')
    except Exception:
        parsed = None
    return render_template('profile/view_profile.html', title='View Profile', profile=profile, parsed=parsed)

@bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    profile = current_user.profile
    if not profile:
        flash('Please create your profile first.', 'info')
        return redirect(url_for('profile.create_profile'))

    if request.method == 'POST':
        profile.name = request.form.get('name', '').strip()
        profile.place = request.form.get('place', '').strip()
        profile.user_type = request.form.get('user_type', '').strip()
        profile.organization_name = request.form.get('organization_name') # New field
        detail_1 = request.form.get('detail_1', '').strip()
        detail_2 = request.form.get('detail_2', '').strip()
        resume_file = request.files.get('resume_file')
        profile.interests = request.form.get('interests')
        profile.hobbies = request.form.get('hobbies')
        profile.additional_info = request.form.get('additional_info')

        # Enforce required fields
        if not profile.name or not profile.user_type:
            flash('Full Name and "I am a" are required fields.', 'danger')
            return redirect(url_for('profile.edit_profile'))

        if resume_file and resume_file.filename:
            if not allowed_file(resume_file.filename):
                flash('Resume must be a PDF file.', 'danger')
                return redirect(url_for('profile.edit_profile'))
            saved_path = save_resume_and_json(current_user.id, resume_file)
            profile.resume_path = saved_path
            # Parse resume synchronously after upload
            parsed = parse_resume_with_ai(current_user.id)
            if parsed:
                flash('Resume uploaded and parsed successfully.', 'success')
            else:
                flash('Resume uploaded but parsing failed. You can try "Parse Resume" later.', 'warning')

        # Update combined details
        combined_details = ''
        if detail_1:
            combined_details += f"{detail_1}\n"
        if detail_2:
            combined_details += f"{detail_2}\n"
        profile.details = combined_details
        db.session.commit()
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('profile.view_profile'))
    return render_template('profile/edit_profile.html', title='Edit Profile', profile=profile)
