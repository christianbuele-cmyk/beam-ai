from tools.web_search import search_web, search_news_rss
from agents.llm_agent import ask_llm


class WebAgent:

    def process(self, message):

        message_lower = message.lower()

        if "noticias" in message_lower:

            if any(word in message_lower for word in [
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
                results = search_news_rss("espana")

            else:
                results = search_news_rss("general")

        else:
            results = search_web(message)

        prompt = f"""
Resume la siguiente información encontrada en Internet:

{results}
"""

        return ask_llm(prompt)
