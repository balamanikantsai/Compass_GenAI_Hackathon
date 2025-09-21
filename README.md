# Career Advisor Flask App

AI-powered career advisor with chat, resume parsing/tailoring, and a 7-day plan tracker.

## Features
- AI chat with session management (rename/delete/auto-name)
- Resume upload (PDF), text extraction, and AI parsing to structured JSON
- Resume tailoring with actionable, sentence-level suggestions
- Personalized 7-day career plan generator and task tracker
- SQLite database under `instance/site.db`

## Prerequisites
- Python 3.10+ installed
- Windows PowerShell (5.1+) or VS Code with Python extension

## Quick Start (Windows PowerShell)
1) Create & activate a virtual environment
- `python -m venv .venv`
- `./.venv/Scripts/Activate.ps1`

2) Install dependencies
- `python -m pip install --upgrade pip`
- `pip install -r requirements.txt`

3) Configure environment
- Copy `.env.example` to `.env`
- Set `SECRET_KEY` and (optional) `DATABASE_URL`
- Set `GEMINI_API_KEY` to enable AI features (required for chat/plan/tailoring)

4) Run the app (with auto-reload)
- `flask --version` (first time only, to confirm Flask is on PATH)
- `$env:FLASK_APP = 'main.py'; $env:FLASK_ENV = 'development'; $env:FLASK_DEBUG = '1'; flask run --reload`

Open the app at `http://127.0.0.1:5000/`.

Note: `.flaskenv` is included and usually picked up automatically when using `flask run`. Setting the env vars explicitly as above is a safe fallback on Windows.

## VS Code: Debug + Hot Reload
- Launch config: `.vscode/launch.json` → "Flask: Debug with Reload"
- Press F5 and pick the above configuration to start the dev server with reload
- Alternatively, run the task: `.vscode/tasks.json` → "Flask: Run (reload)"

## Environment Variables
- `SECRET_KEY`: Required for session security
- `DATABASE_URL`: Optional; defaults to SQLite at `instance/site.db`
- `GEMINI_API_KEY`: Required for AI features (Google Gemini)
- `GEMINI_MODEL`: Optional; default is `gemini-1.5-flash`

Store these in `.env`. The app uses `python-dotenv` and loads `.env` automatically.

## Data & Uploads
- SQLite DB path: `instance/site.db` (created automatically)
- Resume uploads: `instance/uploads/user_<id>_resume.pdf`
- Parsed resume JSON: `instance/user_data/user_<id>_resume.json`

## Common Workflows
- Create profile → upload PDF resume → resume is parsed immediately
- Tailor resume → paste a job description → get structured suggestions
- Chat with AI → keep multiple sessions; rename/delete/auto-name
- Generate career plan from chat → view and track progress under Tracker

## Chat Memory & Concise Replies
- The model receives full session history for context on every turn.
- Replies are prompted to be concise (≤ 5 lines), expanding only for genuine domain explanations.
- The UI collapses overly long AI messages with a “Show full” toggle to keep chats readable.

## Troubleshooting
- AI features disabled: Ensure `GEMINI_API_KEY` is set in `.env` and restart the server
- Model not found: Set `GEMINI_MODEL` (e.g., `gemini-1.5-flash`) or upgrade `google-generativeai`
- Flask not found: Activate venv, then `pip install -r requirements.txt`
- Permission errors on venv activation: Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` in an elevated PowerShell, then re-run activation

## Production Notes
- Use a production WSGI server (e.g., Gunicorn via WSL) and a real database
- Set strong `SECRET_KEY` and configure HTTPS/secure cookies
- Consider externalizing AI calls or using a task queue for heavy jobs
