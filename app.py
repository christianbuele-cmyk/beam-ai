from pathlib import Path
from fastapi.responses import FileResponse
import hashlib
import hmac
import json
import os
import re
import sqlite3
import secrets
import time
import psycopg
from psycopg.rows import dict_row
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents.router import Router
from memory.memory_store import load_memory, save_memory
from database import get_db_connection


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "beam.db"
PROFILE_DIR = DATA_DIR / "profiles"
SHORTCUT_DIR = DATA_DIR / "shortcuts"
ACCOUNT_DIR = DATA_DIR / "accounts"
AUTH_SESSION_DIR = DATA_DIR / "auth_sessions"
PASSWORD_RESET_DIR = DATA_DIR / "password_resets"
SUPPORT_REQUEST_DIR = DATA_DIR / "support_requests"
MEMORY_DIR = BASE_DIR / "memory" / "sessions"
SESSION_COOKIE = "beam_session"
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def home():
    return FileResponse(
        BASE_DIR / "templates" / "index.html",
        media_type="text/html"
    )
router = Router()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

DEFAULT_SHORTCUTS = [
    {
        "name": "Plan para hoy",
        "emoji": "🎉",
        "instruction": "Recomiéndame planes interesantes para hacer hoy cerca de mí.",
    },
    {
        "name": "Escapada",
        "emoji": "🚗",
        "instruction": "Propón una escapada de fin de semana cerca de mi ubicación.",
    },
    {
        "name": "Dónde comer",
        "emoji": "🍽️",
        "instruction": "Recomiéndame lugares interesantes para comer cerca de mí.",
    },
]


class ShortcutCreate(BaseModel):
    name: str
    emoji: str = ""
    instruction: str


class ShortcutUpdate(BaseModel):
    name: str
    emoji: str = ""
    instruction: str


@app.middleware("http")
async def add_session_cookie(request: Request, call_next):
    session_id = request.cookies.get(SESSION_COOKIE, "")
    is_new_session = not SESSION_ID_PATTERN.fullmatch(session_id)
    if is_new_session:
        session_id = secrets.token_urlsafe(32)
    request.state.session_id = session_id

    response = await call_next(request)
    if is_new_session:
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
        is_https = request.url.scheme == "https" or forwarded_proto == "https"
        response.set_cookie(
            key=SESSION_COOKIE,
            value=session_id,
            httponly=True,
            secure=is_https,
            samesite="lax",
            path="/",
            max_age=60 * 60 * 24 * 365,
        )
    return response


def session_key(request: Request) -> str:
    """Return a non-reversible storage key for this browser session."""
    session_id = request.state.session_id
    if not SESSION_ID_PATTERN.fullmatch(session_id):
        raise HTTPException(status_code=401, detail="Sesión no válida.")
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def session_file(directory: Path, key: str) -> Path:
    return directory / f"{key}.json"

def initialize_database():
    with get_db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                email TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                session_key TEXT PRIMARY KEY,
                memory_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                session_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                profile_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )

        connection.commit()

initialize_database()


def normalize_email(email: str) -> str:
    return email.strip().lower()

def get_account_from_db(email: str):
    normalized_email = normalize_email(email)
    placeholder = "%s" if os.getenv("DATABASE_URL") else "?"

    with get_db_connection() as connection:
        return connection.execute(
            f"""
            SELECT email, session_id, salt, password_hash, created_at
            FROM accounts
            WHERE email = {placeholder}
            """,
            (normalized_email,)
        ).fetchone()

def create_account_in_db(
    email: str,
    session_id: str,
    salt: str,
    password_hash: str
):
    normalized_email = normalize_email(email)
    placeholders = "%s, %s, %s, %s, %s" if os.getenv("DATABASE_URL") else "?, ?, ?, ?, ?"

    with get_db_connection() as connection:
        connection.execute(
            f"""
            INSERT INTO accounts (
                email,
                session_id,
                salt,
                password_hash,
                created_at
            )
            VALUES ({placeholders})
            """,
            (
                normalized_email,
                session_id,
                salt,
                password_hash,
                int(time.time())
            )
        )
        connection.commit()

