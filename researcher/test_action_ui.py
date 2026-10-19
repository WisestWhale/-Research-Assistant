from pathlib import Path
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


class ActionUITests(unittest.TestCase):
    def test_open_requires_click_and_is_not_repeated(self):
        with patch("webbrowser.open_new_tab", return_value=True) as opener:
            app = AppTest.from_file(str(Path(__file__).with_name("action_demo.py"))).run()
            self.assertFalse(app.exception)
            opener.assert_not_called()
            app.button(key="open_demo").click().run()
            self.assertFalse(app.exception)
            opener.assert_called_once_with("https://docs.python.org/3/")
            app.run()
            self.assertEqual(opener.call_count, 1)
            self.assertEqual(app.session_state.demo_action.status, "opened")

    def test_cancel_does_not_open_browser(self):
        with patch("webbrowser.open_new_tab") as opener:
            app = AppTest.from_file(str(Path(__file__).with_name("action_demo.py"))).run()
            app.button(key="cancel_demo").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state.demo_action.status, "cancelled")
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
