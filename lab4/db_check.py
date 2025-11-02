# db_check.py
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

url = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME", "webapp_db"),
)

engine = create_engine(url, echo=False, future=True)


def main() -> int:
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] connecting to {url.render_as_string(hide_password=True)}")

    try:
        with engine.connect() as conn:
            # по желанию можно зафиксировать search_path
            conn.execute(text("SET search_path TO auth, public"))

            total_users = conn.execute(
                text("SELECT COUNT(*) FROM auth.users")
            ).scalar_one()
            total_roles = conn.execute(
                text("SELECT COUNT(*) FROM auth.roles")
            ).scalar_one()

            sample_users = (
                conn.execute(
                    text(
                        """
                SELECT user_id, login, email
                FROM auth.users
                ORDER BY user_id
                LIMIT 5
            """
                    )
                )
                .mappings()
                .all()
            )

            sample_map = (
                conn.execute(
                    text(
                        """
                SELECT u.login, r.role_name
                FROM auth.user_roles ur
                JOIN auth.users u ON u.user_id = ur.user_id
                JOIN auth.roles r ON r.role_id = ur.role_id
                ORDER BY u.login, r.role_name
                LIMIT 10
            """
                    )
                )
                .mappings()
                .all()
            )

            print(f"users: {total_users}, roles: {total_roles}")
            print("sample users:")
            for row in sample_users:
                print(f"  - {row['user_id']}: {row['login']} <{row['email']}>")

            print("user → roles (sample):")
            for row in sample_map:
                print(f"  - {row['login']} → {row['role_name']}")

        print("OK: database connectivity and SELECTs succeeded.")
        return 0

    except SQLAlchemyError as e:
        print("ERROR:", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
