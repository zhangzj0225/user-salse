"""create admin user script

Usage:
    python scripts/create_admin.py --username admin --password mypassword
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import sqlalchemy as sa
import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def main():
    parser = argparse.ArgumentParser(description="Create admin user")
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--password", required=True, help="Admin password")
    args = parser.parse_args()

    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        pw_hash = bcrypt.hashpw(args.password.encode("utf-8"), bcrypt.gensalt()).decode()
        session.execute(
            sa.text(
                "INSERT INTO admin_users (username, password_hash) "
                "VALUES (:username, :pw) "
                "ON DUPLICATE KEY UPDATE password_hash = :pw"
            ),
            {"username": args.username, "pw": pw_hash},
        )
        session.commit()
        print(f"Admin user '{args.username}' created/updated.")
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