def update_account_password_in_db(
    email: str,
    salt: str,
    password_hash: str
):
    normalized_email = normalize_email(email)
    placeholder = "%s" if os.getenv("DATABASE_URL") else "?"

    with get_db_connection() as connection:
        connection.execute(
            f"""
            UPDATE accounts
            SET salt = {placeholder},
                password_hash = {placeholder}
            WHERE email = {placeholder}
            """,
            (
                salt,
                password_hash,
                normalized_email
            )
        )
        connection.commit()

def get_profile_from_db(session_id: str):
    placeholder = "%s" if os.getenv("DATABASE_URL") else "?"

    with get_db_connection() as connection:
        row = connection.execute(
            f"""
            SELECT profile_json
            FROM profiles
            WHERE session_id = {placeholder}
            """,
            (session_id,)
        ).fetchone()

    if row is None:
        return None

    try:
        return json.loads(row["profile_json"])
    except (json.JSONDecodeError, TypeError):
        return None


def save_profile_to_db(
    session_id: str,
    email: str,
    profile: dict
):
    normalized_email = normalize_email(email)
    profile_json = json.dumps(
        profile,
        ensure_ascii=False
    )
    now = int(time.time())

    existing_profile = get_profile_from_db(session_id)

    with get_db_connection() as connection:
        if existing_profile is None:
            placeholders = (
                "%s, %s, %s, %s, %s"
                if os.getenv("DATABASE_URL")
                else "?, ?, ?, ?, ?"
            )

            connection.execute(
                f"""
                INSERT INTO profiles (
                    session_id,
                    email,
                    profile_json,
                    created_at,
                    updated_at
                )
                VALUES ({placeholders})
                """,
                (
                    session_id,
                    normalized_email,
                    profile_json,
                    now,
                    now
                )
            )
        else:
            placeholder = "%s" if os.getenv("DATABASE_URL") else "?"

            connection.execute(
                f"""
                UPDATE profiles
                SET email = {placeholder},
                    profile_json = {placeholder},
                    updated_at = {placeholder}
                WHERE session_id = {placeholder}
                """,
                (
                    normalized_email,
                    profile_json,
                    now,
                    session_id
                )
            )

        connection.commit()

def account_key(email: str) -> str:
    normalized_email = normalize_email(email)
    return hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()


def hash_password(password: str, salt: bytes) -> str:
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        600_000
    )
    return password_hash.hex()


def create_password_credentials(password: str) -> dict:
    salt = secrets.token_bytes(32)

    return {
        "salt": salt.hex(),
        "password_hash": hash_password(password, salt)
    }


def verify_password(password: str, salt_hex: str, expected_hash: str) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False

    calculated_hash = hash_password(password, salt)

    return hmac.compare_digest(
        calculated_hash,
        expected_hash
    )

def read_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
    temporary_path.replace(path)
PASSWORD_RESET_TTL_SECONDS = 15 * 60


def create_password_reset_token(email: str) -> str:
    normalized_email = normalize_email(email)

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    reset_data = {
        "email": normalized_email,
        "token_hash": token_hash,
        "expires_at": int(time.time()) + PASSWORD_RESET_TTL_SECONDS,
        "used": False
    }

    reset_path = session_file(
        PASSWORD_RESET_DIR,
        token_hash
    )

    write_json(reset_path, reset_data)

    return token

def load_buttons(key: str):
    path = session_file(SHORTCUT_DIR, key)
    buttons = read_json(path, None)
    if buttons is None:
        buttons = [dict(item, id=str(uuid4())) for item in DEFAULT_SHORTCUTS]
        write_json(path, buttons)
    return buttons if isinstance(buttons, list) else []


def save_buttons(key: str, buttons):
    write_json(session_file(SHORTCUT_DIR, key), buttons)


@app.get("/chat")
def chat(
    request: Request,
    message: str,
    tone: str = "Profesional",
    agent_name: str = "BEAM AI"
):
    clean_agent_name = agent_name.strip() or "BEAM AI"

    session_id = request.state.session_id
    key = session_key(request)

    profile = get_profile_from_db(session_id)

    if not isinstance(profile, dict):
        profile = {}

    print("SESSION:", key)
    print("TONO SELECCIONADO:", tone)
    print("NOMBRE AGENTE:", clean_agent_name)

    response = router.process(
        message,
        key,
        tone,
        clean_agent_name,
        profile
    )
    return {
        "user": message,
        "assistant": response
    }

