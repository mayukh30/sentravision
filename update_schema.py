from backend.db.database import engine
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

def update_db():
    with engine.connect() as conn:
        try:
            print("Adding user_id to streams table...")
            # We'll use an IF NOT EXISTS equivalent by catching the error if it already exists,
            # but Postgres ALTER TABLE ADD COLUMN IF NOT EXISTS is cleaner.
            conn.execute(text("ALTER TABLE streams ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)"))
            conn.commit()
            print("Successfully updated database schema.")
        except Exception as e:
            print(f"Error updating schema: {e}")

if __name__ == "__main__":
    update_db()
