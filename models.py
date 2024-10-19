from extensions import db
from flask_login import UserMixin
from flask_bcrypt import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

# Define the association table for waitlist
waitlist = db.Table('waitlist',
                    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
                    db.Column('session_id', db.Integer,
                              db.ForeignKey('session.id'))
                    )

# Define the association table for confirmed participants (poll)
poll = db.Table('poll',
                db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
                db.Column('session_id', db.Integer,
                          db.ForeignKey('session.id')),
                extend_existing=True  # Ensure no conflicts when re-defining the table
                )


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    # New display_name field
    display_name = db.Column(db.String(50), nullable=False)

    sessions = db.relationship(
        'Session', secondary='poll', back_populates='users')
    waitlisted_sessions = db.relationship(
        'Session', secondary='waitlist', back_populates='waitlist')

    # Set password (used during registration)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password).decode('utf-8')

    # Check password (used during login)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # String representation of the user (for debugging)
    def __repr__(self):
        return f'<User {self.email}>'


class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    slots = db.Column(db.Integer, nullable=False)

    # Relationship with users
    users = db.relationship('User', secondary='poll',
                            back_populates='sessions')
    waitlist = db.relationship(
        'User', secondary='waitlist', back_populates='waitlisted_sessions')

    @property
    def is_locked(self):
        lock_time = datetime.combine(
            # datetime for 8pm night before session
            self.date - timedelta(days=1), datetime.min.time()) + timedelta(hours=20)
            # date for testing
            # self.date - timedelta(days=1), datetime.min.time()) + timedelta(hours=15) + timedelta(minutes=36)
        return datetime.now() >= lock_time


class Fee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'))
    amount_owed = db.Column(db.Float, nullable=False)
