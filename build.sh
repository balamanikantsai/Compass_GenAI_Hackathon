#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Ensure instance directory exists for SQLite database
mkdir -p instance
mkdir -p instance/uploads
mkdir -p instance/user_data

# Create database tables
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all(); print('Database tables created successfully')"