"""
Database migration script for Iteration 4.

This script migrates your existing PancrePal database from Iteration 3
to the new schema with User authentication support.

What it does:
1. Creates User table
2. Adds user_id foreign key to LogEntry and UserProgress
3. Creates a default admin user
4. Links existing data to the admin user

IMPORTANT: Backup your database before running this!
"""

from app import app, db
from db import User, LogEntry, UserProgress
from datetime import datetime

print("🔄 Starting database migration for Iteration 4...\n")

# Create application context
with app.app_context():
    print("Step 1: Creating backup timestamp...")
    backup_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    print(f"   Backup timestamp: {backup_timestamp}")
    print(f"   ⚠️  IMPORTANT: Make a copy of pancrepal.db before continuing!\n")

    proceed = input("Have you backed up your database? (yes/no): ")
    if proceed.lower() != 'yes':
        print("❌ Migration cancelled. Please backup your database first.")
        exit()

    print("\nStep 2: Dropping existing tables...")
    db.drop_all()
    print("   ✓ Tables dropped")

    print("\nStep 3: Creating new schema with User support...")
    db.create_all()
    print("   ✓ New tables created")

    print("\nStep 4: Creating default admin user...")
    admin_email = input("Enter admin email (e.g., admin@pancrepal.com): ").strip().lower()
    admin_password = input("Enter admin password (min 8 characters): ").strip()

    if len(admin_password) < 8:
        print("❌ Password must be at least 8 characters.")
        exit()

    # Create admin user
    admin = User(email=admin_email)
    admin.set_password(admin_password)
    db.session.add(admin)
    db.session.commit()

    print(f"   ✓ Admin user created: {admin_email}")

    print("\nStep 5: Creating UserProgress for admin...")
    progress = UserProgress(user_id=admin.id)
    db.session.add(progress)
    db.session.commit()
    print("   ✓ UserProgress created")

    print("\n" + "=" * 60)
    print("✅ Migration completed successfully!")
    print("=" * 60)
    print("\nYour database is now ready for Iteration 4.")
    print(f"\nLogin credentials:")
    print(f"   Email: {admin_email}")
    print(f"   Password: [the password you entered]")
    print("\n📝 Note: Your old data has been cleared to prevent conflicts.")
    print("   Use seed.py to generate sample data if needed.")
    print("\n🚀 Start the app with: python app.py")