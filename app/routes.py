from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.models import User, Complaint, Category, ComplaintUpdate

main = Blueprint('main', __name__)

# ── Home ──────────────────────────────────────────────────────────
@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))

# ── Register ─────────────────────────────────────────────────────
@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'complainant')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with that email already exists.', 'danger')
            return redirect(url_for('main.register'))

        hashed_password = generate_password_hash(password)
        new_user = User(
            full_name=full_name,
            email=email,
            password=hashed_password,
            role=role
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully. Please log in.', 'success')
        return redirect(url_for('main.login'))

    return render_template('register.html')

# ── Login ─────────────────────────────────────────────────────────
@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, password):
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('main.login'))

        login_user(user)
        return redirect(url_for('main.dashboard'))

    return render_template('login.html')

# ── Logout ────────────────────────────────────────────────────────
@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

# ── Dashboard ─────────────────────────────────────────────────────
@main.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'complainant':
        complaints = Complaint.query.filter_by(user_id=current_user.id).all()
        return render_template('complainant_dashboard.html', complaints=complaints)

    elif current_user.role == 'officer':
        complaints = Complaint.query.filter_by(assigned_to=current_user.id).all()
        return render_template('officer_dashboard.html', complaints=complaints)

    elif current_user.role == 'admin':
        complaints = Complaint.query.all()
        users = User.query.all()
        return render_template('admin_dashboard.html', complaints=complaints, users=users)

    elif current_user.role == 'management':
        from sqlalchemy import func
        from datetime import datetime, timedelta

        total = Complaint.query.count()
        resolved = Complaint.query.filter_by(status='resolved').count()
        pending = Complaint.query.filter_by(status='submitted').count()

        categories = Category.query.all()
        category_labels = [c.name for c in categories]
        category_data = [
            Complaint.query.filter_by(category_id=c.id).count()
            for c in categories
        ]

        month_labels = []
        month_data = []
        for i in range(5, -1, -1):
            date = datetime.utcnow().replace(day=1) - timedelta(days=i*30)
            label = date.strftime('%b %Y')
            count = Complaint.query.filter(
                func.year(Complaint.submitted_at) == date.year,
                func.month(Complaint.submitted_at) == date.month
            ).count()
            month_labels.append(label)
            month_data.append(count)

        return render_template('management_dashboard.html',
                               total=total, resolved=resolved, pending=pending,
                               category_labels=category_labels,
                               category_data=category_data,
                               month_labels=month_labels,
                               month_data=month_data)

    return redirect(url_for('main.login'))
# ── Submit Complaint ──────────────────────────────────────────────
@main.route('/submit-complaint', methods=['GET', 'POST'])
@login_required
def submit_complaint():
    categories = Category.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category_id = request.form.get('category_id') or None
        priority = request.form.get('priority', 'normal')

        complaint = Complaint(
            title=title,
            description=description,
            category_id=category_id,
            priority=priority,
            user_id=current_user.id
        )
        db.session.add(complaint)
        db.session.commit()
        flash('Your complaint has been submitted successfully.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('submit_complaint.html', categories=categories)

# ── My Complaints ─────────────────────────────────────────────────
@main.route('/my-complaints')
@login_required
def my_complaints():
    complaints = Complaint.query.filter_by(user_id=current_user.id).all()
    return render_template('my_complaints.html', complaints=complaints)

# ── View Complaint ────────────────────────────────────────────────
@main.route('/complaint/<int:complaint_id>', methods=['GET', 'POST'])
@login_required
def view_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    officers = User.query.filter_by(role='officer').all()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_status':
            new_status = request.form.get('status')
            note = request.form.get('note')
            complaint.status = new_status
            update = ComplaintUpdate(
                complaint_id=complaint.id,
                updated_by=current_user.id,
                note=note,
                new_status=new_status
            )
            db.session.add(update)
            db.session.commit()
            flash('Complaint updated successfully.', 'success')

        elif action == 'assign':
            officer_id = request.form.get('officer_id')
            complaint.assigned_to = officer_id
            complaint.status = 'under_review'
            update = ComplaintUpdate(
                complaint_id=complaint.id,
                updated_by=current_user.id,
                note=f'Complaint assigned to officer.',
                new_status='under_review'
            )
            db.session.add(update)
            db.session.commit()
            flash('Complaint assigned successfully.', 'success')

        return redirect(url_for('main.view_complaint', complaint_id=complaint.id))

    return render_template('view_complaint.html', complaint=complaint, officers=officers)

# ── All Complaints (Admin) ────────────────────────────────────────
@main.route('/all-complaints')
@login_required
def all_complaints():
    if current_user.role not in ['admin', 'management']:
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))
    complaints = Complaint.query.order_by(Complaint.submitted_at.desc()).all()
    return render_template('all_complaints.html', complaints=complaints)

# ── Manage Users (Admin) ──────────────────────────────────────────
@main.route('/manage-users')
@login_required
def manage_users():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))
    users = User.query.all()
    return render_template('manage_users.html', users=users)

# ── Manage Categories (Admin) ─────────────────────────────────────
@main.route('/manage-categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        category = Category(name=name, description=description)
        db.session.add(category)
        db.session.commit()
        flash('Category added successfully.', 'success')
        return redirect(url_for('main.manage_categories'))

    categories = Category.query.all()
    return render_template('manage_categories.html', categories=categories)

# ── Analytics (Management) ────────────────────────────────────────
@main.route('/analytics')
@login_required
def analytics():
    if current_user.role != 'management':
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.dashboard'))

# ── Assigned Complaints (Officer) ─────────────────────────────────
@main.route('/assigned-complaints')
@login_required
def assigned_complaints():
    if current_user.role != 'officer':
        flash('Access denied.', 'danger')
        return redirect(url_for('main.dashboard'))
    complaints = Complaint.query.filter_by(assigned_to=current_user.id).all()
    return render_template('officer_dashboard.html', complaints=complaints)