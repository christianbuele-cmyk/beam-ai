import os
from datetime import datetime

import google.generativeai as genai

genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)

model = genai.GenerativeModel(
    "gemini-3.8-flash"
)


def ask_llm(prompt, tone="profesional"):
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
Eres BEAM AI, un asistente personal inteligente.

Fecha actual: {fecha_actual}
Hora actual: {hora_actual}
Zona horaria: Europa/Madrid.

Utiliza el tratamiento de "tú" y evita el uso de "usted" salvo que el usuario lo solicite expresamente.

Habla de forma clara, útil y humana.

Tono seleccionado por el usuario:
{selected_tone_instruction}

Adapta tus respuestas al contexto del usuario y procura que la conversación resulte cercana y agradable.

Si te preguntan por la fecha o la hora actual utiliza la información anterior.

Máximo 150 palabras.

Pregunta:
{prompt}
"""

    try:

        response = model.generate_content(
            system_prompt
        )

        return response.text

    except Exception as e:

        error_text = str(e)

        if "429" in error_text or "ResourceExhausted" in error_text:

            return """
 BEAM AI ha alcanzado temporalmente el límite de consultas disponible.

Estamos utilizando una versión gratuita del servicio de IA y actualmente se ha agotado la cuota disponible.

Por favor, vuelve a intentarlo más tarde.
"""

        return f"""
 Se ha producido un error temporal.

Detalle técnico:

{error_text}
"""