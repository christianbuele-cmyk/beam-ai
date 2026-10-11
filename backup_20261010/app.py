import json
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from agents.router import Router


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
BUTTONS_FILE = DATA_DIR / "buttons.json"
USERS_FILE = DATA_DIR / "users.json"

app = FastAPI()

router = Router()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class ShortcutCreate(BaseModel):
    name: str
    emoji: str
    instruction: str


class ShortcutUpdate(BaseModel):
    name: str
    emoji: str
    instruction: str


def initialize_buttons_file():
    DATA_DIR.mkdir(exist_ok=True)

    if not BUTTONS_FILE.exists():
        default_buttons = [
            {
                "id": str(uuid4()),
                "name": "Plan para hoy",
                "emoji": "🎉",
                "instruction": (
                    "Recomiéndame planes interesantes para hacer hoy cerca de mí."
                )
            },
            {
                "id": str(uuid4()),
                "name": "Escapada",
                "emoji": "🚗",
                "instruction": (
                    "Propón una escapada de fin de semana cerca de mi ubicación."
                )
            },
            {
                "id": str(uuid4()),
                "name": "Dónde comer",
                "emoji": "🍽️",
                "instruction": (
                    "Recomiéndame lugares interesantes para comer cerca de mí."
                )
            }
        ]

        save_buttons(default_buttons)


def load_buttons():
    initialize_buttons_file()

    try:
        with BUTTONS_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return []


def save_buttons(buttons):
    DATA_DIR.mkdir(exist_ok=True)

    with BUTTONS_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            buttons,
            file,
            ensure_ascii=False,
            indent=4
        )


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )


@app.get("/chat")
def chat(message: str):
    response = router.process(message)

    return {
        "user": message,
        "assistant": response
    }


@app.get("/shortcuts")
def get_shortcuts():
    return load_buttons()


@app.post("/shortcuts")
def create_shortcut(shortcut: ShortcutCreate):
    name = shortcut.name.strip()
    emoji = shortcut.emoji.strip()
    instruction = shortcut.instruction.strip()

    if not name or not instruction:
        raise HTTPException(
            status_code=400,
            detail="El nombre y la instrucción son obligatorios."
        )

    buttons = load_buttons()

    new_button = {
        "id": str(uuid4()),
        "name": name,
        "emoji": emoji or "✨",
        "instruction": instruction
    }

    buttons.append(new_button)
    save_buttons(buttons)

    return new_button


@app.put("/shortcuts/{shortcut_id}")
def update_shortcut(shortcut_id: str, shortcut: ShortcutUpdate):
    buttons = load_buttons()

    for button in buttons:
        if button["id"] == shortcut_id:
            button["name"] = shortcut.name.strip()
            button["emoji"] = shortcut.emoji.strip() or "✨"
            button["instruction"] = shortcut.instruction.strip()

            if not button["name"] or not button["instruction"]:
                raise HTTPException(
                    status_code=400,
                    detail="El nombre y la instrucción son obligatorios."
                )

            save_buttons(buttons)
            return button

    raise HTTPException(
        status_code=404,
        detail="No se ha encontrado el acceso rápido."
    )


@app.delete("/shortcuts/{shortcut_id}")
def delete_shortcut(shortcut_id: str):
    buttons = load_buttons()

    updated_buttons = [
        button
        for button in buttons
        if button["id"] != shortcut_id
    ]

    if len(updated_buttons) == len(buttons):
        raise HTTPException(
            status_code=404,
            detail="No se ha encontrado el acceso rápido."
        )

    save_buttons(updated_buttons)

    return {
        "deleted": True
    }
@app.get("/user")
def get_user():

    if not USERS_FILE.exists():
        return {"exists": False}

    try:
        content = USERS_FILE.read_text(
            encoding="utf-8-sig"
        ).strip()

        if not content:
            return {"exists": False}

        data = json.loads(content)

        if not isinstance(data, dict) or not data:
            return {"exists": False}

        return {
            "exists": True,
            "user": data
        }

    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
        OSError
    ) as error:

        print(f"Error leyendo users.json: {error}")

        return {"exists": False}


@app.post("/user")
async def save_user(request: Request):

    data = await request.json()

    DATA_DIR.mkdir(exist_ok=True)

    USERS_FILE.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )

    return {
        "saved": True
    }