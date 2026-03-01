from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, \
    send_from_directory, send_file, make_response, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import os
import random

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'

# SQLAlchemy configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pancrepal.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Import db after app is created
from db import db, User, LogEntry, UserProgress
from gamification import update_streak, check_and_award_badges, get_daily_tip, should_show_reminder
from analytics import (calculate_advanced_metrics, identify_recurring_patterns,
                       generate_weekly_suggestion, get_metric_explanation,
                       analyze_time_of_day, generate_insights)
from exports import generate_csv_export

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


# ============================================================================
# USER LOADER
# ============================================================================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ============================================================================
# US-26: DEMO MODE CONSTANTS & HELPERS
# ============================================================================

DEMO_USER_EMAIL = 'demo@pancrepal.internal'
DEMO_USER_PASSWORD = 'DemoMode2026!'


def is_demo_mode() -> bool:
    """Return True if the current session is a read-only demo session."""
    return session.get('demo_mode', False)


@app.context_processor
def inject_demo_mode():
    """Make is_demo available in every template automatically."""
    return {'is_demo': is_demo_mode()}


def ensure_demo_user():
    """
    Create the demo user account and seed it with 45 days of realistic
    read-only data if it does not already exist.

    Called once when /demo is first visited. Subsequent visits reuse the
    persisted data (no reset required per US-26).
    """
    user = User.query.filter_by(email=DEMO_USER_EMAIL).first()

    if not user:
        user = User(email=DEMO_USER_EMAIL)
        user.set_password(DEMO_USER_PASSWORD)
        db.session.add(user)
        db.session.commit()

        progress = UserProgress(
            user_id=user.id,
            current_streak=12,
            longest_streak=21,
            total_logs=0,
            badges_earned='first_log,streak_3,streak_7,logs_50',
            selected_avatar='default',
            unlocked_avatars='default,space',
        )
        db.session.add(progress)
        db.session.commit()

    # Only seed if nearly empty
    entry_count = LogEntry.query.filter_by(user_id=user.id).count()
    if entry_count < 10:
        _seed_demo_data(user.id)


def _seed_demo_data(user_id: int):
    """
    Generate 45 days of deterministic, realistic demo data.

    The data is deliberately shaped to produce interesting patterns for the
    Insight Engine and Time-of-Day Analysis:
      • Morning readings are well-controlled (high TIR)
      • Evening readings spike more frequently (dinner carbs)
      • Occasional night-time lows
      • Stressed moods correlate with elevated glucose
      • ~72% of entries include carb data
    """
    # Deterministic seed so the demo always looks the same
    rng = random.Random(42)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=45)

    # (hour, jitter_minutes, meal_type, carb_min, carb_max, base_glucose, variance)
    meal_schedule = [
        (7,  30, 'breakfast', 35,  65,  6.8, 1.1),
        (12, 30, 'lunch',     45,  85,  7.4, 1.4),
        (15,  0, 'snack',     15,  35,  7.0, 1.0),
        (19,  0, 'dinner',    60, 100,  8.6, 2.2),  # Evening spikes intentional
        (22,  0, 'snack',     20,  45,  7.2, 1.5),
    ]

    moods    = ['happy', 'calm', 'stressed', 'tired', 'frustrated']
    weights  = [0.30, 0.30, 0.20, 0.15, 0.05]

    entries = []
    current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

    while current <= end_date:
        # ~8% chance of missing a whole day (realistic teenager logging)
        if rng.random() < 0.08:
            current += timedelta(days=1)
            continue

        weekend = current.weekday() >= 5

        for (hour, jitter_mins, meal_type, carb_min, carb_max, base_g, variance) in meal_schedule:
            # ~15% chance of skipping an individual meal reading
            if rng.random() < 0.15:
                continue

            actual_hour   = max(0, min(23, hour + rng.randint(-1, 1)))
            actual_minute = max(0, min(59, jitter_mins + rng.randint(-15, 15)))

            timestamp = current.replace(hour=actual_hour, minute=actual_minute, second=0)

            # Slightly higher glucose on weekends
            glucose = base_g + (0.4 if weekend else 0) + rng.gauss(0, variance * 0.55)

            # Night entries can dip lower (hypos)
            if actual_hour >= 22 or actual_hour < 5:
                glucose += rng.gauss(-0.3, 0.6)

            glucose = round(max(2.9, min(15.0, glucose)), 1)

            # Mood — stressed pushes glucose up
            mood = rng.choices(moods, weights=weights)[0]
            if mood == 'stressed':
                glucose = round(min(15.0, glucose + rng.uniform(0.7, 1.8)), 1)

            # Carb tracking (~72% of entries)
            carbs = None
            if rng.random() < 0.72:
                carbs = rng.randint(carb_min, carb_max)

            entries.append(LogEntry(
                user_id=user_id,
                timestamp=timestamp,
                blood_glucose=glucose,
                meal_type=meal_type,
                mood=mood,
                notes=None,
                carbs_grams=carbs,
            ))

        current += timedelta(days=1)

    # Batch insert for speed
    db.session.bulk_save_objects(entries)

    progress = UserProgress.query.filter_by(user_id=user_id).first()
    if progress:
        progress.total_logs = len(entries)
        progress.last_log_date = datetime.now().date()

    db.session.commit()


