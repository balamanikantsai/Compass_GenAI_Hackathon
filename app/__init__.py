from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv
import os
import json
import markdown
from datetime import datetime
from markupsafe import Markup

# Load environment variables from .env file
load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

def format_datetime(value):
    return value.strftime('%B %d, %Y')

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.jinja_env.filters['format_datetime'] = format_datetime

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User # Import User model for user_loader

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Custom Jinja2 filter for parsing JSON strings
    @app.template_filter('from_json')
    def from_json_filter(value):
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return []
        return []
    
    # Custom Jinja2 filter for rendering Markdown to HTML
    @app.template_filter('markdown')
    def markdown_filter(text):
        return Markup(markdown.markdown(text))

    # Add current_time to all templates
    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}

    # Import and register blueprints here
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.profile import bp as profile_bp
    app.register_blueprint(profile_bp, url_prefix='/profile')

    from app.career_advisor import bp as career_advisor_bp
    app.register_blueprint(career_advisor_bp, url_prefix='/career')
    
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()  # Create database tables for the first time if they don't exist

    return app
