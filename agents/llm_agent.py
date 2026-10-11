import requests

def ask_llm(prompt):

    system_prompt = f"""
Eres BEAM AI.

Responde de manera profesional.
Máximo 150 palabras.

Pregunta:
{prompt}
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2",
            "prompt": system_prompt,
            "stream": False
        }
    )

    return response.json()["response"]