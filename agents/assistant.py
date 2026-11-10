from memory.memory_store import load_memory, save_memory
from agents.llm_agent import ask_llm


class AssistantAgent:

    def process(
        self,
        message: str,
        session_key: str,
        tone: str = "Profesional",
        agent_name: str = "BEAM AI",
        about: str = ""
    ):

        memory = load_memory(session_key)
        memory_enabled = memory.get("enabled", True)

        history = memory.get("history", []) if memory_enabled else []

        if not isinstance(history, list):
            history = []

        if memory_enabled and message.lower().startswith("me llamo"):
            name = message[8:].strip()
            memory["name"] = name

        history.append({
            "role": "user",
            "content": message
        })

        context = ""

        for item in history[-10:]:
            context += f"{item['role']}: {item['content']}\n"

        personal_context = ""

        if about.strip():
            personal_context = f"""
Información personal proporcionada por el usuario:
{about.strip()}

Utiliza esta información para personalizar la respuesta cuando sea relevante.
No menciones estos datos innecesariamente.
No inventes información adicional sobre el usuario.
Si una recomendación pudiera entrar en conflicto con esta información personal,
tenla en cuenta y adapta la respuesta.
"""

        prompt = f"""
{personal_context}

Historial de conversación:

{context}

Usuario:
{message}
"""
        response = ask_llm(
            prompt,
            tone=tone,
            agent_name=agent_name
        )

        if memory_enabled:
            history.append({
                "role": "assistant",
                "content": response
            })

            memory["history"] = history

            print("NOMBRE DEL AGENTE EN ASSISTANT:", agent_name)
            print("GUARDANDO MEMORIA")
            print(memory)

            save_memory(memory, session_key)

            print("MEMORIA GUARDADA")
        else:
            print("MEMORIA DESACTIVADA - historial no guardado")

        return response