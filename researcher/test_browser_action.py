import unittest
from unittest.mock import Mock

from browser_action import BrowserAction
from research_tools import Source


class BrowserActionTests(unittest.TestCase):
    def make_action(self):
        source = Source("Example", "https://example.com/page")
        return BrowserAction.from_sources(source.url, "Read the source", [source])

    def test_waits_for_approval_and_opens_once(self):
        action = self.make_action()
        opener = Mock(return_value=True)
        self.assertEqual(action.status, "pending")
        opener.assert_not_called()
        action.open(opener)
        action.open(opener)
        opener.assert_called_once_with("https://example.com/page")
        self.assertEqual(action.status, "opened")

    def test_cancel_prevents_opening(self):
        action = self.make_action()
        opener = Mock()
        action.cancel()
        action.open(opener)
        opener.assert_not_called()
        self.assertEqual(action.status, "cancelled")

    def test_failed_launch_does_not_retry_on_rerun(self):
        for opener in [Mock(return_value=False), Mock(side_effect=OSError("no browser"))]:
            action = self.make_action()
            action.open(opener)
            action.open(opener)
            self.assertEqual(action.status, "failed")
            self.assertEqual(opener.call_count, 1)

    def test_rejects_unknown_sources_and_non_web_targets(self):
        for url in ["file:///C:/Windows", "javascript:alert(1)", "https://user:pass@example.com", "https://example.com/\npage"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                BrowserAction.from_sources(url, "Open it", [Source("Bad", url)])
        with self.assertRaises(ValueError):
            BrowserAction.from_sources("https://other.example", "Open it", [])
        with self.assertRaises(ValueError):
            BrowserAction.from_sources("https://example.com", "  ", [])


if __name__ == "__main__":
    unittest.main()
