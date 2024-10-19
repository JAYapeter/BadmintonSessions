from models import User, Session
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from config import Config
from extensions import db  # Import db from extensions
from flask_migrate import Migrate
from sqlalchemy import asc
from datetime import datetime, timedelta
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect


app = Flask(__name__)
# Initialize CSRF protection
csrf = CSRFProtect(app)

app.config.from_object(Config)
db.init_app(app)  # Initialize db with app
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Redirect to login page if not authenticated


# Initialize Flask-Migrate
migrate = Migrate(app, db)


# User loader callback function

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        # Get display name from form
        display_name = request.form['display_name']

        # Check if the email is already registered
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email is already registered')
            return redirect(url_for('register'))

        # Create a new user with the display name
        new_user = User(email=email, display_name=display_name)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! You can now log in.')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Find user by email
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!')
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    # Get the current date
    current_date = datetime.now().date()

    # Retrieve only upcoming sessions sorted by the session date (oldest to newest)
    sessions = Session.query.filter(
        Session.date >= current_date).order_by(asc(Session.date)).all()

    return render_template('index.html', sessions=sessions)


# Set a simple admin password (you can replace this with more secure logic)
ADMIN_PASSWORD = 'admin123'


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form['password']
        if password == ADMIN_PASSWORD:
            session['admin'] = True  # Mark the user as an admin
            return redirect(url_for('admin'))
        else:
            flash('Invalid password, please try again.')
            return redirect(url_for('admin_login'))
    return render_template('admin_login.html')


@app.route('/admin_logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    # Get the current date
    current_date = datetime.now().date()

    # Retrieve current and past sessions
    current_sessions = Session.query.filter(
        Session.date >= current_date).order_by(asc(Session.date)).all()
    past_sessions = Session.query.filter(
        Session.date < current_date).order_by(Session.date.desc()).all()

    if request.method == 'POST':
        # Add new session logic
        if 'add_session' in request.form:
            date = request.form['date']
            # Convert the string date from the form to a Python date object
            date = datetime.strptime(date, '%Y-%m-%d').date()

            slots = int(request.form['slots'])
            if (slots < 0):
                flash('Number of Slots must be greater than 0', 'error')
                return redirect(url_for('admin'))
            else:
                new_session = Session(date=date, slots=slots)
                db.session.add(new_session)
                db.session.commit()
                flash('Session added successfully!')
                return redirect(url_for('admin'))

    return render_template('admin.html', current_sessions=current_sessions, past_sessions=past_sessions)


@app.route('/admin/delete_session/<int:session_id>', methods=['POST'])
def delete_session(session_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    session_to_delete = Session.query.get(session_id)
    if session_to_delete:
        db.session.delete(session_to_delete)
        db.session.commit()
        flash('Session deleted successfully!')
    else:
        flash('Session not found.')

    return redirect(url_for('admin'))


@app.route('/admin/modify_session/<int:session_id>', methods=['POST'])
def modify_session(session_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    session_to_modify = Session.query.get(session_id)
    if session_to_modify:
        # Get the new slot count from the form
        new_slots = int(request.form['slots'])
        old_slots = session_to_modify.slots
        date = request.form['date']
        # Convert the string date from the form to a Python date object
        date = datetime.strptime(date, '%Y-%m-%d').date()
        session_to_modify.date = date
        session_to_modify.slots = new_slots

        # If slots have increased, move users from waitlist to participants
        if new_slots > old_slots:
            available_slots = new_slots - len(session_to_modify.users)
            if available_slots > 0 and len(session_to_modify.waitlist) > 0:
                users_to_move = min(available_slots, len(
                    session_to_modify.waitlist))
                for _ in range(users_to_move):
                    # Get the first user from the waitlist
                    user = session_to_modify.waitlist.pop(0)
                    # Move them to participants
                    session_to_modify.users.append(user)
                db.session.commit()
                flash(f'{users_to_move} users moved from waitlist to participants.')

        # If slots have decreased, move participants to the waitlist
        elif new_slots < old_slots:
            excess_participants = len(session_to_modify.users) - new_slots
            if excess_participants > 0:
                # Get the last excess participants
                users_to_move = session_to_modify.users[-excess_participants:]
                for user in users_to_move:
                    session_to_modify.users.remove(user)
                    session_to_modify.waitlist.append(
                        user)  # Move them to the waitlist
                db.session.commit()
                flash(
                    f'{excess_participants} users moved from participants to waitlist due to slot reduction.')

        db.session.commit()
        flash('Session modified successfully!')
    else:
        flash('Session not found.')

    return redirect(url_for('admin'))


# View participants for a session in the admin panel
@app.route('/admin/session/<int:session_id>/participants_json', methods=['GET'])
@login_required
def admin_session_participants_json(session_id):
    session = Session.query.get_or_404(session_id)
    participants = [{'id': user.id, 'display_name': user.display_name}
                    for user in session.users]
    waitlist = [{'id': user.id, 'display_name': user.display_name}
                for user in session.waitlist]

    return jsonify({
        'participants': participants,
        'waitlist': waitlist
    })


@app.route('/admin/session/<int:session_id>/emails', methods=['GET'])
@login_required
def get_session_emails(session_id):
    session = Session.query.get_or_404(session_id)
    # Get emails of confirmed participants
    # Assuming 'session.users' contains confirmed participants
    emails = [user.email for user in session.users]

    return jsonify({'emails': ', '.join(emails)})


@app.route('/poll', methods=['POST'])
@login_required
def poll():
    session_id = request.form.get('session_id')
    user = current_user  # The logged-in user
    session = Session.query.get(session_id)

    if not session:
        return jsonify({'error': 'Session not found.'}), 404

    # Check if the user is already confirmed or waitlisted for this session
    if user in session.users:
        return jsonify({'error': 'You are already confirmed for this session.'}), 400
    if user in session.waitlist:
        return jsonify({'error': 'You are already waitlisted for this session.'}), 400

    # Check if there are remaining slots in the session
    remaining_slots = session.slots - len(session.users)

    if remaining_slots > 0:
        # Add the user as a confirmed participant
        session.users.append(user)
        message = 'You have successfully joined the session!'
    else:
        # Add the user to the waitlist
        session.waitlist.append(user)
        message = 'The session is full. You have been added to the waitlist.'

    # Commit changes to the database
    db.session.commit()

    # Update the response with the new number of remaining slots and waitlist count
    remaining_slots = session.slots - len(session.users)
    waitlist_count = len(session.waitlist)

    return jsonify({
        'message': message,
        'remaining_slots': remaining_slots,
        'waitlist_count': waitlist_count
    })


@app.route('/join_session/<int:session_id>', methods=['POST'])
@login_required
def join_session(session_id):
    session = Session.query.get_or_404(session_id)
    user = current_user

    # Check if the user is already in the session
    if user in session.users:
        return jsonify({'error': 'You have already joined this session.'}), 400

    # Check if the session is full
    if len(session.users) < session.slots:
        session.users.append(user)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'You have successfully joined the session.',
            'remaining_slots': session.slots - len(session.users),
            'waitlist_count': len(session.waitlist),
            'joined': True  # Indicate that the user has joined
        })
    else:
        # If the session is full, add the user to the waitlist
        if user not in session.waitlist:
            session.waitlist.append(user)
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'The session is full. You have been added to the waitlist.',
                'remaining_slots': session.slots - len(session.users),
                'waitlist_count': len(session.waitlist),
                'joined': False,
                'waitlisted': True
            })
        else:
            return jsonify({'error': 'You are already on the waitlist for this session.'}), 400


