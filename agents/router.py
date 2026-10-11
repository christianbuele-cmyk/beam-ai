from agents.assistant import AssistantAgent
from agents.calculator import CalculatorAgent
from agents.web_agent import WebAgent

class Router:

    def __init__(self):

        self.assistant = AssistantAgent()
        self.calculator = CalculatorAgent()
        self.web_agent = WebAgent()

    def process(self, message, session_key):

        message_lower = message.lower()

        if "calcula" in message_lower:
            return self.calculator.process(message)

        if "busca" in message_lower:
            return self.web_agent.process(message)

        return self.assistant.process(message, session_key)
