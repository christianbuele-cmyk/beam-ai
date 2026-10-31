from pathlib import Path
from fastapi.responses import FileResponse
import hashlib
import hmac
import json
import re
import secrets
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from agents.router import Router


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PROFILE_DIR = DATA_DIR / "profiles"
SHORTCUT_DIR = DATA_DIR / "shortcuts"
ACCOUNT_DIR = DATA_DIR / "accounts"
AUTH_SESSION_DIR = DATA_DIR / "auth_sessions"
MEMORY_DIR = BASE_DIR / "memory" / "sessions"
SESSION_COOKIE = "beam_session"
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent


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
def normalize_email(email: str) -> str:
    return email.strip().lower()


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

    print("SESSION:", session_key(request))
    print("TONO SELECCIONADO:", tone)
    print("NOMBRE AGENTE:", clean_agent_name)

    response = router.process(
        message,
        session_key(request),
        tone,
        clean_agent_name
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
    key = session_key(request)
    user = read_json(session_file(PROFILE_DIR, key), None)
    if not isinstance(user, dict) or not user:
        return JSONResponse({"exists": False}, headers={"Cache-Control": "no-store"})
    return JSONResponse({"exists": True, "user": user}, headers={"Cache-Control": "no-store"})


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

    if len(interests) > 10:
        raise HTTPException(
            status_code=400,
            detail="Máximo 10 intereses."
        )

    key = session_key(request)
    profile_path = session_file(PROFILE_DIR, key)
    existing_profile = read_json(profile_path, None)

    if not isinstance(existing_profile, dict) or not existing_profile:
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
            "session_id": request.state.session_id,
            "salt": credentials["salt"],
            "password_hash": credentials["password_hash"]
        }

        write_json(account_path, account)

    user["name"] = name
    user["email"] = email
    user["city"] = city
    user["about"] = about
    user["interests"] = interests[:10]

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

    email_key = account_key(email)
    account_path = session_file(ACCOUNT_DIR, email_key)
    account = read_json(account_path, None)

    if not isinstance(account, dict) or not account:
        raise HTTPException(
            status_code=401,
            detail="Correo electrónico o contraseña incorrectos."
        )

    if not verify_password(
        password,
        str(account.get("salt", "")),
        str(account.get("password_hash", ""))
    ):
        raise HTTPException(
            status_code=401,
            detail="Correo electrónico o contraseña incorrectos."
        )

    original_session_id = str(account.get("session_id", ""))

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

    email_key = account_key(email)
    account_path = session_file(
        ACCOUNT_DIR,
        email_key
    )

    account = read_json(
        account_path,
        None
    )

    if not isinstance(account, dict) or not account:
        raise HTTPException(
            status_code=404,
            detail="No se ha encontrado la cuenta."
        )

    if not verify_password(
        current_password,
        str(account.get("salt", "")),
        str(account.get("password_hash", ""))
    ):
        raise HTTPException(
            status_code=401,
            detail="La contraseña actual no es correcta."
        )

    credentials = create_password_credentials(
        new_password
    )

    account["salt"] = credentials["salt"]
    account["password_hash"] = credentials["password_hash"]

    write_json(
        account_path,
        account
    )

    return {
        "password_changed": True
    }
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
    memory = read_json(session_file(MEMORY_DIR, key), {})

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
        raise HTTPException(status_code=400, detail="La configuración de memoria debe ser JSON válido.")

    enabled = data.get("enabled")

    if not isinstance(enabled, bool):
        raise HTTPException(status_code=400, detail="El estado de memoria debe ser true o false.")

    key = session_key(request)
    path = session_file(MEMORY_DIR, key)
    memory = read_json(path, {})

    if not isinstance(memory, dict):
        memory = {}

    memory["enabled"] = enabled
    write_json(path, memory)

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