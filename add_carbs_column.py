"""
Database Migration: Add carbs_grams column to log_entries table
US-22: Carbohydrate Tracking

This script safely adds the carbs_grams column to existing database.
Run once before deploying US-22, US-21, and US-23 features.
"""

import sqlite3
import os
from datetime import datetime
import shutil

# Database path
DB_PATH = 'instance/pancrepal.db'


def backup_database():
    """Create timestamped backup of database before migration."""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        print("   This is normal for new installations.")
        return False

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f'pancrepal_backup_{timestamp}.db'

    try:
        shutil.copy2(DB_PATH, backup_path)
        print(f"✅ Backup created: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False


def check_column_exists(cursor):
    """Check if carbs_grams column already exists."""
    cursor.execute("PRAGMA table_info(log_entries)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    return 'carbs_grams' in column_names


def add_carbs_column():
    """Add carbs_grams column to log_entries table."""
    if not os.path.exists(DB_PATH):
        print("ℹ️  No existing database found. Column will be created on first app run.")
        return True

    try:
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check if column already exists
        if check_column_exists(cursor):
            print("ℹ️  Column 'carbs_grams' already exists. No migration needed.")
            conn.close()
            return True

        # Add column
        print("🔄 Adding carbs_grams column to log_entries table...")
        cursor.execute("""
            ALTER TABLE log_entries 
            ADD COLUMN carbs_grams INTEGER NULL
        """)

        conn.commit()

        # Verify column was added
        if check_column_exists(cursor):
            print("✅ Column added successfully!")

            # Show row count
            cursor.execute("SELECT COUNT(*) FROM log_entries")
            count = cursor.fetchone()[0]
            print(f"   {count} existing entries will have NULL carbs (backward compatible)")
        else:
            print("❌ Column addition failed - verification unsuccessful")
            conn.close()
            return False

        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main():
    """Run migration with backup."""
    print("=" * 60)
    print("PancrePal Database Migration - US-22: Carbohydrate Tracking")
    print("=" * 60)
    print()

    # Step 1: Backup
    print("Step 1: Creating backup...")
    backup_created = backup_database()
    print()

    # Step 2: Add column
    print("Step 2: Adding carbs_grams column...")
    success = add_carbs_column()
    print()

    # Summary
    print("=" * 60)
    if success:
        print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
        print()
        print("Next steps:")
        print("1. Replace your Python files (app.py, db.py, analytics.py, exports.py)")
        print("2. Replace your template files (index.html, log.html, analytics.html)")
        print("3. Install new dependencies: pip install reportlab matplotlib")
        print("4. Restart your Flask app: python app.py")
        print()
        if backup_created:
            print("💾 Backup available for rollback if needed")
    else:
        print("❌ MIGRATION FAILED")
        print()
        print("Troubleshooting:")
        print("- Check that pancrepal.db exists")
        print("- Ensure no other process has the database locked")
        print("- Review error messages above")
        if backup_created:
            print("- Restore from backup if needed")
    print("=" * 60)


if __name__ == '__main__':
    main()