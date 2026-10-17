import unittest

from research_tools import ChatExport, WebSearch


class FakeSearchClient:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return {"results": self.results}


class ResearchToolsTests(unittest.TestCase):
    def test_repeated_query_uses_one_request_and_sources_are_unique(self):
        client = FakeSearchClient([
            {"title": "Example", "url": "https://example.com", "content": "A fact"},
            {"title": "Duplicate", "url": "https://example.com", "content": "More"},
        ])
        search = WebSearch(client, max_results=4)
        first = search.search("  batteries  ")
        self.assertEqual(first, search.search("batteries"))
        self.assertEqual(client.calls, [{"query": "batteries", "max_results": 4}])
        self.assertEqual(len(search.sources), 1)
        self.assertIn("A fact", first)

    def test_blank_query_does_not_call_service(self):
        client = FakeSearchClient([])
        self.assertEqual(WebSearch(client).search("  "), "Please provide a search query.")
        self.assertEqual(client.calls, [])

    def test_invalid_links_are_excluded(self):
        client = FakeSearchClient([
            {"url": "javascript:alert(1)", "content": "invalid"},
            {"url": "https://example.com", "content": "valid"},
        ])
        search = WebSearch(client)
        self.assertNotIn("invalid", search.search("topic"))
        self.assertEqual(search.sources[0].title, "https://example.com")

    def test_failed_request_can_be_retried(self):
        class FlakyClient:
            calls = 0

            def search(self, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise ConnectionError("offline")
                return {"results": []}

        search = WebSearch(FlakyClient())
        with self.assertRaises(ConnectionError):
            search.search("topic")
        self.assertEqual(search.search("topic"), "No results found.")

    def test_export_includes_speakers_and_sources(self):
        messages = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Answer", "sources": [
                {"title": "Example", "url": "https://example.com"}
            ]},
        ]
        self.assertEqual(ChatExport.to_text(messages),
                         "User: Question\n\nAssistant: Answer\n\nSources:\n- Example: https://example.com")
        self.assertEqual(ChatExport.to_text([]), "")


    def test_markdown_export_preserves_answer_and_escapes_source_labels(self):
        messages = [
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "**Answer**\n\n- A finding", "sources": [
                {"title": "Study [v2]\nnotes", "url": "https://example.com/a b?q=(test)"}
            ]},
        ]
        output = ChatExport.to_markdown(messages)
        self.assertIn("## User\n\nQuestion\n\n---\n\n## Assistant", output)
        self.assertIn("**Answer**\n\n- A finding", output)
        self.assertIn(r"- [Study \[v2\] notes](<https://example.com/a%20b?q=(test)>)", output)
        self.assertEqual(ChatExport.to_markdown([]), "")
        self.assertNotIn("Sources consulted", ChatExport.to_markdown(messages[:1]))


if __name__ == "__main__":
    unittest.main()
