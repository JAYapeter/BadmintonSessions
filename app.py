from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from config import Config
from extensions import db  # Import db from extensions
from flask_migrate import Migrate
from sqlalchemy import asc
from datetime import datetime
from flask_login import LoginManager, login_user, logout_user, login_required, current_user


app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)  # Initialize db with app
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Redirect to login page if not authenticated


# Initialize Flask-Migrate
migrate = Migrate(app, db)

from models import User, Session

# User loader callback function
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        display_name = request.form['display_name']  # Get display name from form

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
    sessions = Session.query.filter(Session.date >= current_date).order_by(asc(Session.date)).all()

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
    current_sessions = Session.query.filter(Session.date >= current_date).order_by(asc(Session.date)).all()
    past_sessions = Session.query.filter(Session.date < current_date).order_by(Session.date.desc()).all()

    if request.method == 'POST':
        # Add new session logic
        if 'add_session' in request.form:
            date = request.form['date']
            slots = int(request.form['slots'])
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
        session_to_modify.date = request.form['date']
        session_to_modify.slots = new_slots
        
        # If slots have increased, move users from waitlist to participants
        if new_slots > old_slots:
            available_slots = new_slots - len(session_to_modify.users)
            if available_slots > 0 and len(session_to_modify.waitlist) > 0:
                users_to_move = min(available_slots, len(session_to_modify.waitlist))
                for _ in range(users_to_move):
                    user = session_to_modify.waitlist.pop(0)  # Get the first user from the waitlist
                    session_to_modify.users.append(user)      # Move them to participants
                db.session.commit()
                flash(f'{users_to_move} users moved from waitlist to participants.')

        # If slots have decreased, move participants to the waitlist
        elif new_slots < old_slots:
            excess_participants = len(session_to_modify.users) - new_slots
            if excess_participants > 0:
                users_to_move = session_to_modify.users[-excess_participants:]  # Get the last excess participants
                for user in users_to_move:
                    session_to_modify.users.remove(user)
                    session_to_modify.waitlist.append(user)  # Move them to the waitlist
                db.session.commit()
                flash(f'{excess_participants} users moved from participants to waitlist due to slot reduction.')

        db.session.commit()
        flash('Session modified successfully!')
    else:
        flash('Session not found.')

    return redirect(url_for('admin'))


