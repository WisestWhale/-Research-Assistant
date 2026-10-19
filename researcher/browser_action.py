from dataclasses import dataclass
from urllib.parse import urlsplit
import webbrowser


@dataclass
class BrowserAction:
    url: str
    reason: str
    status: str = "pending"

    @classmethod
    def from_sources(cls, url, reason, sources):
        if not isinstance(url, str) or not isinstance(reason, str) or not reason.strip():
            raise ValueError("Provide a source URL and a reason.")
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or any(character.isspace() or ord(character) < 32 for character in url)):
            raise ValueError("Only HTTP or HTTPS pages without embedded credentials are allowed.")
        if url not in {source.url for source in sources}:
            raise ValueError("Choose a URL returned by this question's web search.")
        return cls(url, reason.strip()[:500])

    def open(self, opener=None):
        if self.status != "pending":
            return
        self.status = "failed"
        try:
            if (opener or webbrowser.open_new_tab)(self.url):
                self.status = "opened"
        except Exception:
            self.status = "failed"

    def cancel(self):
        if self.status == "pending":
            self.status = "cancelled"
