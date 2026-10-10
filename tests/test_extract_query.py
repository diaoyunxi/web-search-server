"""Tests for SearchRequestHandler._extract_query"""
import unittest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from web_search_server import SearchRequestHandler

class TestExtractQuery(unittest.TestCase):
    def setUp(self):
        self.handler = SearchRequestHandler.__new__(SearchRequestHandler)

    def test_extract_from_string_message(self):
        messages = [{"role": "user", "content": "Perform a web search for the query: Python best practices"}]
        result = self.handler._extract_query(messages)
        self.assertEqual(result, "Python best practices")

    def test_extract_from_plain_string(self):
        messages = [{"role": "user", "content": "hello world"}]
        result = self.handler._extract_query(messages)
        self.assertEqual(result, "hello world")

    def test_extract_from_list_content(self):
        messages = [{"role": "user", "content": [{"type": "text", "text": "Perform a web search for the query: AI trends"}]}]
        result = self.handler._extract_query(messages)
        self.assertEqual(result, "AI trends")

    def test_empty_messages(self):
        result = self.handler._extract_query([])
        self.assertEqual(result, "")

if __name__ == "__main__":
    unittest.main()
