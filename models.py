from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'staff', 'trekker'
    is_active = db.Column(db.Boolean, default=True)  # Admin can deactivate
    is_blacklisted = db.Column(db.Boolean, default=False)  # Admin can blacklist
    
    # Relationships
    profile = db.relationship('StaffProfile', back_populates='user', uselist=False, cascade="all, delete-orphan")
    bookings = db.relationship('Booking', back_populates='user', cascade="all, delete-orphan")
    assigned_treks = db.relationship('Trek', back_populates='staff', foreign_keys='Trek.staff_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


class StaffProfile(db.Model):
    __tablename__ = 'staff_profile'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    contact_details = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'approved', 'blacklisted'
    
    # Relationship
    user = db.relationship('User', back_populates='profile')

    def __repr__(self):
        return f'<StaffProfile UserID={self.user_id} Status={self.status}>'


class Trek(db.Model):
    __tablename__ = 'trek'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)  # 'Easy', 'Moderate', 'Hard'
    duration = db.Column(db.Integer, nullable=False)  # in days
    max_slots = db.Column(db.Integer, nullable=False)
    available_slots = db.Column(db.Integer, nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Assigned staff
    status = db.Column(db.String(20), default='Pending')  # 'Pending', 'Approved', 'Open', 'Closed', 'Completed'
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    
    # Relationships
    staff = db.relationship('User', back_populates='assigned_treks', foreign_keys=[staff_id])
    bookings = db.relationship('Booking', back_populates='trek', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Trek {self.name} (Slots: {self.available_slots}/{self.max_slots})>'


class Booking(db.Model):
    __tablename__ = 'booking'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    trek_id = db.Column(db.Integer, db.ForeignKey('trek.id'), nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Booked')  # 'Booked', 'Cancelled', 'Completed'
    
    # Relationships
    user = db.relationship('User', back_populates='bookings')
    trek = db.relationship('Trek', back_populates='bookings')

    def __repr__(self):
        return f'<Booking ID={self.id} User={self.user_id} Trek={self.trek_id} Status={self.status}>'
