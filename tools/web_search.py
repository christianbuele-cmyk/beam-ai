from ddgs import DDGS
import requests
from lxml import etree

def search_web(query):

    results = []

    with DDGS() as ddgs:

        search_results = list(
            ddgs.text(query, max_results=5)
        )

    for r in search_results:

        results.append(
            f"""
Titulo: {r['title']}
Resumen: {r['body']}
"""
        )

    return "\n".join(results)

def search_news(query="España"):

    from datetime import datetime, timezone, timedelta

    results = []

    with DDGS() as ddgs:
        news_results = list(
            ddgs.news(
                query,
                region="es-es",
                max_results=30
            )
        )

    now = datetime.now(timezone.utc)
    limit = now - timedelta(hours=48)

    recent_news = []

    for r in news_results:
        raw_date = str(r.get("date", "")).strip()

        try:
            published = datetime.fromisoformat(
                raw_date.replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            continue

        if published >= limit and published <= now:
            recent_news.append((published, r))

    recent_news.sort(
        key=lambda item: item[0],
        reverse=True
    )

    for published, r in recent_news:

        results.append(
            f"""
Fecha: {published.isoformat()}
Fuente: {r.get('source', '')}
Titulo: {r.get('title', '')}
Resumen: {r.get('body', '')}
URL: {r.get('url', '')}
"""
        )

    return "\n".join(results)



def search_news_rss(category="general"):

    feeds = {
        "espana": "https://www.rtve.es/api/tematicas/1420/noticias.rss",
        "internacional": "https://www.rtve.es/api/tematicas/1021/noticias.rss",
        "deportes": "https://www.rtve.es/api/tematicas/817/noticias.rss"
    }

    if category == "general":
        selected_feeds = [
            ("España", feeds["espana"]),
            ("Internacional", feeds["internacional"])
        ]

    elif category == "internacional":
        selected_feeds = [
            ("Internacional", feeds["internacional"])
        ]

    elif category == "deportes":
        selected_feeds = [
            ("Deportes", feeds["deportes"])
        ]

    else:
        selected_feeds = [
            ("España", feeds["espana"])
        ]

    results = []

    for section, rss_url in selected_feeds:

        response = requests.get(
            rss_url,
            timeout=10,
            headers={
                "User-Agent": "BRLOX-AI/1.0"
            }
        )

        response.raise_for_status()

        root = etree.fromstring(response.content)

        items = root.xpath("//item")[:5]

        for item in items:

            title = (item.findtext("title") or "").strip()
            description = (item.findtext("description") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            link = (item.findtext("link") or "").strip()

            results.append(
                f"""
Categoria: {section}
Fecha: {pub_date}
Fuente: RTVE
Titulo: {title}
Resumen: {description}
URL: {link}
"""
            )

    return "\n".join(results)