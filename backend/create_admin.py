#!/usr/bin/env python3
"""Create default admin user if it doesn't exist"""
import sys
import os
sys.path.insert(0, '/opt/depl0y/backend')

# Set DATABASE_URL environment variable to ensure SQLite is used
os.environ['DATABASE_URL'] = 'sqlite:////var/lib/depl0y/db/depl0y.db'

try:
    from app.core.database import SessionLocal
    from app.models import User, UserRole
    from app.core.security import get_password_hash
    
    print("✓ Imports successful")
    
    def create_admin_user():
        """Create default admin user with 2FA disabled"""
        db = SessionLocal()
        try:
            print("✓ Database connection established")
            
            # Check if admin user already exists
            existing_admin = db.query(User).filter(User.username == 'admin').first()
            if existing_admin:
                print(f"⚠️  Admin user already exists (ID: {existing_admin.id})")
                print(f"   Current 2FA status: {existing_admin.totp_enabled}")
                # Reset password to default and ensure 2FA is disabled
                existing_admin.hashed_password = get_password_hash("admin")
                existing_admin.totp_enabled = False
                existing_admin.totp_secret = None
                existing_admin.is_active = True
                db.commit()
                print("✓ Admin password reset to: admin")
                print("✓ 2FA explicitly disabled (totp_enabled=False)")
                print("✓ 2FA secret cleared (totp_secret=None)")
                print("✓ Account activated")
                
                # Verify the change
                db.refresh(existing_admin)
                print(f"✓ VERIFIED: totp_enabled = {existing_admin.totp_enabled}")
                return

            # Create new admin user
            print("Creating new admin user...")
            hashed_password = get_password_hash("admin")
            admin_user = User(
                username="admin",
                email="admin@localhost",
                hashed_password=hashed_password,
                role=UserRole.ADMIN,
                is_active=True,
                totp_enabled=False,  # Explicitly disable 2FA
                totp_secret=None
            )

            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            
            print("✓ Created default admin user")
            print(f"  ID: {admin_user.id}")
            print(f"  Username: admin")
            print(f"  Password: admin")
            print(f"  2FA Enabled: {admin_user.totp_enabled}")
            print(f"  2FA Secret: {admin_user.totp_secret}")
            print(f"  Active: {admin_user.is_active}")
            print(f"  Role: {admin_user.role}")

        except Exception as e:
            print(f"✗ Error with admin user: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
        finally:
            db.close()

    create_admin_user()
    
except Exception as e:
    print(f"✗ Fatal error during import/setup: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
