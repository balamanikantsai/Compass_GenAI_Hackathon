from flask import Blueprint

bp = Blueprint('career_advisor', __name__)

from app.career_advisor import routes
