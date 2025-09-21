from app import create_app, db, login_manager
from app.models import User, Profile, CareerPlan, DailyTask

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Profile': Profile, 'CareerPlan': CareerPlan, 'DailyTask': DailyTask}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
