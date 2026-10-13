import os
from datetime import datetime

import google.generativeai as genai

genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)

model = genai.GenerativeModel(
    "gemini-3.8-flash"
)


def ask_llm(prompt):

    now = datetime.now()

    fecha_actual = now.strftime("%d/%m/%Y")
    hora_actual = now.strftime("%H:%M")

    system_prompt = f"""
Eres BEAM AI.

Fecha actual: {fecha_actual}
Hora actual: {hora_actual}
Zona horaria: Europa/Madrid

Responde de forma natural.

Si te preguntan por la fecha o la hora actual,
utiliza la información anterior.

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