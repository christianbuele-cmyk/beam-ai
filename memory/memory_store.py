import json
import os
import re

from database import get_db_connection


SESSION_KEY_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def _validate_session_key(session_key: str) -> None:
    if not SESSION_KEY_PATTERN.fullmatch(session_key):
        raise ValueError("A valid per-session key is required for memory storage.")


def load_memory(session_key: str) -> dict:
    _validate_session_key(session_key)

    placeholder = "%s" if os.getenv("DATABASE_URL") else "?"

    with get_db_connection() as connection:
        row = connection.execute(
            f"""
            SELECT memory_json
            FROM memories
            WHERE session_key = {placeholder}
            """,
            (session_key,)
        ).fetchone()

    if row is None:
        return {}

    try:
        memory = json.loads(row["memory_json"])
        return memory if isinstance(memory, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def save_memory(data: dict, session_key: str) -> None:
    _validate_session_key(session_key)

    memory_json = json.dumps(
        data,
        ensure_ascii=False
    )

    placeholder = "%s" if os.getenv("DATABASE_URL") else "?"

    with get_db_connection() as connection:
        existing = connection.execute(
            f"""
            SELECT session_key
            FROM memories
            WHERE session_key = {placeholder}
            """,
            (session_key,)
        ).fetchone()

        if existing is None:
            placeholders = (
                "%s, %s, %s, %s"
                if os.getenv("DATABASE_URL")
                else "?, ?, ?, ?"
            )

            import time
            now = int(time.time())

            connection.execute(
                f"""
                INSERT INTO memories (
                    session_key,
                    memory_json,
                    created_at,
                    updated_at
                )
                VALUES ({placeholders})
                """,
                (
                    session_key,
                    memory_json,
                    now,
                    now
                )
            )
        else:
            import time
            now = int(time.time())

            connection.execute(
                f"""
                UPDATE memories
                SET memory_json = {placeholder},
                    updated_at = {placeholder}
                WHERE session_key = {placeholder}
                """,
                (
                    memory_json,
                    now,
                    session_key
                )
            )

        connection.commit()