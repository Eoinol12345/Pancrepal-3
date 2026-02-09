from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import bcrypt

# Initialize SQLAlchemy instance
db = SQLAlchemy()


class User(UserMixin, db.Model):
    """
    User account model for authentication.

    Each user has their own isolated data - log entries, progress, badges.
    Passwords are hashed using bcrypt for security.
    """

    __tablename__ = 'users'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Authentication fields
    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    # Timestamps
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    last_login = db.Column(
        db.DateTime,
        nullable=True
    )

    # Relationships
    log_entries = db.relationship(
        'LogEntry',
        backref='user',
        lazy=True,
        cascade='all, delete-orphan'
    )

    progress = db.relationship(
        'UserProgress',
        backref='user',
        uselist=False,
        cascade='all, delete-orphan'
    )

    def set_password(self, password):
        """
        Hash password using bcrypt before storing.

        Args:
            password: Plain text password
        """
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            salt
        ).decode('utf-8')

    def check_password(self, password):
        """
        Verify password matches stored hash.

        Args:
            password: Plain text password to check

        Returns:
            Boolean indicating if password is correct
        """
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )

    def __repr__(self):
        return f'<User {self.email}>'


class LogEntry(db.Model):
    """
    Core model for diabetes log entries.

    Fields represent the essential data points for Type 1 diabetes management:
    - Blood glucose: Primary health metric
    - Meal type: Context for glucose readings
    - Mood: Emotional state tracking for holistic support
    - Notes: Optional detailed reflection
    - Carbs (US-22): Carbohydrate intake tracking
    """

    __tablename__ = 'log_entries'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to user
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Timestamp - automatically set to current time
    timestamp = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True  # Indexed for efficient date-range queries
    )

    # Blood glucose level in mmol/L (UK/International standard)
    # Range: typically 2.2-22.2 for T1D logging
    blood_glucose = db.Column(
        db.Float,
        nullable=False,
        comment="Blood glucose in mmol/L"
    )

    # Meal type - categorical data for pattern recognition
    # Options: 'breakfast', 'lunch', 'dinner', 'snack', 'none'
    meal_type = db.Column(
        db.String(20),
        nullable=False,
        comment="Meal context for glucose reading"
    )

    # Mood - emotional state using emoji-based system
    # Options: 'happy', 'calm', 'stressed', 'tired', 'frustrated'
    mood = db.Column(
        db.String(20),
        nullable=False,
        comment="Emotional state at time of logging"
    )

    # Optional notes for additional context
    notes = db.Column(
        db.Text,
        nullable=True,
        comment="User's optional reflections"
    )

    # US-22: Carbohydrate tracking (grams)
    carbs_grams = db.Column(
        db.Integer,
        nullable=True,
        comment="Carbohydrate intake in grams (optional)"
    )

    def __repr__(self):
        """String representation for debugging."""
        return f'<LogEntry {self.id}: {self.blood_glucose}mmol/L at {self.timestamp}>'

    def to_dict(self):
        """
        Convert model to dictionary for JSON serialization.
        Useful for API responses and chart data.
        """
        return {
            'id': self.id,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat(),
            'blood_glucose': self.blood_glucose,
            'meal_type': self.meal_type,
            'mood': self.mood,
            'notes': self.notes,
            'carbs_grams': self.carbs_grams  # US-22
        }


