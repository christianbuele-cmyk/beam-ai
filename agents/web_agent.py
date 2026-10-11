from tools.web_search import search_web
from agents.llm_agent import ask_llm

class WebAgent:

    def process(self, message):

        results = search_web(message)

        prompt = f"""
Resume la siguiente información encontrada en Internet:

{results}
"""

        return ask_llm(prompt)
