from memory.memory_store import load_memory, save_memory
from agents.llm_agent import ask_llm


class AssistantAgent:

    def process(
        self,
        message: str,
        session_key: str,
        tone: str = "Profesional",
        agent_name: str = "BEAM AI"
    ):
        memory = load_memory(session_key)
        history = memory.get("history", [])

        if message.lower().startswith("me llamo"):
            name = message[8:].strip()
            memory["name"] = name

        history.append({
            "role": "user",
            "content": message
        })

        context = ""

        for item in history[-10:]:
            context += f"{item['role']}: {item['content']}\n"

        prompt = f"""
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

        history.append({
            "role": "assistant",
            "content": response
        })

        memory["history"] = history[-20:]

        print("NOMBRE DEL AGENTE EN ASSISTANT:", agent_name)
        print("GUARDANDO MEMORIA")
        print(memory)

        save_memory(memory, session_key)

        print("MEMORIA GUARDADA")

        return response