class UserProgress(db.Model):
    """
    Tracks user progress, streaks, and gamification elements.

    Design Philosophy:
    - Encourages consistency without pressure
    - Celebrates milestones (badges)
    - Personalizes experience (avatar customization)
    """

    __tablename__ = 'user_progress'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to user
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        index=True
    )

    # Streak tracking
    current_streak = db.Column(
        db.Integer,
        default=0,
        comment="Current consecutive days with logs"
    )

    longest_streak = db.Column(
        db.Integer,
        default=0,
        comment="Record streak for motivation"
    )

    last_log_date = db.Column(
        db.Date,
        nullable=True,
        comment="Date of last log entry"
    )

    # Gamification metrics
    total_logs = db.Column(
        db.Integer,
        default=0,
        comment="Total number of logs ever created"
    )

    badges_earned = db.Column(
        db.Text,
        default='',
        comment="Comma-separated list of earned badge IDs"
    )

    # Avatar customization
    selected_avatar = db.Column(
        db.String(50),
        default='default',
        comment="Current avatar style/theme"
    )

    unlocked_avatars = db.Column(
        db.Text,
        default='default',
        comment="Comma-separated list of unlocked avatar IDs"
    )

    # Preferences
    reminder_time = db.Column(
        db.Time,
        nullable=True,
        comment="Preferred time for gentle reminders"
    )

    reminders_enabled = db.Column(
        db.Boolean,
        default=False,
        comment="Whether user wants reminders"
    )

    # Timestamps
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f'<UserProgress: {self.current_streak} day streak, {self.total_logs} logs>'

    def add_badge(self, badge_id: str):
        """
        Award a new badge to the user.
        Badges are stored as comma-separated string.
        """
        if not self.badges_earned:
            self.badges_earned = badge_id
        elif badge_id not in self.badges_earned.split(','):
            self.badges_earned += f',{badge_id}'

    def has_badge(self, badge_id: str) -> bool:
        """Check if user has earned a specific badge."""
        return badge_id in (self.badges_earned or '').split(',')

    def unlock_avatar(self, avatar_id: str):
        """Unlock a new avatar style."""
        if not self.unlocked_avatars:
            self.unlocked_avatars = avatar_id
        elif avatar_id not in self.unlocked_avatars.split(','):
            self.unlocked_avatars += f',{avatar_id}'

    def get_unlocked_avatars(self) -> list:
        """Get list of all unlocked avatar IDs."""
        return (self.unlocked_avatars or 'default').split(',')

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'current_streak': self.current_streak,
            'longest_streak': self.longest_streak,
            'total_logs': self.total_logs,
            'badges': (self.badges_earned or '').split(','),
            'selected_avatar': self.selected_avatar,
            'unlocked_avatars': self.get_unlocked_avatars()
        }


# ============================================================================
# BADGE DEFINITIONS (Constants)
# ============================================================================

BADGES = {
    'first_log': {
        'id': 'first_log',
        'name': 'Getting Started',
        'description': 'Logged your first entry!',
        'icon': '🌱'
    },
    'streak_3': {
        'id': 'streak_3',
        'name': '3-Day Streak',
        'description': 'Logged for 3 consecutive days',
        'icon': '🔥'
    },
    'streak_7': {
        'id': 'streak_7',
        'name': 'Week Warrior',
        'description': 'Logged for 7 consecutive days',
        'icon': '⭐'
    },
    'streak_30': {
        'id': 'streak_30',
        'name': 'Monthly Champion',
        'description': 'Logged for 30 consecutive days',
        'icon': '🏆'
    },
    'logs_50': {
        'id': 'logs_50',
        'name': 'Data Collector',
        'description': 'Created 50 total logs',
        'icon': '📊'
    },
    'logs_100': {
        'id': 'logs_100',
        'name': 'Century Club',
        'description': 'Created 100 total logs',
        'icon': '💯'
    }
}

# ============================================================================
# AVATAR STYLES (Constants)
# ============================================================================

AVATAR_STYLES = {
    'default': {
        'id': 'default',
        'name': 'Classic',
        'description': 'The original PancrePal avatar',
        'unlock_requirement': None
    },
    'space': {
        'id': 'space',
        'name': 'Space Explorer',
        'description': 'Reach for the stars!',
        'unlock_requirement': 'streak_7'
    },
    'nature': {
        'id': 'nature',
        'name': 'Nature Friend',
        'description': 'Calm and grounded',
        'unlock_requirement': 'logs_50'
    },
    'rainbow': {
        'id': 'rainbow',
        'name': 'Rainbow Vibes',
        'description': 'Celebrate your colors!',
        'unlock_requirement': 'streak_30'
    }
}