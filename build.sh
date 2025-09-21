#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Create database tables
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"