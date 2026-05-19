#!/usr/bin/env python
"""
Identity App Migration - Production Deployment Script
Executes table renames and content type updates before running Django migrations
"""

import sys

from django.db import connection, transaction
from django.utils import timezone


def check_prerequisites():
    """Verify migration prerequisites"""
    cursor = connection.cursor()

    # Check if already applied
    cursor.execute(
        "SELECT COUNT(*) FROM django_migrations WHERE app='identity' AND name='0001_initial'"
    )
    if cursor.fetchone()[0] > 0:
        print("ℹ️  identity.0001_initial already applied. Skipping.")
        return False

    # Check if vmlc_user table exists
    cursor.execute(
        """
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = 'vmlc_user'
    """
    )
    if cursor.fetchone()[0] == 0:
        print("⚠️  vmlc_user table not found. Skipping identity migration.")
        return False

    print("✅ Prerequisites met. Proceeding with migration.")
    return True


def migrate_identity_app():
    """Execute the identity app migration"""
    print("\n" + "=" * 60)
    print("IDENTITY APP MIGRATION - STARTING")
    print("=" * 60 + "\n")

    try:
        with transaction.atomic():
            cursor = connection.cursor()

            # 1. Rename tables
            print("1. Renaming tables...")
            tables = [
                ("vmlc_user", "identity_user"),
                ("vmlc_staff", "identity_staff"),
                ("vmlc_candidate", "identity_candidate"),
                ("vmlc_prereguser", "identity_prereguser"),
                ("vmlc_userverification", "identity_userverification"),
                ("vmlc_emailotp", "identity_emailotp"),
            ]

            for old_name, new_name in tables:
                cursor.execute(f"ALTER TABLE {old_name} RENAME TO {new_name};")
                print(f"   ✓ {old_name} → {new_name}")

            # 2. Update content types
            print("\n2. Updating content types...")
            cursor.execute(
                """
                UPDATE django_content_type 
                SET app_label = 'identity' 
                WHERE app_label = 'vmlc' 
                AND model IN ('user', 'staff', 'candidate', 'prereguser', 'userverification', 'emailotp')
            """
            )
            rows_updated = cursor.rowcount
            print(f"   ✓ Updated {rows_updated} content types")

            # 3. Mark migration as applied
            print("\n3. Marking migration as applied...")
            cursor.execute(
                "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
                ["identity", "0001_initial", timezone.now()],
            )
            print("   ✓ identity.0001_initial marked as applied")

            print("\n" + "=" * 60)
            print("✅ MIGRATION COMPLETED SUCCESSFULLY")
            print("=" * 60 + "\n")
            return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}", file=sys.stderr)
        print("Transaction rolled back. No changes made.", file=sys.stderr)
        raise


if __name__ == "__main__":
    if check_prerequisites():
        migrate_identity_app()
    else:
        print("Skipping identity migration.")
        sys.exit(0)
