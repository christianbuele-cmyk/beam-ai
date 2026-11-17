import os
import time
from datetime import datetime

import google.generativeai as genai
from openai import OpenAI
from opentelemetry import metrics

meter = metrics.get_meter("brlox-ai.llm")

ai_requests = meter.create_counter(
    "brlox_ai_requests",
    description="Numero de llamadas realizadas a proveedores de IA",
)

ai_errors = meter.create_counter(
    "brlox_ai_errors",
    description="Numero de errores producidos por proveedores de IA",
)

ai_fallbacks = meter.create_counter(
    "brlox_ai_fallbacks",
    description="Numero de activaciones del fallback entre proveedores de IA",
)

ai_duration_ms = meter.create_histogram(
    "brlox_ai_duration_ms",
    unit="ms",
    description="Duracion de las llamadas a proveedores de IA en milisegundos",
)


genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)

model = genai.GenerativeModel(
    "gemini-3.8-flash"
)

grok_client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)

def ask_grok(prompt: str) -> str:
    grok_attributes = {
        "provider": "grok",
        "model": "grok-4.7",
    }

    ai_requests.add(1, grok_attributes)
    grok_started = time.perf_counter()

    try:
        response = grok_client.responses.create(
            model="grok-4.7",
            input=prompt
        )

        ai_duration_ms.record(
            (time.perf_counter() - grok_started) * 1000,
            {**grok_attributes, "status": "success"},
        )

        return response.output_text

    except Exception:
        ai_duration_ms.record(
            (time.perf_counter() - grok_started) * 1000,
            {**grok_attributes, "status": "error"},
        )

        ai_errors.add(1, grok_attributes)
        raise

def ask_llm(prompt, tone="profesional", agent_name="BRLOX AI"):
    tone_key = str(tone or "profesional").strip().lower()

    tone_instructions = {
        "cercano": (
            "Utiliza un tono cercano, cálido y natural. "
            "Habla como alguien de confianza, con expresiones informales moderadas."
        ),
        "profesional": (
            "Utiliza un tono profesional, educado y claro. "
            "Evita bromas y expresiones excesivamente coloquiales."
        ),
        "divertido": (
            "Utiliza un tono divertido, dinámico y juguetón. "
            "Puedes añadir humor ligero cuando encaje, sin perder claridad ni utilidad."
        ),
        "directo": (
            "Utiliza un tono directo y conciso. "
            "Ve al grano, utiliza frases claras y evita rodeos innecesarios."
        )
    }

    selected_tone_instruction = tone_instructions.get(
        tone_key,
        tone_instructions["profesional"]
    )

    now = datetime.now()

    fecha_actual = now.strftime("%d/%m/%Y")
    hora_actual = now.strftime("%H:%M")

    system_prompt = f"""
Tu nombre actual como agente personal es {agent_name}.

BRLOX AI es únicamente el nombre de la aplicación y de la plataforma.
BRLOX AI no es tu nombre personal cuando el usuario ha configurado otro nombre.

Cuando hables de tu identidad, te presentes, saludes o respondas a la pregunta
"¿cómo te llamas?", debes utilizar siempre el nombre {agent_name}.

Si el usuario te saluda usando el nombre {agent_name}, reconoce ese nombre
como propio y continúa la conversación con naturalidad.

Si el historial de conversación contiene una respuesta anterior donde afirmabas
llamarte BRLOX AI o tener otro nombre, considera esa respuesta obsoleta.
La configuración actual del nombre tiene prioridad sobre el historial.

No corrijas al usuario por llamarte {agent_name}.
No digas que tu nombre es BRLOX AI cuando el nombre configurado sea diferente.
Identidad y origen:
Si el usuario pregunta quién eres, responde utilizando siempre tu nombre actual {agent_name}.

Si el usuario pregunta quién te ha creado, quién te ha desarrollado, quién está detrás de ti
o cuál es tu origen, explica que formas parte de la plataforma BRLOX AI.

No atribuyas la creación o el desarrollo de BRLOX AI a Google, Gemini ni al proveedor
del modelo de lenguaje utilizado internamente.

No confundas el proveedor tecnológico del modelo con la identidad, autoría o desarrollo
de BRLOX AI.

Ejemplo de presentación:
"¡Hola! Mi nombre es {agent_name} y soy tu asistente personal inteligente."

Fecha actual: {fecha_actual}
Hora actual: {hora_actual}
Zona horaria: Europa/Madrid.

Utiliza el tratamiento de "tú" y evita el uso de "usted" salvo que el usuario lo solicite expresamente.

Habla de forma clara, útil y humana.

Tono seleccionado por el usuario:
{selected_tone_instruction}

Adapta tus respuestas al contexto del usuario y procura que la conversación resulte cercana y agradable.

Idioma de respuesta:
Responde siempre en el mismo idioma en el que el usuario realiza su consulta.

Si el usuario cambia de idioma durante la conversación, adapta la respuesta al nuevo idioma utilizado.

No cambies de idioma por iniciativa propia, salvo que el usuario solicite expresamente una traducción o pida responder en otro idioma.

Si te preguntan por la fecha o la hora actual utiliza la información anterior.

Máximo 150 palabras.

Pregunta:
{prompt}
"""

    gemini_attributes = {
        "provider": "gemini",
        "model": "gemini-3.8-flash",
    }

    ai_requests.add(1, gemini_attributes)
    gemini_started = time.perf_counter()

    try:
        response = model.generate_content(
            system_prompt,
            request_options={"timeout": 15}
        )

        ai_duration_ms.record(
            (time.perf_counter() - gemini_started) * 1000,
            {**gemini_attributes, "status": "success"},
        )

        return response.text

    except Exception as e:
        error_text = str(e)

        ai_duration_ms.record(
            (time.perf_counter() - gemini_started) * 1000,
            {**gemini_attributes, "status": "error"},
        )

        ai_errors.add(1, gemini_attributes)

        print("ERROR REAL DE GEMINI:", repr(error_text))
        print("GEMINI NO DISPONIBLE - INTENTANDO GROK")

        ai_fallbacks.add(
            1,
            {
                "from_provider": "gemini",
                "to_provider": "grok",
            },
        )

        try:
            grok_response = ask_grok(system_prompt)

            print("RESPUESTA OBTENIDA DESDE GROK")

            return grok_response

        except Exception as grok_error:
            print("ERROR REAL DE GROK:", repr(str(grok_error)))

            return (
                "BRLOX AI no puede procesar tu consulta en este momento.\n\n"
                "Se ha producido un error temporal. Inténtalo de nuevo más tarde."
            )