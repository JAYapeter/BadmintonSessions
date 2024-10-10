from extensions import db

# Define the association table for waitlist
waitlist = db.Table('waitlist',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('session_id', db.Integer, db.ForeignKey('session.id'))
)

# Define the association table for confirmed participants (poll)
poll = db.Table('poll',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('session_id', db.Integer, db.ForeignKey('session.id')),
    extend_existing=True  # Ensure no conflicts when re-defining the table
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    
    # Relationship with sessions as confirmed participants
    sessions = db.relationship('Session', secondary=poll, back_populates='users')
    
    # Relationship with sessions as waitlisted participants
    waitlisted_sessions = db.relationship('Session', secondary=waitlist, back_populates='waitlist')

class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(100), nullable=False)
    slots = db.Column(db.Integer, nullable=False)
    shuttles_used = db.Column(db.Integer, default=0)
    
    # Confirmed participants
    users = db.relationship('User', secondary=poll, back_populates='sessions')
    
    # Waitlisted participants
    waitlist = db.relationship('User', secondary=waitlist, back_populates='waitlisted_sessions')

class Fee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'))
    amount_owed = db.Column(db.Float, nullable=False)
