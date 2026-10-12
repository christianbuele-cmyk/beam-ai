import os
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-3.8-flash")

def ask_llm(prompt):

    system_prompt = f"""
Eres BEAM AI.

Responde de manera profesional.
Máximo 150 palabras.

Pregunta:
{prompt}
"""

    response = model.generate_content(system_prompt)

    return response.text