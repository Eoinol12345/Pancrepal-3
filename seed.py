"""
Seed script for PancrePal database.
Generates realistic test data including carbohydrate tracking (US-22).

Usage:
    python seed.py

Warning: This will DELETE all existing data and create fresh test data.
"""

from app import app, db
from db import User, LogEntry, UserProgress
from datetime import datetime, timedelta
import random
import sys

# Seed configuration
NUM_DAYS = 60  # Generate 60 days of historical data
ENTRIES_PER_DAY_RANGE = (2, 5)  # 2-5 entries per day
CARB_TRACKING_RATE = 0.70  # 70% of entries include carbs (realistic)


def clear_database():
    """Delete all existing data."""
    print("🗑️  Clearing existing data...")
    try:
        with app.app_context():
            db.drop_all()
            db.create_all()
        print("✅ Database cleared and recreated")
        return True
    except Exception as e:
        print(f"❌ Error clearing database: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_test_user():
    """Create a test user account."""
    print("👤 Creating test user...")

    try:
        with app.app_context():
            # Create user
            user = User(email='test@pancrepal.com')
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()

            user_id = user.id
            print(f"   ✓ User created with ID: {user_id}")

            # Create progress record
            progress = UserProgress(
                user_id=user_id,
                current_streak=7,
                longest_streak=14,
                total_logs=0,  # Will be updated as we add entries
                selected_avatar='default',
                unlocked_avatars='default',
                badges_earned='first_log,streak_3,streak_7'
            )
            db.session.add(progress)
            db.session.commit()
            print(f"   ✓ Progress record created")

            print(f"✅ Test user created: test@pancrepal.com")
            print(f"   Password: password123")
            return user_id

    except Exception as e:
        print(f"❌ Error creating user: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_glucose_reading(meal_type, time_of_day, base_control=7.0):
    """
    Generate realistic glucose reading based on meal type and time.

    Args:
        meal_type: 'breakfast', 'lunch', 'dinner', 'snack', 'none'
        time_of_day: Hour of day (0-23)
        base_control: User's average control level (5.0-9.0)

    Returns:
        Float: Glucose reading in mmol/L
    """
    # Base glucose varies by time of day
    if 6 <= time_of_day < 12:  # Morning
        base = base_control + random.uniform(-0.5, 0.5)
    elif 12 <= time_of_day < 18:  # Afternoon
        base = base_control + random.uniform(-0.3, 0.7)
    elif 18 <= time_of_day < 23:  # Evening
        base = base_control + random.uniform(-0.2, 0.8)
    else:  # Night
        base = base_control + random.uniform(-1.0, 0.2)

    # Meal impact
    meal_impact = {
        'breakfast': random.uniform(0.5, 2.0),
        'lunch': random.uniform(0.3, 1.8),
        'dinner': random.uniform(0.4, 2.2),
        'snack': random.uniform(0.2, 1.0),
        'none': random.uniform(-0.5, 0.5)
    }

    glucose = base + meal_impact.get(meal_type, 0)

    # Add some random variation
    glucose += random.gauss(0, 0.5)

    # Ensure realistic bounds
    glucose = max(3.5, min(15.0, glucose))

    return round(glucose, 1)


def generate_carb_amount(meal_type):
    """
    Generate realistic carbohydrate amounts based on meal type.

    US-22: Realistic carb values for testing.

    Args:
        meal_type: Type of meal

    Returns:
        Integer: Carbs in grams, or None if not tracked
    """
    # 70% of entries include carbs (realistic tracking rate)
    if random.random() > CARB_TRACKING_RATE:
        return None

    # Realistic carb ranges by meal type
    carb_ranges = {
        'breakfast': (30, 75),   # Cereal, toast, fruit
        'lunch': (40, 90),        # Sandwich, salad, sides
        'dinner': (50, 100),      # Main meal with starches
        'snack': (10, 35),        # Fruit, crackers, yogurt
        'none': (0, 0)            # No meal
    }

    min_carbs, max_carbs = carb_ranges.get(meal_type, (0, 0))

    if min_carbs == 0 and max_carbs == 0:
        return None

    return random.randint(min_carbs, max_carbs)


def generate_mood():
    """Generate realistic mood distribution."""
    moods = ['happy', 'calm', 'stressed', 'tired', 'frustrated']
    weights = [0.35, 0.30, 0.15, 0.12, 0.08]  # Bias toward positive
    return random.choices(moods, weights=weights)[0]


def generate_notes(meal_type, glucose, carbs):
    """Generate occasional realistic notes."""
    # Only 30% of entries have notes
    if random.random() > 0.3:
        return None

    note_templates = [
        "Feeling good today",
        "Had a busy morning",
        "Didn't sleep well last night",
        "Stressed about exams",
        "Great workout earlier",
        "Forgot to take reading earlier",
        "Feeling a bit tired",
        f"Had {meal_type} with friends",
        "Normal day",
        "Feeling energized"
    ]

    # Special notes for unusual readings
    if glucose > 12.0 and carbs and carbs > 70:
        return f"High reading - maybe ate too much ({carbs}g carbs)"
    elif glucose < 4.0:
        return "Feeling shaky, had some juice"

    return random.choice(note_templates)


def create_log_entries(user_id):
    """Generate realistic log entries for testing."""
    print("📝 Generating log entries...")

    try:
        with app.app_context():
            entries = []
            user_control_level = random.uniform(6.5, 8.0)  # Simulated user's baseline

            # Generate entries going back NUM_DAYS
            end_date = datetime.now()
            start_date = end_date - timedelta(days=NUM_DAYS)

            current_date = start_date
            total_entries = 0
            batch_size = 50  # Commit every 50 entries

            print(f"   Generating entries from {start_date.date()} to {end_date.date()}...")

            while current_date <= end_date:
                # Random number of entries per day
                num_entries = random.randint(*ENTRIES_PER_DAY_RANGE)

                # Generate entries for this day
                for _ in range(num_entries):
                    # Determine meal type based on time of day
                    hour = random.randint(6, 22)

                    if 6 <= hour < 10:
                        meal_type = 'breakfast'
                    elif 11 <= hour < 14:
                        meal_type = 'lunch'
                    elif 17 <= hour < 21:
                        meal_type = 'dinner'
                    else:
                        meal_type = random.choice(['snack', 'none'])

                    # Generate timestamp
                    minute = random.randint(0, 59)
                    timestamp = current_date.replace(hour=hour, minute=minute)

                    # Generate data
                    glucose = generate_glucose_reading(meal_type, hour, user_control_level)
                    carbs = generate_carb_amount(meal_type)  # US-22
                    mood = generate_mood()
                    notes = generate_notes(meal_type, glucose, carbs)

                    # Create entry
                    entry = LogEntry(
                        user_id=user_id,
                        timestamp=timestamp,
                        blood_glucose=glucose,
                        meal_type=meal_type,
                        mood=mood,
                        notes=notes,
                        carbs_grams=carbs  # US-22
                    )
                    db.session.add(entry)
                    total_entries += 1

                    # Commit in batches
                    if total_entries % batch_size == 0:
                        db.session.commit()
                        print(f"   ... {total_entries} entries created")

                # Move to next day
                current_date += timedelta(days=1)

            # Final commit
            db.session.commit()
            print(f"   ✓ All entries committed to database")

            # Update user progress
            progress = UserProgress.query.filter_by(user_id=user_id).first()
            if progress:
                progress.total_logs = total_entries
                db.session.commit()
                print(f"   ✓ Updated user progress")

            # Calculate carb tracking statistics
            entries_with_carbs = LogEntry.query.filter(
                LogEntry.user_id == user_id,
                LogEntry.carbs_grams.isnot(None)
            ).count()

            carb_tracking_pct = (entries_with_carbs / total_entries * 100) if total_entries > 0 else 0

            print(f"✅ Created {total_entries} log entries")
            print(f"   Date range: {start_date.date()} to {end_date.date()}")
            print(f"   Entries per day: {total_entries / NUM_DAYS:.1f} average")
            print(f"   Carb tracking: {entries_with_carbs} entries ({carb_tracking_pct:.1f}%)")

            return True

    except Exception as e:
        print(f"❌ Error creating log entries: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_data():
    """Verify that data was actually created."""
    print("\n🔍 Verifying data...")

    try:
        with app.app_context():
            user_count = User.query.count()
            entry_count = LogEntry.query.count()
            progress_count = UserProgress.query.count()

            print(f"   Users: {user_count}")
            print(f"   Log Entries: {entry_count}")
            print(f"   Progress Records: {progress_count}")

            if user_count > 0 and entry_count > 0:
                print("✅ Data verification passed!")
                return True
            else:
                print("❌ Data verification failed - no data found!")
                return False

    except Exception as e:
        print(f"❌ Error verifying data: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run complete database seeding."""
    print("=" * 60)
    print("PancrePal Database Seed Script")
    print("=" * 60)
    print()

    # Warning
    print("⚠️  WARNING: This will DELETE all existing data!")
    response = input("Continue? (yes/no): ")

    if response.lower() != 'yes':
        print("❌ Seeding cancelled")
        return

    print()

    # Execute seeding
    if not clear_database():
        print("\n❌ Failed to clear database. Aborting.")
        sys.exit(1)

    user_id = create_test_user()
    if not user_id:
        print("\n❌ Failed to create test user. Aborting.")
        sys.exit(1)

    if not create_log_entries(user_id):
        print("\n❌ Failed to create log entries. Aborting.")
        sys.exit(1)

    if not verify_data():
        print("\n❌ Data verification failed. Aborting.")
        sys.exit(1)

    print()
    print("=" * 60)
    print("✅ DATABASE SEEDING COMPLETE!")
    print()
    print("Login credentials:")
    print("  Email: test@pancrepal.com")
    print("  Password: password123")
    print()
    print("Start your app:")
    print("  python app.py")
    print("  Visit: http://localhost:5002")
    print("=" * 60)


if __name__ == '__main__':
    main()