@app.get("/shortcuts")
def get_shortcuts(request: Request):
    buttons = load_buttons(session_key(request))
    return JSONResponse(buttons, headers={"Cache-Control": "no-store"})


@app.post("/shortcuts")
def create_shortcut(request: Request, shortcut: ShortcutCreate):
    name = shortcut.name.strip()
    emoji = shortcut.emoji.strip()
    instruction = shortcut.instruction.strip()
    if not name or not instruction:
        raise HTTPException(status_code=400, detail="El nombre y la instrucción son obligatorios.")

    key = session_key(request)
    buttons = load_buttons(key)
    new_button = {
        "id": str(uuid4()),
        "name": name,
        "emoji": emoji or "✨",
        "instruction": instruction,
    }
    buttons.append(new_button)
    save_buttons(key, buttons)
    return new_button


@app.put("/shortcuts/{shortcut_id}")
def update_shortcut(request: Request, shortcut_id: str, shortcut: ShortcutUpdate):
    key = session_key(request)
    buttons = load_buttons(key)
    for button in buttons:
        if button["id"] == shortcut_id:
            name = shortcut.name.strip()
            instruction = shortcut.instruction.strip()
            if not name or not instruction:
                raise HTTPException(status_code=400, detail="El nombre y la instrucción son obligatorios.")
            button.update({"name": name, "emoji": shortcut.emoji.strip() or "✨", "instruction": instruction})
            save_buttons(key, buttons)
            return button
    raise HTTPException(status_code=404, detail="No se ha encontrado el acceso rápido.")


@app.delete("/shortcuts/{shortcut_id}")
def delete_shortcut(request: Request, shortcut_id: str):
    key = session_key(request)
    buttons = load_buttons(key)
    updated_buttons = [button for button in buttons if button["id"] != shortcut_id]
    if len(updated_buttons) == len(buttons):
        raise HTTPException(status_code=404, detail="No se ha encontrado el acceso rápido.")
    save_buttons(key, updated_buttons)
    return {"deleted": True}


@app.get("/user")
def get_user(request: Request):
    session_id = request.state.session_id

    user = get_profile_from_db(session_id)

    if not isinstance(user, dict) or not user:
        key = session_key(request)
        user = read_json(session_file(PROFILE_DIR, key), None)

        if isinstance(user, dict) and user:
            email = normalize_email(str(user.get("email", "")))

            if email:
                save_profile_to_db(
                    session_id=session_id,
                    email=email,
                    profile=user
                )

    if not isinstance(user, dict) or not user:
        return JSONResponse(
            {"exists": False},
            headers={"Cache-Control": "no-store"}
        )

    return JSONResponse(
        {"exists": True, "user": user},
        headers={"Cache-Control": "no-store"}
    )


