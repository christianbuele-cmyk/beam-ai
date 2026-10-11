import json
import re
from pathlib import Path


MEMORY_DIR = Path(__file__).resolve().parent / "sessions"
SESSION_KEY_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def _memory_file(session_key: str) -> Path:
    if not SESSION_KEY_PATTERN.fullmatch(session_key):
        raise ValueError("A valid per-session key is required for memory storage.")
    return MEMORY_DIR / f"{session_key}.json"


def load_memory(session_key: str) -> dict:
    path = _memory_file(session_key)
    try:
        with path.open("r", encoding="utf-8") as file:
            memory = json.load(file)
            return memory if isinstance(memory, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_memory(data: dict, session_key: str) -> None:
    path = _memory_file(session_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".json.tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    temporary_path.replace(path)
