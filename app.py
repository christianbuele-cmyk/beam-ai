import hashlib
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
MEMORY_DIR = BASE_DIR / "memory" / "sessions"
SESSION_COOKIE = "beam_session"
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")

app = FastAPI()
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


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/chat")
def chat(request: Request, message: str):

    print("SESSION:", session_key(request))

    response = router.process(
        message,
        session_key(request)
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
        raise HTTPException(status_code=400, detail="El perfil debe ser JSON válido.")

    if not isinstance(user, dict) or not user:
        raise HTTPException(status_code=400, detail="El perfil no es válido.")

    name = str(user.get("name", "")).strip()
    city = str(user.get("city", "")).strip()
    about = str(user.get("about", "")).strip()
    interests = user.get("interests", [])

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="El nombre debe tener al menos 2 caracteres.")

    if len(name) > 50:
        raise HTTPException(status_code=400, detail="El nombre es demasiado largo.")

    if len(city) > 50:
        raise HTTPException(status_code=400, detail="La ciudad es demasiado larga.")

    if len(about) > 500:
        raise HTTPException(status_code=400, detail="La descripción es demasiado larga.")

    if not isinstance(interests, list):
        raise HTTPException(status_code=400, detail="Los intereses no son válidos.")

    if len(interests) > 10:
        raise HTTPException(status_code=400, detail="Máximo 10 intereses.")

    user["name"] = name
    user["city"] = city
    user["about"] = about
    user["interests"] = interests[:10]

    key = session_key(request)
    write_json(session_file(PROFILE_DIR, key), user)

    return {"saved": True}