@app.post("/user")
async def save_user(request: Request):
    try:
        user = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="El perfil debe ser JSON válido."
        )

    if not isinstance(user, dict) or not user:
        raise HTTPException(
            status_code=400,
            detail="El perfil no es válido."
        )

    name = str(user.get("name", "")).strip()
    email = normalize_email(str(user.get("email", "")))
    password = str(user.pop("password", ""))
    city = str(user.get("city", "")).strip()
    about = str(user.get("about", "")).strip()
    interests = user.get("interests", [])

    if len(name) < 2:
        raise HTTPException(
            status_code=400,
            detail="El nombre debe tener al menos 2 caracteres."
        )

    if len(name) > 50:
        raise HTTPException(
            status_code=400,
            detail="El nombre es demasiado largo."
        )

    if not email or "@" not in email:
        raise HTTPException(
            status_code=400,
            detail="Introduce un correo electrónico válido."
        )

    if len(city) > 50:
        raise HTTPException(
            status_code=400,
            detail="La ciudad es demasiado larga."
        )

    if len(about) > 500:
        raise HTTPException(
            status_code=400,
            detail="La descripción es demasiado larga."
        )

    if not isinstance(interests, list):
        raise HTTPException(
            status_code=400,
            detail="Los intereses no son válidos."
        )

    if len(interests) > 30:
        raise HTTPException(
            status_code=400,
            detail="Máximo 30 intereses."
    )

    session_id = request.state.session_id
    key = session_key(request)
    profile_path = session_file(PROFILE_DIR, key)

    existing_profile = get_profile_from_db(session_id)

    if not isinstance(existing_profile, dict) or not existing_profile:
        existing_profile = read_json(profile_path, None)

    existing_db_account = get_account_from_db(email)

    if not isinstance(existing_profile, dict) or not existing_profile:
        if existing_db_account is not None:
            account_session_id = str(existing_db_account["session_id"])

            if account_session_id != session_id:
                raise HTTPException(
                    status_code=409,
                    detail="Ya existe una cuenta con este correo electrónico."
                )
        else:
            if len(password) < 8:
                raise HTTPException(
                    status_code=400,
                    detail="La contraseña debe tener al menos 8 caracteres."
                )

            email_key = account_key(email)
            account_path = session_file(ACCOUNT_DIR, email_key)
            existing_account = read_json(account_path, None)

            if isinstance(existing_account, dict) and existing_account:
                raise HTTPException(
                    status_code=409,
                    detail="Ya existe una cuenta con este correo electrónico."
                )

            credentials = create_password_credentials(password)

            account = {
                "email": email,
                "session_id": session_id,
                "salt": credentials["salt"],
                "password_hash": credentials["password_hash"]
            }

            create_account_in_db(
                email=email,
                session_id=session_id,
                salt=credentials["salt"],
                password_hash=credentials["password_hash"]
            )

            write_json(account_path, account)

    user["name"] = name
    user["email"] = email
    user["city"] = city
    user["about"] = about
    user["interests"] = interests[:30]

    save_profile_to_db(
        session_id=session_id,
        email=email,
        profile=user
    )

    write_json(profile_path, user)
  
    return {"saved": True}
@app.post("/login")
async def login(request: Request):
    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="Los datos de acceso no son válidos."
        )

    email = normalize_email(str(data.get("email", "")))
    password = str(data.get("password", ""))

    if not email or not password:
        raise HTTPException(
            status_code=400,
            detail="Introduce el correo electrónico y la contraseña."
        )

    account = get_account_from_db(email)

    if account is None:
        raise HTTPException(
            status_code=401,
            detail="Correo electrónico o contraseña incorrectos."
        )

    if not verify_password(
        password,
        str(account["salt"]),
        str(account["password_hash"])
    ):
        raise HTTPException(
            status_code=401,
            detail="Correo electrónico o contraseña incorrectos."
        )

    original_session_id = str(account["session_id"])

    if not SESSION_ID_PATTERN.fullmatch(original_session_id):
        raise HTTPException(
            status_code=401,
            detail="La cuenta no tiene una sesión válida asociada."
        )

    response = JSONResponse({
        "logged_in": True
    })

    forwarded_proto = request.headers.get(
        "x-forwarded-proto",
        ""
    ).split(",")[0].strip()

    is_https = (
        request.url.scheme == "https"
        or forwarded_proto == "https"
    )

    response.set_cookie(
        key=SESSION_COOKIE,
        value=original_session_id,
        httponly=True,
        secure=is_https,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 24 * 365,
    )

    return response
@app.post("/forgot-password")
async def forgot_password(request: Request):
    generic_response = {
        "requested": True,
        "message": (
            "Si existe una cuenta asociada a ese correo electrónico, "
            "recibirás las instrucciones para restablecer tu contraseña."
        )
    }

    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="Los datos enviados no son válidos."
        )

    email = normalize_email(str(data.get("email", "")))

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Introduce un correo electrónico válido."
        )

    email_key = account_key(email)
    account_path = session_file(ACCOUNT_DIR, email_key)
    account = read_json(account_path, None)

    if not isinstance(account, dict) or not account:
        return generic_response

    token = create_password_reset_token(email)

    reset_url = str(
        request.base_url.replace(
            path="/",
            query=None,
            fragment=None
        )
    ).rstrip("/") + f"/?reset_token={token}"

    response_data = dict(generic_response)

    if request.client and request.client.host in {
        "127.0.0.1",
        "::1",
        "localhost"
    }:
        response_data["development_reset_url"] = reset_url
        print(f"[BEAM AI] Enlace local de recuperación: {reset_url}")

    return response_data


