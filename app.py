import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, StaffProfile, Trek, Booking
from datetime import datetime, date

app = Flask(__name__)

# Basic Config
app.config['SECRET_KEY'] = 'treksync-secret-key-12345'
# Database inside workspace
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trekking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database and seed admin programmatically
with app.app_context():
    db.create_all()
    # Check if admin already exists
    admin_user = User.query.filter_by(role='admin').first()
    if not admin_user:
        admin = User(
            username='admin',
            email='admin@treksync.com',
            role='admin',
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Pre-existing Admin seeded: username='admin', password='admin123'")

# Routes

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        username = request.form.get('username').strip()
        email = request.form.get('email').strip()
        role = request.form.get('role')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        contact_details = request.form.get('contact_details', '').strip()
        
        # Validation
        if not username or not email or not password or not confirm_password:
            flash('All required fields must be filled.', 'error')
            return render_template('register.html')
            
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
            
        if User.query.filter_by(username=username).first():
            flash('Username is already taken.', 'error')
            return render_template('register.html')
            
        if User.query.filter_by(email=email).first():
            flash('Email is already registered.', 'error')
            return render_template('register.html')
            
        # Create user
        try:
            user = User(
                username=username,
                email=email,
                role=role,
                is_active=True
            )
            user.set_password(password)
            db.session.add(user)
            
            # If user is staff, create StaffProfile using relationship
            if role == 'staff':
                profile = StaffProfile(
                    user=user,
                    contact_details=contact_details,
                    status='pending'  # Staff starts as pending admin approval
                )
                db.session.add(profile)
                
            db.session.commit()
            
            if role == 'staff':
                flash('Registration successful! Admin approval is required before logging in.', 'success')
            else:
                flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'error')
            return render_template('register.html')
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Redirect to their dashboard
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'staff':
            return redirect(url_for('staff_dashboard'))
        else:
            return redirect(url_for('trekker_dashboard'))
            
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            flash('Invalid username or password.', 'error')
            return render_template('login.html')
            
        if not user.is_active or user.is_blacklisted:
            flash('Your account has been deactivated or blacklisted.', 'error')
            return render_template('login.html')
            
        login_user(user)
        flash('Successfully logged in!', 'success')
        
        # Redirect based on role
        if user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif user.role == 'staff':
            # Check staff profile status
            profile = StaffProfile.query.filter_by(user_id=user.id).first()
            if profile and profile.status == 'pending':
                return redirect(url_for('pending_approval'))
            elif profile and profile.status == 'blacklisted':
                logout_user()
                flash('Your staff registration has been blacklisted.', 'error')
                return redirect(url_for('login'))
            return redirect(url_for('staff_dashboard'))
        else:
            return redirect(url_for('trekker_dashboard'))
            
    return render_template('login.html')

@app.route('/pending-approval')
@login_required
def pending_approval():
    if current_user.role != 'staff':
        return redirect(url_for('home'))
    profile = StaffProfile.query.filter_by(user_id=current_user.id).first()
    if profile and profile.status == 'approved':
        return redirect(url_for('staff_dashboard'))
    return render_template('pending_approval.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

# Placeholder routes for Milestone 2 testing

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('home'))
    # Placeholder response
    return f"<h1>Admin Dashboard</h1><p>Welcome, {current_user.username}!</p><a href='/logout'>Logout</a>"

@app.route('/staff/dashboard')
@login_required
def staff_dashboard():
    if current_user.role != 'staff':
        flash('Access denied.', 'error')
        return redirect(url_for('home'))
        
    profile = StaffProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or profile.status != 'approved':
        return redirect(url_for('pending_approval'))
        
    # Placeholder response
    return f"<h1>Staff Dashboard</h1><p>Welcome, {current_user.username}! (Approved)</p><a href='/logout'>Logout</a>"

@app.route('/trekker/dashboard')
@login_required
def trekker_dashboard():
    if current_user.role != 'trekker':
        flash('Access denied.', 'error')
        return redirect(url_for('home'))
    # Placeholder response
    return f"<h1>Trekker Dashboard</h1><p>Welcome, {current_user.username}!</p><a href='/logout'>Logout</a>"

if __name__ == '__main__':
    app.run(debug=True)
