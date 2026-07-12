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

from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access denied. Admin role required.', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    stats = {
        'total_treks': Trek.query.count(),
        'total_trekkers': User.query.filter_by(role='trekker').count(),
        'total_staff': User.query.filter_by(role='staff').count(),
        'total_bookings': Booking.query.count()
    }
    pending_staff = StaffProfile.query.filter_by(status='pending').all()
    recent_bookings = Booking.query.order_by(Booking.booking_date.desc()).limit(5).all()
    
    # Fetch trek booking statistics for charts
    trek_stats = db.session.query(
        Trek.name, 
        db.func.count(Booking.id)
    ).outerjoin(Booking, (Booking.trek_id == Trek.id) & (Booking.status == 'Booked')).group_by(Trek.id).all()
    
    trek_labels = [s[0] for s in trek_stats]
    trek_counts = [s[1] for s in trek_stats]
    
    return render_template(
        'admin/dashboard.html', 
        stats=stats, 
        pending_staff=pending_staff, 
        recent_bookings=recent_bookings,
        trek_labels=trek_labels,
        trek_counts=trek_counts
    )

@app.route('/admin/staff')
@login_required
@admin_required
def admin_staff():
    search_query = request.args.get('q', '').strip()
    filter_status = request.args.get('status', '').strip()
    
    query = StaffProfile.query.join(User)
    
    if search_query:
        # Search by staff username or ID
        if search_query.isdigit():
            query = query.filter((User.username.like(f"%{search_query}%")) | (StaffProfile.id == int(search_query)))
        else:
            query = query.filter(User.username.like(f"%{search_query}%"))
            
    if filter_status:
        query = query.filter(StaffProfile.status == filter_status)
        
    staff_profiles = query.all()
    return render_template('admin/staff.html', staff_profiles=staff_profiles, search_query=search_query, filter_status=filter_status)

@app.route('/admin/staff/approve/<int:profile_id>', methods=['POST'])
@login_required
@admin_required
def admin_approve_staff(profile_id):
    profile = StaffProfile.query.get_or_404(profile_id)
    profile.status = 'approved'
    profile.user.is_active = True
    profile.user.is_blacklisted = False
    db.session.commit()
    flash(f'Staff member {profile.user.username} approved successfully.', 'success')
    return redirect(request.referrer or url_for('admin_staff'))

@app.route('/admin/staff/blacklist/<int:profile_id>', methods=['POST'])
@login_required
@admin_required
def admin_blacklist_staff(profile_id):
    profile = StaffProfile.query.get_or_404(profile_id)
    profile.status = 'blacklisted'
    profile.user.is_blacklisted = True
    db.session.commit()
    flash(f'Staff member {profile.user.username} has been blacklisted.', 'success')
    return redirect(request.referrer or url_for('admin_staff'))

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    search_query = request.args.get('q', '').strip()
    filter_status = request.args.get('status', '').strip()
    
    query = User.query.filter_by(role='trekker')
    
    if search_query:
        if search_query.isdigit():
            query = query.filter((User.username.like(f"%{search_query}%")) | (User.id == int(search_query)))
        else:
            query = query.filter(User.username.like(f"%{search_query}%"))
            
    if filter_status == 'active':
        query = query.filter(User.is_active == True, User.is_blacklisted == False)
    elif filter_status == 'deactivated':
        query = query.filter(User.is_active == False, User.is_blacklisted == False)
    elif filter_status == 'blacklisted':
        query = query.filter(User.is_blacklisted == True)
        
    users = query.all()
    return render_template('admin/users.html', users=users, search_query=search_query, filter_status=filter_status)

