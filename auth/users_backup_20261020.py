import json
import hashlib
from pathlib import Path

USERS_FILE = Path("data/users_db.json")


def load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_users(users):
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            users,
            f,
            indent=2,
            ensure_ascii=False
        )


def find_user(email):
    users = load_users()

    for user in users:
        if user["email"].lower() == email.lower():
            return user

    return None


def hash_password(password):
    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


def create_user(name, email, password):
    users = load_users()

    if find_user(email):
        return False

    new_user = {
        "id": len(users) + 1,
        "name": name,
        "email": email,
        "password_hash": hash_password(password)
    }

    users.append(new_user)

    save_users(users)

    return True
def validate_user(email, password):
    user = find_user(email)

    if not user:
        return None

    password_hash = hash_password(password)

    if user["password_hash"] != password_hash:
        return None

    return user
