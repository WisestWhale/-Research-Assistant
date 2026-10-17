"""Small helpers that can be tested without starting Streamlit."""

from dataclasses import dataclass
import re
from urllib.parse import quote, urlparse


@dataclass(frozen=True)
class Source:
    title: str
    url: str


class WebSearch:
    """Collect sources and reuse repeated searches during one question."""

    def __init__(self, client, max_results=3):
        if not 1 <= max_results <= 5:
            raise ValueError("Choose between 1 and 5 search results.")
        self.client = client
        self.max_results = max_results
        self.sources = []
        self._cache = {}

    def search(self, query):
        query = query.strip()
        if not query:
            return "Please provide a search query."
        if query in self._cache:
            return self._cache[query]

        # Let the caller display an error; failed requests are not cached.
        response = self.client.search(query=query, max_results=self.max_results)
        parts = []
        known_urls = {source.url for source in self.sources}
        for result in response.get("results", []):
            url = result.get("url", "")
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            title = result.get("title") or url
            if url not in known_urls:
                self.sources.append(Source(title=title, url=url))
                known_urls.add(url)
            parts.append(f"Source: {url}\n{result.get('content', '')}")

        output = "\n\n".join(parts) or "No results found."
        self._cache[query] = output
        return output


class ChatExport:
    """Keep the downloaded transcript independent of the UI."""

    @staticmethod
    def to_text(messages):
        sections = []
        for message in messages:
            text = f"{message['role'].capitalize()}: {message['content']}"
            sources = message.get("sources", [])
            if sources:
                text += "\n\nSources:\n" + "\n".join(
                    f"- {source['title']}: {source['url']}" for source in sources
                )
            sections.append(text)
        return "\n\n".join(sections)

    @staticmethod
    def to_markdown(messages):
        """Preserve answer formatting and include clickable sources per message."""
        sections = []
        for message in messages:
            text = f"## {message['role'].capitalize()}\n\n{message['content']}"
            sources = message.get("sources", [])
            if sources:
                text += "\n\n### Sources consulted\n\n"
                links = []
                for source in sources:
                    title = " ".join(source['title'].split())
                    title = re.sub(r"([\\`*_{}\[\]<>])", r"\\\1", title)
                    url = quote(source['url'], safe=":/?#[]@!$&'()*+,;=%")
                    links.append(f"- [{title}](<{url}>)")
                text += "\n".join(links)
            sections.append(text)
        return "\n\n---\n\n".join(sections)
