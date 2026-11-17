import html
import re
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

    query_lower = query.lower().strip()

    relevance_terms = [query_lower]

    if query_lower in [
        "inteligencia artificial",
        "ia",
        "artificial intelligence"
    ]:
        relevance_terms = [
            "inteligencia artificial",
            "artificial intelligence",
            " ia ",
            " ai ",
            "openai",
            "chatgpt",
            "gemini",
            "copilot",
            "nvidia"
        ]

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

        if not (limit <= published <= now):
            continue

        title = str(r.get("title", "")).lower()
        body = str(r.get("body", "")).lower()

        searchable_text = f" {title} {body} "

        if not any(
            term in searchable_text
            for term in relevance_terms
        ):
            continue

        recent_news.append((published, r))

    recent_news.sort(
        key=lambda item: item[0],
        reverse=True
    )

    unique_news = []
    seen_signatures = []

    for published, r in recent_news:

        title = str(r.get("title", "")).lower()

        title_words = set(
            re.findall(r"[a-záéíóúüñ0-9]+", title)
        )

        is_duplicate = False

        for seen_words in seen_signatures:

            if not title_words or not seen_words:
                continue

            common_words = title_words & seen_words

            similarity = len(common_words) / min(
                len(title_words),
                len(seen_words)
            )

            if similarity >= 0.55:
                is_duplicate = True
                break

        if is_duplicate:
            continue

        seen_signatures.append(title_words)
        unique_news.append((published, r))

        if len(unique_news) >= 8:
            break
    for published, r in unique_news:

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
        "espana": [
            ("RTVE", "https://www.rtve.es/api/tematicas/1420/noticias.rss")
        ],
        "internacional": [
            ("RTVE", "https://www.rtve.es/api/tematicas/1021/noticias.rss")
        ],
        "deportes": [
            ("RTVE", "https://www.rtve.es/api/tematicas/817/noticias.rss")
        ],
        "tecnologia": [
            ("Xataka", "https://www.xataka.com/index.xml"),
            ("Computer Hoy", "https://computerhoy.20minutos.es/rss")
        ],
        "economia": [
            ("Expansion", "https://e00-expansion.uecdn.es/rss/economia.xml"),
            ("Cinco Días", "https://feeds.elpais.com/mrss-s/pages/ep/site/cincodias.elpais.com/portada")
        ]
    }

    category_labels = {
        "espana": "España",
        "internacional": "Internacional",
        "deportes": "Deportes",
        "tecnologia": "Tecnología",
        "economia": "Economía"
    }

    if category == "general":
        selected_categories = [
            "espana",
            "internacional",
            "deportes",
            "tecnologia",
            "economia"
        ]
    elif category in feeds:
        selected_categories = [category]
    else:
        selected_categories = ["espana"]

    results = []

    for category_key in selected_categories:

        section = category_labels.get(
            category_key,
            category_key.capitalize()
        )

        for source_name, rss_url in feeds[category_key]:

            try:
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

                    raw_description = (
                        item.findtext("description") or ""
                    ).strip()

                    description = html.unescape(raw_description)
                    description = re.sub(
                        r"<[^>]+>",
                        " ",
                        description
                    )
                    description = re.sub(
                        r"\s+",
                        " ",
                        description
                    ).strip()

                    if len(description) > 600:
                        description = description[:600].rsplit(
                            " ",
                            1
                        )[0] + "..."
                    pub_date = (
                        item.findtext("pubDate") or ""
                    ).strip()
                    link = (item.findtext("link") or "").strip()

                    results.append(
                        f"""
Categoria: {section}
Fecha: {pub_date}
Fuente: {source_name}
Titulo: {title}
Resumen: {description}
URL: {link}
"""
                    )

            except Exception as error:
                print(
                    f"RSS ERROR [{source_name}] "
                    f"{category_key}: {error}"
                )

    return "\n".join(results)