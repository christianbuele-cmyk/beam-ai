from agents.assistant import AssistantAgent
from agents.calculator import CalculatorAgent

class Router:

    def __init__(self):

        self.assistant = AssistantAgent()
        self.calculator = CalculatorAgent()

    def process(self, message):

        if "calcula" in message.lower():

            result = self.calculator.process(message)

            if result:
                return result

        return self.assistant.process(message)