# ============================================================================
# US-26: DEMO MODE ROUTE
# ============================================================================

@app.route('/demo')
def demo():
    """
    Enter read-only demo mode.

    Creates (or reuses) the demo account, logs the session in as that user,
    and sets the demo_mode flag so all write routes are blocked.
    """
    # ensure_demo_user() handles creation/seeding. We then re-query the user
    # so it is bound to the current request's DB session (avoids DetachedInstanceError).
    ensure_demo_user()
    demo_user = User.query.filter_by(email=DEMO_USER_EMAIL).first()

    if not demo_user:
        flash('Demo mode could not be initialised. Please try again.', 'error')
        return redirect(url_for('login'))

    login_user(demo_user, remember=False)
    session['demo_mode'] = True

    flash('👋 Welcome to Demo Mode! Explore PancrePal with sample data. Logging is disabled.', 'info')
    return redirect(url_for('index'))


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

        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('register.html')

        if password != password_confirm:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        # Prevent registration with the internal demo email
        if email == DEMO_USER_EMAIL:
            flash('That email address is reserved.', 'error')
            return render_template('register.html')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with this email already exists.', 'error')
            return render_template('register.html')

        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

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
    """Log out current user and clear demo flag."""
    session.pop('demo_mode', None)
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
    Dashboard — main page showing glucose trends and insights.
    US-23: Advanced analytics and metrics.
    """
    user_id = current_user.id

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    entries = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        LogEntry.timestamp >= thirty_days_ago
    ).order_by(LogEntry.timestamp.desc()).all()

    progress = UserProgress.query.filter_by(user_id=user_id).first()
    if not progress:
        progress = UserProgress(user_id=user_id)
        db.session.add(progress)
        db.session.commit()

    if entries and not is_demo_mode():
        today = datetime.now().date()
        latest_entry_date = entries[0].timestamp.date()
        if latest_entry_date == today:
            update_streak(user_id, today)

    # Weekly consistency
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_entries = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        LogEntry.timestamp >= seven_days_ago
    ).all()

    unique_days = set(e.timestamp.date() for e in recent_entries)
    weekly_consistency = round((len(unique_days) / 7) * 100, 1)

    daily_tip = get_daily_tip()
    reminder = should_show_reminder(user_id) if not is_demo_mode() else None

    advanced_metrics = calculate_advanced_metrics(entries) if entries else None
    patterns = identify_recurring_patterns(entries) if entries else []
    suggestion = generate_weekly_suggestion(entries) if entries else None

    # Chart data
    chart_data = {'labels': [], 'glucose': [], 'carbs': [], 'mood': []}
    for entry in reversed(entries[:30]):
        chart_data['labels'].append(entry.timestamp.strftime('%d/%m'))
        chart_data['glucose'].append(entry.blood_glucose)
        chart_data['carbs'].append(entry.carbs_grams if entry.carbs_grams is not None else 0)
        mood_map = {'happy': 5, 'calm': 4, 'stressed': 3, 'tired': 2, 'frustrated': 1}
        chart_data['mood'].append(mood_map.get(entry.mood, 3))

    return render_template(
        'index.html',
        entries=entries[:10],
        progress=progress.to_dict(),
        weekly_consistency=weekly_consistency,
        advanced_metrics=advanced_metrics,
        patterns=patterns,
        suggestion=suggestion,
        daily_tip=daily_tip,
        chart_data=chart_data,
        reminder=reminder,
    )


@app.route('/log', methods=['GET', 'POST'])
@login_required
def log_entry():
    """
    Quick log page.
    US-22: Carbohydrate tracking included.
    US-26: Read-only in demo mode — POST is blocked.
    """
    # US-26: Block writes in demo mode
    if is_demo_mode() and request.method == 'POST':
        flash('Demo mode is read-only. Create a free account to start logging your own data!', 'info')
        return redirect(url_for('index'))

    if request.method == 'POST':
        user_id = current_user.id
        glucose_level = request.form.get('glucose_level')
        meal_type = request.form.get('meal_type', 'none')
        mood = request.form.get('mood')
        notes = request.form.get('notes', '').strip()
        carbs_grams = request.form.get('carbs_grams', '').strip()

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

        entry = LogEntry(
            user_id=user_id,
            blood_glucose=glucose_level,
            meal_type=meal_type,
            mood=mood,
            notes=notes,
            carbs_grams=carbs_value,
        )
        db.session.add(entry)
        db.session.commit()

        today = datetime.now().date()
        update_streak(user_id, today)

        progress = UserProgress.query.filter_by(user_id=user_id).first()
        if progress:
            newly_earned = check_and_award_badges(progress)
            for badge in newly_earned:
                flash(f'🏆 Badge earned: {badge["name"]}!', 'success')

        flash('Entry logged successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('log.html')


# ============================================================================
# US-21: EXPORT ROUTES (CSV only)
# ============================================================================

@app.route('/export/csv')
@login_required
def export_csv():
    """Export user data as CSV. Disabled in demo mode."""
    if is_demo_mode():
        flash('Export is disabled in demo mode. Create an account to export your own data.', 'info')
        return redirect(url_for('index'))

    user_id = current_user.id
    days = request.args.get('days', 30, type=int)

    cutoff_date = datetime.utcnow() - timedelta(days=days)
    entries = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        LogEntry.timestamp >= cutoff_date
    ).order_by(LogEntry.timestamp.desc()).all()

    if not entries:
        flash('No data available for export.', 'error')
        return redirect(url_for('index'))

    csv_data = generate_csv_export(entries)
    response = make_response(csv_data)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = (
        f'attachment; filename=pancrepal_data_{days}days_{datetime.now().strftime("%Y%m%d")}.csv'
    )
    return response


# ============================================================================
# US-23 + US-25 + US-27: ANALYTICS ROUTE
# ============================================================================

@app.route('/analytics')
@login_required
def analytics():
    """
    Detailed analytics page.
    US-23: Advanced KPI metrics.
    US-25: Insight Engine pattern detection.
    US-27: Time-of-day breakdown.
    """
    user_id = current_user.id
    days = request.args.get('days', 30, type=int)

    cutoff_date = datetime.utcnow() - timedelta(days=days)
    entries = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        LogEntry.timestamp >= cutoff_date
    ).order_by(LogEntry.timestamp.desc()).all()

    if not entries:
        flash('No data available for analysis. Start logging to see insights!', 'info')
        return redirect(url_for('index'))

    # US-23: Core metrics
    metrics = calculate_advanced_metrics(entries)
    patterns = identify_recurring_patterns(entries)
    suggestion = generate_weekly_suggestion(entries)

    explanations = {
        'time_in_range':          get_metric_explanation('time_in_range'),
        'coefficient_of_variation': get_metric_explanation('coefficient_of_variation'),
        'hypo_events':            get_metric_explanation('hypo_events'),
        'hyper_events':           get_metric_explanation('hyper_events'),
        'avg_glucose':            get_metric_explanation('avg_glucose'),
        'avg_daily_carbs':        get_metric_explanation('avg_daily_carbs'),
    }

    # US-27: Time-of-day breakdown
    time_analysis = analyze_time_of_day(entries)

    # Build chart data for time-of-day TIR bar chart (passed as JSON to template)
    tod_chart = {
        'labels': [],
        'tir':    [],
        'hypo':   [],
        'hyper':  [],
        'colors': [],
    }
    color_map = {
        'morning':   'rgba(255, 186, 73, 0.8)',
        'afternoon': 'rgba(74, 144, 226, 0.8)',
        'evening':   'rgba(155, 89, 182, 0.8)',
        'night':     'rgba(52, 73, 94, 0.8)',
    }
    for period_key in ['morning', 'afternoon', 'evening', 'night']:
        p = time_analysis[period_key]
        if p['has_data']:
            tod_chart['labels'].append(f"{p['icon']} {p['label']}")
            tod_chart['tir'].append(p['time_in_range_pct'])
            tod_chart['hypo'].append(p['hypo_pct'])
            tod_chart['hyper'].append(p['hyper_pct'])
            tod_chart['colors'].append(color_map[period_key])

    # US-25: Insight Engine
    insights = generate_insights(entries, time_analysis)

    return render_template(
        'analytics.html',
        metrics=metrics,
        patterns=patterns,
        suggestion=suggestion,
        explanations=explanations,
        days=days,
        time_analysis=time_analysis,
        tod_chart=tod_chart,
        insights=insights,
    )


# ============================================================================
# REMAINING ROUTES (unchanged from Iteration 5)
# ============================================================================

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

    available_avatars = ['default']
    unlocked = progress.get_unlocked_avatars()
    available_avatars.extend([a for a in unlocked if a != 'default'])

    return render_template('avatar.html', progress=progress.to_dict(), avatars=available_avatars)


@app.route('/avatar/update', methods=['POST'])
@login_required
def update_avatar():
    """Update user's avatar selection. Blocked in demo mode."""
    if is_demo_mode():
        flash('Avatar changes are disabled in demo mode.', 'info')
        return redirect(url_for('avatar'))

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
        if is_demo_mode():
            flash('Settings cannot be changed in demo mode.', 'info')
            return redirect(url_for('settings'))
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
    """Data Ethics & Privacy page — accessible without login."""
    return render_template('ethics.html')


# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/api/entries', methods=['GET'])
@login_required
def api_entries():
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
    user_id = current_user.id
    progress = UserProgress.query.filter_by(user_id=user_id).first()
    if not progress:
        return jsonify({'error': 'No progress found'}), 404
    return jsonify(progress.to_dict())


@app.route('/api/metrics', methods=['GET'])
@login_required
def api_metrics():
    user_id = current_user.id
    days = request.args.get('days', 30, type=int)
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    entries = LogEntry.query.filter(
        LogEntry.user_id == user_id,
        LogEntry.timestamp >= cutoff_date
    ).all()
    if not entries:
        return jsonify({'error': 'No data available'}), 404
    return jsonify(calculate_advanced_metrics(entries))


# ============================================================================
# PWA ROUTES
# ============================================================================

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')


@app.route('/service-worker.js')
def service_worker():
    return send_from_directory('static', 'service-worker.js')


@app.route('/apple-touch-icon.png')
def apple_touch_icon():
    return send_from_directory('static/icons', 'icon-192x192.png')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static/icons', 'icon-192x192.png')


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
else:
    with app.app_context():
        db.create_all()
