from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    profile = db.relationship('Profile', backref='user', uselist=False)
    career_plans = db.relationship('CareerPlan', backref='user', lazy=True)
    chat_sessions = db.relationship('ChatSession', backref='user', lazy=True)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"


class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    place = db.Column(db.String(100), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # student, teacher, professional, learner
    organization_name = db.Column(db.String(100), nullable=True)
    details = db.Column(db.Text)
    resume_path = db.Column(db.String(200))
    interests = db.Column(db.Text)
    hobbies = db.Column(db.Text)
    additional_info = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)

    def __repr__(self):
        return f"Profile('{self.name}', '{self.user_type}')"


class CareerPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    career_goal = db.Column(db.String(200), nullable=False)
    created_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    daily_tasks = db.relationship('DailyTask', backref='career_plan', lazy=True)

    def __repr__(self):
        return f"CareerPlan(User ID: {self.user_id}, Goal: '{self.career_goal}', Active: {self.is_active})"


class DailyTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    career_plan_id = db.Column(db.Integer, db.ForeignKey('career_plan.id'), nullable=False)
    day_number = db.Column(db.Integer, nullable=False)
    task_description = db.Column(db.Text, nullable=False)
    resources = db.Column(db.Text)
    is_completed = db.Column(db.Boolean, nullable=False, default=False)
    completed_date = db.Column(db.DateTime)

    def __repr__(self):
        return f"DailyTask(Plan ID: {self.career_plan_id}, Day {self.day_number}, Completed: {self.is_completed})"

class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_name = db.Column(db.String(100), default='New Session') # Add Session name
    created_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    messages = db.relationship('ChatMessage', backref='chat_session', lazy=True)
    has_career_plan = db.Column(db.Boolean, nullable=False, default=False) # flag to verify tracker is created or not


    def __repr__(self):
        return f"ChatSession(User ID: {self.user_id}, Created: {self.created_date})"

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender = db.Column(db.String(50), nullable=False)  # 'user' or 'ai'
    content = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"ChatMessage(Session ID: {self.session_id}, Sender: {self.sender}, Time: {self.timestamp})"
