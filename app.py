"""
PancrePal - Diabetes Companion Web App
Iteration 5: Advanced Features

US-21: Doctor-Ready Export (PDF + CSV)
US-22: Carbohydrate Tracking
US-23: Advanced Analytics & Metrics

FIXED: Weekly consistency calculation added to dashboard
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, send_file, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import os

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'

# SQLAlchemy configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pancrepal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Import db after app is created
from db import db, User, LogEntry, UserProgress
from gamification import update_streak, check_and_award_badges, get_daily_tip, should_show_reminder
from analytics import calculate_advanced_metrics, identify_recurring_patterns, generate_weekly_suggestion, get_metric_explanation
from exports import generate_csv_export, generate_pdf_report

# Initialize database with app
db.init_app(app)

# Create tables if they don't exist
with app.app_context():
    db.create_all()

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        # Validation
        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('register.html')

        if password != password_confirm:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with this email already exists.', 'error')
            return render_template('register.html')

        # Create user
        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Create user progress record
        progress = UserProgress(user_id=user.id)
        db.session.add(progress)
        db.session.commit()

        login_user(user)
        flash('Account created successfully! Welcome to PancrePal.', 'success')
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login page."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('login.html')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash('Welcome back!', 'success')

            # Redirect to next page if specified, otherwise dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Log out current user."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ============================================================================
# MAIN APPLICATION ROUTES
# ============================================================================

@app.route('/')
@login_required
def index():
    """
    Dashboard - main page showing glucose trends and insights.
    US-23: Now includes advanced analytics and metrics.
    FIXED: Weekly consistency calculation added.
    """
    user_id = current_user.id

    # Get recent entries (last 30 days for better analytics)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    entries = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        LogEntry.timestamp >= thirty_days_ago
    ).order_by(LogEntry.timestamp.desc()).all()

    # Get user progress
    progress = UserProgress.query.filter_by(user_id=user_id).first()
    if not progress:
        progress = UserProgress(user_id=user_id)
        db.session.add(progress)
        db.session.commit()

    # Check and update streak for today
    if entries:
        today = datetime.now().date()
        latest_entry_date = entries[0].timestamp.date()
        if latest_entry_date == today:
            update_streak(user_id, today)

    # FIXED: Calculate weekly consistency (days logged in last 7 days)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_entries = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        LogEntry.timestamp >= seven_days_ago
    ).all()

    # Count unique days with entries
    unique_days = set()
    for entry in recent_entries:
        unique_days.add(entry.timestamp.date())

    weekly_consistency = round((len(unique_days) / 7) * 100, 1)  # Percentage rounded to 1 decimal

    # Get daily tip
    daily_tip = get_daily_tip()

    # Check if reminder should be shown
    reminder = should_show_reminder(user_id)

    # US-23: Calculate advanced metrics
    advanced_metrics = calculate_advanced_metrics(entries) if entries else None

    # Get patterns and suggestions
    patterns = identify_recurring_patterns(entries) if entries else []
    suggestion = generate_weekly_suggestion(entries) if entries else None

    # Prepare chart data (US-22: includes carbs)
    chart_data = {
        'labels': [],
        'glucose': [],
        'carbs': [],  # US-22
        'mood': []
    }

    for entry in reversed(entries[:30]):  # Last 30 entries, oldest to newest for chart
        chart_data['labels'].append(entry.timestamp.strftime('%d/%m'))  # FIXED: DD/MM format
        chart_data['glucose'].append(entry.blood_glucose)
        chart_data['carbs'].append(entry.carbs_grams if entry.carbs_grams is not None else 0)  # US-22
        # Convert mood to numeric
        mood_map = {'happy': 5, 'calm': 4, 'stressed': 3, 'tired': 2, 'frustrated': 1}
        chart_data['mood'].append(mood_map.get(entry.mood, 3))

    return render_template(
        'index.html',
        entries=entries[:10],  # Show 10 most recent on dashboard
        progress=progress.to_dict(),
        weekly_consistency=weekly_consistency,  # FIXED: Pass to template
        advanced_metrics=advanced_metrics,  # US-23
        patterns=patterns,
        suggestion=suggestion,
        daily_tip=daily_tip,
        chart_data=chart_data,
        reminder=reminder
    )


@app.route('/log', methods=['GET', 'POST'])
@login_required
def log_entry():
    """
    Quick log page for adding glucose entries.
    US-22: Now includes carbohydrate tracking.
    """
    if request.method == 'POST':
        user_id = current_user.id
        glucose_level = request.form.get('glucose_level')
        meal_type = request.form.get('meal_type', 'none')
        mood = request.form.get('mood')
        notes = request.form.get('notes', '').strip()
        carbs_grams = request.form.get('carbs_grams', '').strip()  # US-22

        # Validation
        if not glucose_level or not mood:
            flash('Glucose level and mood are required.', 'error')
            return render_template('log.html')

        try:
            glucose_level = float(glucose_level)
            if glucose_level < 2.0 or glucose_level > 30.0:
                flash('Glucose level must be between 2.0 and 30.0 mmol/L.', 'error')
                return render_template('log.html')
        except ValueError:
            flash('Invalid glucose level.', 'error')
            return render_template('log.html')

        # US-22: Validate carbs if provided
        carbs_value = None
        if carbs_grams:
            try:
                carbs_value = int(carbs_grams)
                if carbs_value < 0 or carbs_value > 500:
                    flash('Carbs must be between 0 and 500 grams.', 'error')
                    return render_template('log.html')
            except ValueError:
                flash('Invalid carbs value. Please enter a whole number.', 'error')
                return render_template('log.html')

        # Add entry
        entry = LogEntry(
            user_id=user_id,
            blood_glucose=glucose_level,
            meal_type=meal_type,
            mood=mood,
            notes=notes,
            carbs_grams=carbs_value  # US-22
        )
        db.session.add(entry)
        db.session.commit()

        # Update streak with today's date
        today = datetime.now().date()
        update_streak(user_id, today)

        # Get user progress to check for new badges
        progress = UserProgress.query.filter_by(user_id=user_id).first()
        if progress:
            newly_earned = check_and_award_badges(progress)

            # Flash message for badges
            if newly_earned:
                for badge in newly_earned:
                    flash(f'🏆 Badge earned: {badge["name"]}!', 'success')

        flash('Entry logged successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('log.html')


# ============================================================================
# US-21: EXPORT ROUTES
# ============================================================================

@app.route('/export/csv')
@login_required
def export_csv():
    """
    Export user data as CSV file.
    US-21: Doctor-ready CSV export.
    """
    user_id = current_user.id
    days = request.args.get('days', 30, type=int)

    # Get entries for specified period
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    entries = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        LogEntry.timestamp >= cutoff_date
    ).order_by(LogEntry.timestamp.desc()).all()

    if not entries:
        flash('No data available for export.', 'error')
        return redirect(url_for('index'))

    # Generate CSV
    csv_data = generate_csv_export(entries)

    # Create response
    response = make_response(csv_data)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=pancrepal_data_{days}days_{datetime.now().strftime("%Y%m%d")}.csv'

    return response


@app.route('/export/pdf')
@login_required
def export_pdf():
    """
    Export comprehensive PDF report for healthcare providers.
    US-21: Professional medical report with charts and analytics.
    """
    user_id = current_user.id
    days = request.args.get('days', 30, type=int)

    # Get entries for specified period
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    entries = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        LogEntry.timestamp >= cutoff_date
    ).order_by(LogEntry.timestamp.desc()).all()

    if not entries:
        flash('No data available for export.', 'error')
        return redirect(url_for('index'))

    # Generate PDF
    pdf_buffer = generate_pdf_report(current_user.email, entries, days)

    # Send file
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f'pancrepal_report_{days}days_{datetime.now().strftime("%Y%m%d")}.pdf',
        mimetype='application/pdf'
    )


# ============================================================================
# US-23: ANALYTICS ROUTES
# ============================================================================

@app.route('/analytics')
@login_required
def analytics():
    """
    Detailed analytics page with all metrics and explanations.
    US-23: Advanced analytics dashboard.
    """
    user_id = current_user.id
    days = request.args.get('days', 30, type=int)

    # Get entries for specified period
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    entries = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        LogEntry.timestamp >= cutoff_date
    ).order_by(LogEntry.timestamp.desc()).all()

    if not entries:
        flash('No data available for analysis. Start logging to see insights!', 'info')
        return redirect(url_for('index'))

    # Calculate metrics
    metrics = calculate_advanced_metrics(entries)
    patterns = identify_recurring_patterns(entries)
    suggestion = generate_weekly_suggestion(entries)

    # Get metric explanations
    explanations = {
        'time_in_range': get_metric_explanation('time_in_range'),
        'coefficient_of_variation': get_metric_explanation('coefficient_of_variation'),
        'hypo_events': get_metric_explanation('hypo_events'),
        'hyper_events': get_metric_explanation('hyper_events'),
        'avg_glucose': get_metric_explanation('avg_glucose'),
        'avg_daily_carbs': get_metric_explanation('avg_daily_carbs')
    }

    return render_template(
        'analytics.html',
        metrics=metrics,
        patterns=patterns,
        suggestion=suggestion,
        explanations=explanations,
        days=days
    )


@app.route('/avatar')
@login_required
def avatar():
    """Avatar customization page."""
    user_id = current_user.id
    progress = UserProgress.query.filter_by(user_id=user_id).first()

    if not progress:
        progress = UserProgress(user_id=user_id)
        db.session.add(progress)
        db.session.commit()

    # Get available avatars
    available_avatars = ['default']
    unlocked = progress.get_unlocked_avatars()
    available_avatars.extend([a for a in unlocked if a != 'default'])

    return render_template('avatar.html', progress=progress.to_dict(), avatars=available_avatars)


@app.route('/avatar/update', methods=['POST'])
@login_required
def update_avatar():
    """Update user's avatar selection."""
    user_id = current_user.id
    avatar_id = request.form.get('avatar_id')

    if avatar_id:
        progress = UserProgress.query.filter_by(user_id=user_id).first()
        if progress:
            progress.selected_avatar = avatar_id
            db.session.commit()
            flash('Avatar updated!', 'success')

    return redirect(url_for('avatar'))


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """User settings page."""
    if request.method == 'POST':
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings'))

    user_id = current_user.id
    progress = UserProgress.query.filter_by(user_id=user_id).first()

    if not progress:
        progress = UserProgress(user_id=user_id)
        db.session.add(progress)
        db.session.commit()

    return render_template('settings.html', progress=progress.to_dict())


