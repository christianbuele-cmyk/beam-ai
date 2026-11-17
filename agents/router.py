import re
from agents.assistant import AssistantAgent
from agents.calculator import CalculatorAgent
from agents.web_agent import WebAgent


class Router:

    def __init__(self):
        self.assistant = AssistantAgent()
        self.calculator = CalculatorAgent()
        self.web_agent = WebAgent()

    def process(
        self,
        message,
        session_key,
        tone="Profesional",
        agent_name="BRLOX AI",
        profile=None,
        conversation_id=""
    ):
        message_lower = message.lower()

        if "calcula" in message_lower:
            return self.calculator.process(message)

        if "noticias" in message_lower:
            return self.web_agent.process(message)

        current_intent = any(term in message_lower for term in [
            "qué hay de nuevo",
            "que hay de nuevo",
            "qué está pasando",
            "que esta pasando",
            "lo último",
            "lo ultimo",
            "novedades",
            "actualidad",
            "hoy"
        ])

        technology_topic = any(term in message_lower for term in [
            "tecnología",
            "tecnologia",
            "inteligencia artificial",
            "openai",
            "chatgpt",
            "gemini",
            "copilot"
        ])

        economy_topic = any(term in message_lower for term in [
            "economía",
            "economia",
            "económica",
            "economica",
            "económicas",
            "economicas",
            "económico",
            "economico",
            "económicos",
            "economicos"
        ])

        ia_topic = re.search(
            r"\bia\b",
            message_lower
        ) is not None

        if current_intent and (
            technology_topic
            or ia_topic
            or economy_topic
        ):
            return self.web_agent.process(
                f"noticias {message}"
            )

        if any(word in message_lower for word in [
            "deportes",
            "deportivo",
            "deportiva",
            "deportivos",
            "deportivas",
            "fútbol",
            "futbol"
        ]):
            return self.web_agent.process(
                f"noticias deportivas {message}"
            )

        if "busca" in message_lower:
            return self.web_agent.process(message)


        return self.assistant.process(
            message,
            session_key,
            tone,
            agent_name,
            profile,
            conversation_id
        )