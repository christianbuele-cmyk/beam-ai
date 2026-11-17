import re
from tools.web_search import search_web, search_news, search_news_rss
from agents.llm_agent import ask_llm


class WebAgent:

    def process(self, message):

        message_lower = message.lower()

        if "noticias" in message_lower:

            if "openai" in message_lower:
                results = search_news("OpenAI")

            elif "chatgpt" in message_lower:
                results = search_news("ChatGPT")

            elif "gemini" in message_lower:
                results = search_news("Gemini")

            elif "copilot" in message_lower:
                results = search_news("Microsoft Copilot")

            elif (
                "inteligencia artificial" in message_lower
                or re.search(r"\bia\b", message_lower)
            ):
                results = search_news("inteligencia artificial")

            elif any(word in message_lower for word in [
                "tecnología",
                "tecnologia",
                "tecnológica",
                "tecnologica",
                "tecnológicas",
                "tecnologicas"
            ]):
                results = search_news_rss("tecnologia")

            elif any(word in message_lower for word in [
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
            ]):
                results = search_news_rss("economia")

            elif any(word in message_lower for word in [
                "deportes",
                "deportiva",
                "deportivas",
                "deportivo",
                "deportivos",
                "fútbol",
                "futbol"
            ]):
                results = search_news_rss("deportes")
            elif any(word in message_lower for word in [
                "mundo",
                "internacional",
                "internacionales",
                "global"
            ]):
                results = search_news_rss("internacional")

            else:
                results = search_news_rss("general")

        else:
            results = search_web(message)

        prompt = f"""
Resume la siguiente información encontrada en Internet:

{results}
"""

        return ask_llm(prompt)