# View participants for a session in the admin panel
@app.route('/admin/session/<int:session_id>/participants_json', methods=['GET'])
def admin_view_participants_json(session_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    session_obj = Session.query.get(session_id)
    if session_obj:
        participants = [{'id': user.id, 'name': user.name} for user in session_obj.users]
        waitlist = [{'id': user.id, 'name': user.name} for user in session_obj.waitlist]
        
        return jsonify({
            'participants': participants,
            'waitlist': waitlist
        })
    else:
        return jsonify({'error': 'Session not found'}), 404

# Add a participant to a session
@app.route('/admin/session/<int:session_id>/add_participant', methods=['POST'])
def admin_add_participant(session_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    session_obj = Session.query.get(session_id)  # Make sure this session ID is used

    if session_obj:
        user_name = request.form['user_name']
        user = User.query.filter_by(name=user_name).first()

        if not user:
            # Create a new user if one doesn't exist
            user = User(name=user_name)
            db.session.add(user)
            db.session.commit()

        # Add participant if slots are available, otherwise add to waitlist
        if len(session_obj.users) < session_obj.slots:
            session_obj.users.append(user)
            db.session.commit()
            return jsonify({'message': f'{user_name} added to session'}), 200  # Return success response
        else:
            # Add user to the waitlist if session is full
            session_obj.waitlist.append(user)
            db.session.commit()
            return jsonify({'message': f'{user_name} added to the waitlist'}), 200  # Return success response
    else:
        return jsonify({'error': 'Session not found'}), 404



# Delete a participant and update the waitlist
@app.route('/admin/session/<int:session_id>/remove_participant/<int:user_id>', methods=['POST'])
def admin_remove_participant(session_id, user_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    session_obj = Session.query.get(session_id)
    user = User.query.get(user_id)

    if session_obj and user:
        # Remove user from the participants list
        if user in session_obj.users:
            session_obj.users.remove(user)
            flash(f'{user.name} removed from participants.')

            # Check the waitlist and move the top waitlisted user into participants
            if len(session_obj.waitlist) > 0:
                top_waitlist_user = session_obj.waitlist.pop(0)
                session_obj.users.append(top_waitlist_user)
                flash(f'{top_waitlist_user.name} moved from waitlist to participants.')

            db.session.commit()
            return jsonify({'message': 'User removed successfully'}), 200  # Return success response
        else:
            return jsonify({'error': 'User not found in participants'}), 404
    else:
        return jsonify({'error': 'Session or user not found'}), 404
    
@app.route('/admin/session/<int:session_id>/remove_waitlisted/<int:user_id>', methods=['POST'])
def admin_remove_waitlisted(session_id, user_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    session_obj = Session.query.get(session_id)
    user = User.query.get(user_id)

    if session_obj and user:
        # Remove the user from the waitlist
        if user in session_obj.waitlist:
            session_obj.waitlist.remove(user)
            db.session.commit()
            return jsonify({'message': f'{user.name} removed from waitlist'}), 200
        else:
            return jsonify({'error': 'User not found in waitlist'}), 404
    else:
        return jsonify({'error': 'Session or user not found'}), 404


# Reorder participants and waitlist
@app.route('/admin/session/<int:session_id>/reorder', methods=['POST'])
def admin_reorder(session_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    session_obj = Session.query.get(session_id)

    if session_obj:
        # Reorder participants
        participant_order = request.form.getlist('participant_order[]')
        new_participants = []
        for user_id in participant_order:
            user = User.query.get(user_id)
            if user:
                new_participants.append(user)
        session_obj.users = new_participants

        # Reorder waitlist
        waitlist_order = request.form.getlist('waitlist_order[]')
        new_waitlist = []
        for user_id in waitlist_order:
            user = User.query.get(user_id)
            if user:
                new_waitlist.append(user)
        session_obj.waitlist = new_waitlist

        db.session.commit()
        return jsonify({'message': 'Participant and waitlist order updated successfully.'}), 200

    return jsonify({'error': 'Session not found'}), 404



@app.route('/poll', methods=['POST'])
def poll():
    session_id = request.form['session_id']
    user_name = request.form['user_name']
    
    # Find or create the user
    user = User.query.filter_by(name=user_name).first()
    if not user:
        user = User(name=user_name)
        db.session.add(user)
        db.session.commit()

    # Get the session
    session = Session.query.get(session_id)
    
    # Check if the session is full
    if len(session.users) < session.slots:
        session.users.append(user)
        db.session.commit()
        message = 'You have successfully joined the session!'
    else:
        # Add to waitlist if the session is full
        if user not in session.waitlist:
            session.waitlist.append(user)
            db.session.commit()
            message = 'The session is full. You have been added to the waitlist.'
        else:
            message = 'You are already on the waitlist.'

    # Return response with updated slot and waitlist count
    return {
        'message': message,
        'remaining_slots': session.slots - len(session.users),
        'waitlist_count': len(session.waitlist)
    }, 200


@app.route('/fees', methods=['GET', 'POST'])
def fees():
    if request.method == 'POST':
        session_id = request.form['session_id']
        shuttles_used = int(request.form['shuttles_used'])
        session = Session.query.get(session_id)

        session.shuttles_used = shuttles_used
        db.session.commit()

        return redirect(url_for('fees'))

    sessions = Session.query.all()
    return render_template('fees.html', sessions=sessions)

@app.route('/waitlist')
def waitlist():
    waitlisted = Poll.query.all()
    return render_template('waitlist.html', waitlisted=waitlisted)

@app.route('/session_participants/<int:session_id>', methods=['GET'])
def session_participants(session_id):
    session = Session.query.get(session_id)
    
    if session:
        participants = [{'name': user.name} for user in session.users]
        waitlisted = [{'name': user.name} for user in session.waitlist]
        
        return jsonify({
            'participants': participants,
            'waitlist': waitlisted
        })
    else:
        return jsonify({'error': 'Session not found'}), 404

@app.route('/add_session', methods=['GET', 'POST'])
def add_session():
    if request.method == 'POST':
        date = request.form['date']
        slots = int(request.form['slots'])
        
        new_session = Session(date=date, slots=slots, shuttles_used=0)
        db.session.add(new_session)
        db.session.commit()
        
        return redirect(url_for('index'))
    
    return render_template('add_session.html')


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)  # Allow access from any IP address

