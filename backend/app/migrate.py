"""In-place SQLite schema upgrades for databases created by older versions.

`Base.metadata.create_all` only creates missing *tables*; it cannot add
columns to an existing table. SQLite supports `ALTER TABLE ... ADD COLUMN`,
which is all this app needs to move forward.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# Columns added to `todos` after the first release.
TODO_COLUMNS = {
    "project_id": "project_id INTEGER NULL REFERENCES projects(id) ON DELETE CASCADE",
    "due_date": "due_date DATE NULL",
    "position": "position INTEGER NOT NULL DEFAULT 0",
    "completed_at": "completed_at DATETIME NULL",
    "assignee_id": "assignee_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL",
}

# Columns added to `projects` when accounts + sharing arrived.
PROJECT_COLUMNS = {
    "owner_id": "owner_id INTEGER NULL REFERENCES users(id) ON DELETE CASCADE",
    "is_shared": "is_shared BOOLEAN NOT NULL DEFAULT 0",
}

# Columns added to `users` when email verification arrived.
USER_COLUMNS = {
    "email_verified": "email_verified BOOLEAN NOT NULL DEFAULT 0",
    "email_verified_at": "email_verified_at DATETIME NULL",
}


def _add_missing_columns(engine: Engine, table: str, columns: dict[str, str]) -> set[str]:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return set()

    existing = {col["name"] for col in inspector.get_columns(table)}
    added: set[str] = set()
    with engine.begin() as conn:
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
                added.add(name)
    return added


def ensure_schema(engine: Engine) -> None:
    added = _add_missing_columns(engine, "todos", TODO_COLUMNS)

    if "position" in added:
        # Older rows have no positions. Use -id so the previous
        # "newest first" ordering is preserved (positions sort ascending).
        with engine.begin() as conn:
            conn.execute(text("UPDATE todos SET position = -id WHERE position = 0"))

    _add_missing_columns(engine, "projects", PROJECT_COLUMNS)

    user_added = _add_missing_columns(engine, "users", USER_COLUMNS)
    if "email_verified" in user_added:
        # Accounts that predate verification were created before the feature
        # existed — trust them rather than locking everyone out.
        with engine.begin() as conn:
            conn.execute(text("UPDATE users SET email_verified = 1"))