@app.route('/admin/users/toggle_active/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    status_str = "activated" if user.is_active else "deactivated"
    flash(f'User {user.username} has been {status_str}.', 'success')
    return redirect(request.referrer or url_for('admin_users'))

@app.route('/admin/users/blacklist/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_blacklist_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_blacklisted = True
    user.is_active = False
    db.session.commit()
    flash(f'User {user.username} has been blacklisted.', 'success')
    return redirect(request.referrer or url_for('admin_users'))

@app.route('/admin/users/unblacklist/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_unblacklist_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_blacklisted = False
    user.is_active = True
    db.session.commit()
    flash(f'User {user.username} unblacklisted successfully.', 'success')
    return redirect(request.referrer or url_for('admin_users'))

@app.route('/admin/treks')
@login_required
@admin_required
def admin_treks():
    search_query = request.args.get('q', '').strip()
    filter_difficulty = request.args.get('difficulty', '').strip()
    filter_status = request.args.get('status', '').strip()
    
    query = Trek.query
    
    if search_query:
        if search_query.isdigit():
            query = query.filter((Trek.name.like(f"%{search_query}%")) | (Trek.location.like(f"%{search_query}%")) | (Trek.id == int(search_query)))
        else:
            query = query.filter((Trek.name.like(f"%{search_query}%")) | (Trek.location.like(f"%{search_query}%")))
            
    if filter_difficulty:
        query = query.filter(Trek.difficulty == filter_difficulty)
    if filter_status:
        query = query.filter(Trek.status == filter_status)
        
    treks = query.all()
    return render_template('admin/treks.html', treks=treks, search_query=search_query, filter_difficulty=filter_difficulty, filter_status=filter_status)

@app.route('/admin/treks/create', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_create_trek():
    approved_staff = StaffProfile.query.filter_by(status='approved').all()
    
    if request.method == 'POST':
        name = request.form.get('name').strip()
        location = request.form.get('location').strip()
        difficulty = request.form.get('difficulty')
        duration = int(request.form.get('duration'))
        max_slots = int(request.form.get('max_slots'))
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        staff_id = request.form.get('staff_id')
        status = request.form.get('status', 'Pending')
        
        # Parse dates
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format.', 'error')
            return render_template('admin/trek_form.html', approved_staff=approved_staff, trek=None)
            
        if start_date > end_date:
            flash('Start date cannot be after end date.', 'error')
            return render_template('admin/trek_form.html', approved_staff=approved_staff, trek=None)
            
        # Create Trek
        trek = Trek(
            name=name,
            location=location,
            difficulty=difficulty,
            duration=duration,
            max_slots=max_slots,
            available_slots=max_slots,  # Initially all slots available
            status=status,
            start_date=start_date,
            end_date=end_date
        )
        
        if staff_id:
            trek.staff_id = int(staff_id)
            
        db.session.add(trek)
        db.session.commit()
        
        flash('Trek route created successfully!', 'success')
        return redirect(url_for('admin_treks'))
        
    return render_template('admin/trek_form.html', approved_staff=approved_staff, trek=None)

@app.route('/admin/treks/edit/<int:trek_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    approved_staff = StaffProfile.query.filter_by(status='approved').all()
    
    if request.method == 'POST':
        name = request.form.get('name').strip()
        location = request.form.get('location').strip()
        difficulty = request.form.get('difficulty')
        duration = int(request.form.get('duration'))
        max_slots = int(request.form.get('max_slots'))
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        staff_id = request.form.get('staff_id')
        status = request.form.get('status')
        
        # Parse dates
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format.', 'error')
            return render_template('admin/trek_form.html', approved_staff=approved_staff, trek=trek)
            
        if start_date > end_date:
            flash('Start date cannot be after end date.', 'error')
            return render_template('admin/trek_form.html', approved_staff=approved_staff, trek=trek)
            
        # Slots adjustment logic
        active_bookings_count = Booking.query.filter_by(trek_id=trek.id, status='Booked').count()
        if max_slots < active_bookings_count:
            flash(f'Cannot set max slots to {max_slots} because there are already {active_bookings_count} active bookings.', 'error')
            return render_template('admin/trek_form.html', approved_staff=approved_staff, trek=trek)
            
        trek.name = name
        trek.location = location
        trek.difficulty = difficulty
        trek.duration = duration
        trek.max_slots = max_slots
        trek.available_slots = max_slots - active_bookings_count
        trek.status = status
        trek.start_date = start_date
        trek.end_date = end_date
        
        if staff_id:
            trek.staff_id = int(staff_id)
        else:
            trek.staff_id = None
            
        db.session.commit()
        flash('Trek details updated successfully.', 'success')
        return redirect(url_for('admin_treks'))
        
    return render_template('admin/trek_form.html', approved_staff=approved_staff, trek=trek)

@app.route('/admin/treks/delete/<int:trek_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    db.session.delete(trek)
    db.session.commit()
    flash('Trek route deleted successfully.', 'success')
    return redirect(url_for('admin_treks'))

@app.route('/admin/bookings')
@login_required
@admin_required
def admin_bookings():
    search_query = request.args.get('q', '').strip()
    filter_status = request.args.get('status', '').strip()
    
    query = Booking.query.join(User).join(Trek)
    
    if search_query:
        if search_query.isdigit():
            query = query.filter((User.username.like(f"%{search_query}%")) | (Trek.name.like(f"%{search_query}%")) | (Booking.id == int(search_query)))
        else:
            query = query.filter((User.username.like(f"%{search_query}%")) | (Trek.name.like(f"%{search_query}%")))
            
    if filter_status:
        query = query.filter(Booking.status == filter_status)
        
    bookings = query.order_by(Booking.booking_date.desc()).all()
    return render_template('admin/bookings.html', bookings=bookings, search_query=search_query, filter_status=filter_status)

def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'staff':
            flash('Access denied. Staff role required.', 'error')
            return redirect(url_for('home'))
        
        # Verify approval
        profile = StaffProfile.query.filter_by(user_id=current_user.id).first()
        if not profile or profile.status != 'approved':
            return redirect(url_for('pending_approval'))
            
        return f(*args, **kwargs)
    return decorated_function

@app.route('/staff/dashboard')
@login_required
@staff_required
def staff_dashboard():
    treks = Trek.query.filter_by(staff_id=current_user.id).all()
    
    # Calculate total participants across all assigned treks
    total_participants = 0
    for trek in treks:
        total_participants += Booking.query.filter_by(trek_id=trek.id, status='Booked').count()
        
    return render_template('staff/dashboard.html', treks=treks, total_participants=total_participants)

@app.route('/staff/assigned-treks')
@login_required
@staff_required
def staff_assigned_treks():
    treks = Trek.query.filter_by(staff_id=current_user.id).all()
    return render_template('staff/assigned_treks.html', treks=treks)

@app.route('/staff/trek/<int:trek_id>')
@login_required
@staff_required
def staff_trek_detail(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    
    # Access control: Ensure this trek is assigned to the current staff member
    if trek.staff_id != current_user.id:
        flash('Access denied. You are not assigned to manage this trek.', 'error')
        return redirect(url_for('staff_dashboard'))
        
    bookings = Booking.query.filter_by(trek_id=trek.id).order_by(Booking.booking_date.desc()).all()
    booked_count = Booking.query.filter_by(trek_id=trek.id, status='Booked').count()
    
    return render_template('staff/trek_detail.html', trek=trek, bookings=bookings, booked_count=booked_count)

@app.route('/staff/trek/<int:trek_id>/update', methods=['POST'])
@login_required
@staff_required
def staff_update_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    
    if trek.staff_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('staff_dashboard'))
        
    available_slots = int(request.form.get('available_slots'))
    status = request.form.get('status')
    
    booked_count = Booking.query.filter_by(trek_id=trek.id, status='Booked').count()
    max_allowed_slots = trek.max_slots - booked_count
    
    if available_slots < 0 or available_slots > max_allowed_slots:
        flash(f'Invalid slots number. Available slots must be between 0 and {max_allowed_slots}.', 'error')
        return redirect(url_for('staff_trek_detail', trek_id=trek.id))
        
    trek.available_slots = available_slots
    trek.status = status
    db.session.commit()
    
    flash('Trek details updated successfully.', 'success')
    return redirect(url_for('staff_trek_detail', trek_id=trek.id))

@app.route('/staff/trek/<int:trek_id>/start', methods=['POST'])
@login_required
@staff_required
def staff_start_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    
    if trek.staff_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('staff_dashboard'))
        
    trek.status = 'Started'
    trek.available_slots = 0  # Close booking when trek starts
    db.session.commit()
    
    flash('Expedition has started! Bookings are now closed.', 'success')
    return redirect(url_for('staff_trek_detail', trek_id=trek.id))

@app.route('/staff/trek/<int:trek_id>/complete', methods=['POST'])
@login_required
@staff_required
def staff_complete_trek(trek_id):
    trek = Trek.query.get_or_404(trek_id)
    
    if trek.staff_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('staff_dashboard'))
        
    trek.status = 'Completed'
    trek.available_slots = 0
    
    # Mark all active bookings for this trek as completed
    active_bookings = Booking.query.filter_by(trek_id=trek.id, status='Booked').all()
    for booking in active_bookings:
        booking.status = 'Completed'
        
    db.session.commit()
    
    flash('Expedition marked as completed successfully. Participant records updated.', 'success')
    return redirect(url_for('staff_trek_detail', trek_id=trek.id))

@app.route('/trekker/dashboard')
@login_required
def trekker_dashboard():
    if current_user.role != 'trekker':
        flash('Access denied. Trekker role required.', 'error')
        return redirect(url_for('home'))
        
    search_query = request.args.get('q', '').strip()
    filter_difficulty = request.args.get('difficulty', '').strip()
    
    # Query open treks
    trek_query = Trek.query.filter_by(status='Open')
    
    if search_query:
        trek_query = trek_query.filter((Trek.name.like(f"%{search_query}%")) | (Trek.location.like(f"%{search_query}%")))
    if filter_difficulty:
        trek_query = trek_query.filter(Trek.difficulty == filter_difficulty)
        
    treks = trek_query.all()
    
    # Get stats for current user
    active_bookings_count = Booking.query.filter_by(user_id=current_user.id, status='Booked').count()
    completed_bookings_count = Booking.query.filter_by(user_id=current_user.id, status='Completed').count()
    
    # Active booking trek IDs to prevent duplicate booking
    booked_trek_ids = [b.trek_id for b in Booking.query.filter_by(user_id=current_user.id, status='Booked').all()]
    
    return render_template(
        'trekker/dashboard.html', 
        treks=treks, 
        active_bookings_count=active_bookings_count, 
        completed_bookings_count=completed_bookings_count,
        booked_trek_ids=booked_trek_ids,
        search_query=search_query,
        filter_difficulty=filter_difficulty
    )

@app.route('/trekker/bookings')
@login_required
def trekker_bookings():
    if current_user.role != 'trekker':
        flash('Access denied.', 'error')
        return redirect(url_for('home'))
    bookings = Booking.query.filter_by(user_id=current_user.id, status='Booked').order_by(Booking.booking_date.desc()).all()
    return render_template('trekker/bookings.html', bookings=bookings)

@app.route('/trekker/history')
@login_required
def trekker_history():
    if current_user.role != 'trekker':
        flash('Access denied.', 'error')
        return redirect(url_for('home'))
    bookings = Booking.query.filter(
        Booking.user_id == current_user.id, 
        Booking.status.in_(['Cancelled', 'Completed'])
    ).order_by(Booking.booking_date.desc()).all()
    return render_template('trekker/history.html', bookings=bookings)

@app.route('/trekker/trek/<int:trek_id>')
@login_required
def trekker_trek_detail(trek_id):
    if current_user.role != 'trekker':
        flash('Access denied.', 'error')
        return redirect(url_for('home'))
        
    trek = Trek.query.get_or_404(trek_id)
    # Check if this trekker has an active booking for this trek
    active_booking = Booking.query.filter_by(user_id=current_user.id, trek_id=trek.id, status='Booked').first()
    
    return render_template('trekker/trek_detail.html', trek=trek, active_booking=active_booking)

@app.route('/trekker/book/<int:trek_id>', methods=['POST'])
@login_required
def trekker_book_trek(trek_id):
    if current_user.role != 'trekker':
        flash('Access denied.', 'error')
        return redirect(url_for('home'))
        
    trek = Trek.query.get_or_404(trek_id)
    
    # Validation 1: Trek must be Open
    if trek.status != 'Open':
        flash('Bookings are not open for this trek.', 'error')
        return redirect(url_for('trekker_dashboard'))
        
    # Validation 2: Must have available slots
    if trek.available_slots <= 0:
        flash('No slots available! This trek is sold out.', 'error')
        return redirect(url_for('trekker_dashboard'))
        
    # Validation 3: Prevent duplicate active booking
    duplicate = Booking.query.filter_by(user_id=current_user.id, trek_id=trek.id, status='Booked').first()
    if duplicate:
        flash('You have already booked this trek.', 'error')
        return redirect(url_for('trekker_dashboard'))
        
    try:
        # Create booking
        booking = Booking(
            user_id=current_user.id,
            trek_id=trek.id,
            status='Booked'
        )
        # Decrement slots
        trek.available_slots -= 1
        
        db.session.add(booking)
        db.session.commit()
        
        flash(f'Successfully booked trek: {trek.name}!', 'success')
        return redirect(url_for('trekker_bookings'))
    except Exception as e:
        db.session.rollback()
        flash('An error occurred during booking. Please try again.', 'error')
        return redirect(url_for('trekker_dashboard'))

@app.route('/trekker/cancel/<int:booking_id>', methods=['POST'])
@login_required
def trekker_cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Access control: Ensure this booking belongs to the current user
    if booking.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('trekker_bookings'))
        
    # Booking must be active and trek must be Open
    if booking.status != 'Booked' or booking.trek.status != 'Open':
        flash('This booking cannot be cancelled at this stage.', 'error')
        return redirect(url_for('trekker_bookings'))
        
    try:
        booking.status = 'Cancelled'
        # Restore available slot
        booking.trek.available_slots += 1
        
        db.session.commit()
        flash('Booking cancelled successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred during cancellation.', 'error')
        
    return redirect(url_for('trekker_bookings'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        # Check duplicate email
        existing_user = User.query.filter_by(email=email).first()
        if existing_user and existing_user.id != current_user.id:
            flash('Email address is already in use by another account.', 'error')
            return render_template('profile.html')
            
        try:
            current_user.email = email
                
            # If staff, update profile contact details
            if current_user.role == 'staff':
                profile = StaffProfile.query.filter_by(user_id=current_user.id).first()
                if profile:
                    profile.contact_details = request.form.get('contact_details', '').strip()
                    
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('edit_profile'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating profile.', 'error')
            return render_template('profile.html')
            
    return render_template('profile.html')

@app.route('/api/treks')
def api_treks():
    treks = Trek.query.all()
    data = []
    for t in treks:
        data.append({
            'id': t.id,
            'name': t.name,
            'location': t.location,
            'difficulty': t.difficulty,
            'duration': t.duration,
            'max_slots': t.max_slots,
            'available_slots': t.available_slots,
            'status': t.status,
            'start_date': t.start_date.strftime('%Y-%m-%d'),
            'end_date': t.end_date.strftime('%Y-%m-%d'),
            'guide': t.staff.username if t.staff else None
        })
    return {'treks': data}

@app.route('/api/bookings')
def api_bookings():
    bookings = Booking.query.all()
    data = []
    for b in bookings:
        data.append({
            'id': b.id,
            'user': b.user.username,
            'trek': b.trek.name,
            'booking_date': b.booking_date.strftime('%Y-%m-%d %H:%M:%S'),
            'status': b.status
        })
    return {'bookings': data}

@app.route('/api/users')
def api_users():
    users = User.query.all()
    data = []
    for u in users:
        data.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'role': u.role,
            'is_active': u.is_active,
            'is_blacklisted': u.is_blacklisted
        })
    return {'users': data}

if __name__ == '__main__':
    app.run(debug=True)