@app.route('/leave_session/<int:session_id>', methods=['POST'])
@login_required
def leave_session(session_id):
    session = Session.query.get_or_404(session_id)

    # if is_session_locked(session):
    if (session.is_locked):
        return jsonify({"error": "You can't leave this session after 8 p.m. the day before."}), 403

    user = current_user

    # Check if the user is part of the session
    if user in session.users:
        # Remove the user from confirmed participants
        session.users.remove(user)

        # If there is a waitlist, move the first person from waitlist to confirmed
        if session.waitlist:
            next_in_line = session.waitlist.pop(0)
            session.users.append(next_in_line)

        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'You have successfully left the session.',
            'remaining_slots': session.slots - len(session.users),
            'waitlist_count': len(session.waitlist),
            'joined': False  # Indicate that the user has left
        })
    elif user in session.waitlist:
        # Remove the user from confirmed participants
        session.waitlist.remove(user)

        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'You have successfully left the waitlist.',
            'remaining_slots': session.slots - len(session.users),
            'waitlist_count': len(session.waitlist),
            'joined': False  # Indicate that the user has left
        })
    else:
        return jsonify({'error': 'You are not part of this session.'}), 400


@app.route('/session_participants/<int:session_id>', methods=['GET'])
def session_participants(session_id):
    session = Session.query.get_or_404(session_id)

    if session:
        participants = [{'display_name': user.display_name}
                        for user in session.users]
        waitlisted = [{'display_name': user.display_name}
                      for user in session.waitlist]

        return jsonify({
            'participants': participants,
            'waitlist': waitlisted
        })
    else:
        return jsonify({'error': 'Session not found'}), 404


# def is_session_locked(session):

#     # Lock time is 8 p.m. the day before the session
#     # Subtract 1 day, add 20 hours to get 8 p.m.
#     lock_time = session.date - timedelta(days=1, hours=-20)
#     return datetime.now() >= lock_time


# @app.route('/add_session', methods=['GET', 'POST'])
# def add_session():
#     if request.method == 'POST':
#         date = request.form['date']
#         slots = int(request.form['slots'])

#         new_session = Session(date=date, slots=slots, shuttles_used=0)
#         db.session.add(new_session)
#         db.session.commit()

#         return redirect(url_for('index'))

#     return render_template('add_session.html')


if __name__ == "__main__":
    # Allow access from any IP address
    app.run(debug=True, host='0.0.0.0', port=8000)