@app.post("/change-password")
async def change_password(request: Request):
    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="Los datos enviados no son válidos."
        )

    current_password = str(data.get("current_password", ""))
    new_password = str(data.get("new_password", ""))

    if not current_password or not new_password:
        raise HTTPException(
            status_code=400,
            detail="Completa todos los campos."
        )

    if len(new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="La nueva contraseña debe tener al menos 8 caracteres."
        )

    key = session_key(request)
    profile = read_json(
        session_file(PROFILE_DIR, key),
        None
    )

    if not isinstance(profile, dict) or not profile:
        raise HTTPException(
            status_code=401,
            detail="No se ha encontrado una sesión de usuario válida."
        )

    email = normalize_email(
        str(profile.get("email", ""))
    )

    if not email:
        raise HTTPException(
            status_code=400,
            detail="La cuenta no tiene un correo electrónico asociado."
        )

    account = get_account_from_db(email)

    if account is None:
        raise HTTPException(
            status_code=404,
            detail="No se ha encontrado la cuenta."
        )

    if not verify_password(
        current_password,
        str(account["salt"]),
        str(account["password_hash"])
    ):
        raise HTTPException(
            status_code=401,
            detail="La contraseña actual no es correcta."
        )

    credentials = create_password_credentials(
        new_password
    )

    update_account_password_in_db(
        email=email,
        salt=credentials["salt"],
        password_hash=credentials["password_hash"]
    )


    return {
        "password_changed": True
    }
@app.post("/reset-password")
async def reset_password(request: Request):
    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="Los datos enviados no son válidos."
        )

    token = str(data.get("token", "")).strip()
    new_password = str(data.get("new_password", ""))

    if not token or not new_password:
        raise HTTPException(
            status_code=400,
            detail="Completa todos los campos."
        )

    if len(new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="La nueva contraseña debe tener al menos 8 caracteres."
        )

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    reset_path = session_file(
        PASSWORD_RESET_DIR,
        token_hash
    )

    reset_data = read_json(
        reset_path,
        None
    )

    if not isinstance(reset_data, dict) or not reset_data:
        raise HTTPException(
            status_code=400,
            detail="El enlace de recuperación no es válido."
        )

    if reset_data.get("used") is True:
        raise HTTPException(
            status_code=400,
            detail="Este enlace de recuperación ya se ha utilizado."
        )

    expires_at = int(reset_data.get("expires_at", 0))

    if int(time.time()) > expires_at:
        raise HTTPException(
            status_code=400,
            detail="El enlace de recuperación ha caducado."
        )

    stored_token_hash = str(
        reset_data.get("token_hash", "")
    )

    if not hmac.compare_digest(
        token_hash,
        stored_token_hash
    ):
        raise HTTPException(
            status_code=400,
            detail="El enlace de recuperación no es válido."
        )

    email = normalize_email(
        str(reset_data.get("email", ""))
    )

    if not email:
        raise HTTPException(
            status_code=400,
            detail="El enlace de recuperación no es válido."
        )

    account = get_account_from_db(email)

    if account is None:
        raise HTTPException(
            status_code=400,
            detail="No se ha encontrado la cuenta."
        )

    credentials = create_password_credentials(
        new_password
    )

    update_account_password_in_db(
        email=email,
        salt=credentials["salt"],
        password_hash=credentials["password_hash"]
    )

    reset_data["used"] = True

    write_json(
        reset_path,
        reset_data
    )

    response = JSONResponse({
        "password_reset": True
    })

    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        samesite="lax"
    )

    return response
@app.post("/logout")
def logout(request: Request):
    response = JSONResponse({
        "logged_out": True
    })

    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        samesite="lax"
    )

    return response
@app.get("/export-data")
def export_user_data(request: Request):
    key = session_key(request)

    profile = read_json(
        session_file(PROFILE_DIR, key),
        {}
    )

    shortcuts = read_json(
        session_file(SHORTCUT_DIR, key),
        []
    )

    memory = read_json(
        session_file(MEMORY_DIR, key),
        {}
    )

    if not isinstance(profile, dict):
        profile = {}

    if not isinstance(shortcuts, list):
        shortcuts = []

    if not isinstance(memory, dict):
        memory = {}

    export_data = {
        "profile": profile,
        "shortcuts": shortcuts,
        "memory": memory
    }

    content = json.dumps(
        export_data,
        ensure_ascii=False,
        indent=2
    )

    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition":
                'attachment; filename="beam-ai-data.json"'
        }
    )

