from memory.memory_store import load_memory, save_memory
from agents.llm_agent import ask_llm

class AssistantAgent:

    def process(self, message: str, session_key: str):

        memory = load_memory(session_key)

        message = message.lower()

        if "como me llamo" in message:

            if "name" in memory:
                return f"Te llamas {memory['name']}"

            return "Todavía no sé tu nombre."

        if message.startswith("me llamo"):

            name = message.replace("me llamo", "").strip()

            memory["name"] = name

            save_memory(memory, session_key)

            return f"Encantado {name}"

        return ask_llm(message)