@app.route('/ethics')
def ethics():
    """Data Ethics & Privacy page - accessible without login."""
    return render_template('ethics.html')


# ============================================================================
# API ROUTES (for future mobile app integration)
# ============================================================================

@app.route('/api/entries', methods=['GET'])
@login_required
def api_entries():
    """API endpoint to get user's entries."""
    user_id = current_user.id
    days = request.args.get('days', 30, type=int)

    cutoff_date = datetime.utcnow() - timedelta(days=days)
    entries = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        LogEntry.timestamp >= cutoff_date
    ).order_by(LogEntry.timestamp.desc()).all()

    return jsonify([e.to_dict() for e in entries])


@app.route('/api/progress', methods=['GET'])
@login_required
def api_progress():
    """API endpoint to get user's progress."""
    user_id = current_user.id
    progress = UserProgress.query.filter_by(user_id=user_id).first()

    if not progress:
        return jsonify({'error': 'No progress found'}), 404

    return jsonify(progress.to_dict())


@app.route('/api/metrics', methods=['GET'])
@login_required
def api_metrics():
    """
    API endpoint to get advanced metrics.
    US-23: Expose analytics via API.
    """
    user_id = current_user.id
    days = request.args.get('days', 30, type=int)

    cutoff_date = datetime.utcnow() - timedelta(days=days)
    entries = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        LogEntry.timestamp >= cutoff_date
    ).all()

    if not entries:
        return jsonify({'error': 'No data available'}), 404

    metrics = calculate_advanced_metrics(entries)
    return jsonify(metrics)


# ============================================================================
# PWA ROUTES
# ============================================================================

@app.route('/manifest.json')
def manifest():
    """Serve PWA manifest file."""
    return send_from_directory('static', 'manifest.json')


@app.route('/service-worker.js')
def service_worker():
    """Serve service worker file."""
    return send_from_directory('static', 'service-worker.js')


@app.route('/apple-touch-icon.png')
def apple_touch_icon():
    """Serve Apple touch icon for iOS."""
    return send_from_directory('static/icons', 'icon-192x192.png')


@app.route('/favicon.ico')
def favicon():
    """Serve favicon."""
    return send_from_directory('static/icons', 'icon-192x192.png')


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    """Handle 500 errors."""
    return render_template('500.html'), 500


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
else:
    with app.app_context():
        db.create_all()