@app.delete("/user")
def delete_user(request: Request):
    key = session_key(request)

    user_files = [
        session_file(PROFILE_DIR, key),
        session_file(SHORTCUT_DIR, key),
        session_file(MEMORY_DIR, key),
    ]

    for path in user_files:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    response = JSONResponse({
        "deleted": True
    })

    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        samesite="lax"
    )

    return response
@app.get("/memory")
def get_memory(request: Request):
    key = session_key(request)
    memory = load_memory(key)

    if not isinstance(memory, dict):
        memory = {}

    history = memory.get("history", [])
    if not isinstance(history, list):
        history = []

    return JSONResponse(
        {
            "enabled": memory.get("enabled", True),
            "history": history
        },
        headers={"Cache-Control": "no-store"}
    )

@app.put("/memory")
async def update_memory(request: Request):
    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="La configuración de memoria debe ser JSON válido."
        )

    enabled = data.get("enabled")

    if not isinstance(enabled, bool):
        raise HTTPException(
            status_code=400,
            detail="El estado de memoria debe ser true o false."
        )

    key = session_key(request)
    memory = load_memory(key)

    if not isinstance(memory, dict):
        memory = {}

    memory["enabled"] = enabled
    save_memory(memory, key)

    return {"saved": True, "enabled": enabled}

@app.delete("/memory")
def reset_memory(request: Request):
    key = session_key(request)
    path = session_file(MEMORY_DIR, key)

    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        raise HTTPException(status_code=500, detail="No se ha podido reiniciar la memoria.")

    return {"reset": True}
@app.post("/support-request")
async def create_support_request(request: Request):
    try:
        data = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=400,
            detail="La solicitud de soporte debe ser JSON válido."
        )

    request_type = str(data.get("type", "chat")).strip().lower()
    subject = str(data.get("subject", "")).strip()
    phone = str(data.get("phone", "")).strip()
    message = str(data.get("message", "")).strip()
    category = str(data.get("category", "")).strip()
    details = str(data.get("details", "")).strip()

    if request_type not in {"chat", "email", "callback", "error", "suggestion"}:
        raise HTTPException(
            status_code=400,
            detail="El tipo de solicitud de soporte no es válido."
        )
    if not message:
        raise HTTPException(
            status_code=400,
            detail="Describe tu consulta antes de enviarla."
        )

    max_message_length = 2000 if request_type == "email" else 1000

    if len(message) > max_message_length:
        raise HTTPException(
            status_code=400,
            detail=f"La consulta no puede superar los {max_message_length} caracteres."
        )

    if request_type == "error":
        if not category:
            raise HTTPException(
                status_code=400,
                detail="Selecciona el tipo de problema."
            )

        if len(category) > 80:
            raise HTTPException(
                status_code=400,
                detail="El tipo de problema no es válido."
            )

        if len(details) > 1000:
            raise HTTPException(
                status_code=400,
                detail="Los detalles adicionales no pueden superar los 1000 caracteres."
            )
   
    if request_type == "email":
        if not subject:
            raise HTTPException(
                status_code=400,
                detail="Introduce un asunto antes de enviar el mensaje."
            )

        if len(subject) > 120:
            raise HTTPException(
                status_code=400,
                detail="El asunto no puede superar los 120 caracteres."
            )

    if request_type == "callback":
        phone_digits = re.sub(r"\D", "", phone)

        if not phone.startswith("+") or len(phone_digits) < 7 or len(phone_digits) > 15:
            raise HTTPException(
                status_code=400,
                detail="Introduce un número de teléfono válido."
            )

    key = session_key(request)
    path = session_file(SUPPORT_REQUEST_DIR, key)

    requests = read_json(path, [])

    if not isinstance(requests, list):
        requests = []

    support_request = {
        "id": str(uuid4()),
        "type": request_type,
        "message": message,
        "created_at": int(time.time()),
        "status": "received"
    }

    if request_type == "error":
        support_request["category"] = category

    if request_type in {"error", "suggestion"} and details:
        support_request["details"] = details

    if request_type == "email":
        support_request["subject"] = subject

    if request_type == "callback":
        support_request["phone"] = phone

    requests.append(support_request)
    write_json(path, requests)

    return {
        "submitted": True,
        "request_id": support_request["id"]
    }