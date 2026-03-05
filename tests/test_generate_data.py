"""Tests for generate_data.parse_script and fetch_script.
No real network calls — requests.get is always mocked."""

from unittest.mock import MagicMock, patch

import pytest

from generate_data import fetch_script, parse_script

# ---------------------------------------------------------------------------
# Minimal JS fixture that mirrors real NCERT structure
# ---------------------------------------------------------------------------

SCRIPT = """
function change1(sind) {
if (
  document.test.tclass.value == 10 &&
  document.test.tsubject.options[sind].text == "Mathematics"
) {
  document.test.tbook.options[0].text = "..Select Book Title..";
  document.test.tbook.options[1].text = "Mathematics";
  document.test.tbook.options[1].value = "textbook.php?iemh1=0-15";
  document.test.tbook.options[2].text = "Ganit";
  document.test.tbook.options[2].value = "textbook.php?ihmh1=0-15";
} else if (
  document.test.tclass.value == 10 &&
  document.test.tsubject.options[sind].text == "Science"
) {
  document.test.tbook.options[0].text = "..Select Book Title..";
  document.test.tbook.options[1].text = "Science";
  document.test.tbook.options[1].value = "textbook.php?iesc1=1-16";
} else if (
  document.test.tclass.value == 11 &&
  document.test.tsubject.options[sind].text == "Physics"
) {
  document.test.tbook.options[0].text = "..Select Book Title..";
  document.test.tbook.options[1].text = "Physics Part I";
  document.test.tbook.options[1].value = "textbook.php?leph1=1-8";
  document.test.tbook.options[2].text = "Physics Part II";
  document.test.tbook.options[2].value = "textbook.php?leph2=9-15";
} else {
  document.test.tbook.options[0].text = "..Select Book Title..";
}
}
"""


# ---------------------------------------------------------------------------
# parse_script
# ---------------------------------------------------------------------------

class TestParseScript:
    def _parse(self):
        return parse_script(SCRIPT)

    def test_extracts_classes(self):
        data = self._parse()
        assert set(data.keys()) == {"10", "11"}

    def test_extracts_subjects(self):
        data = self._parse()
        assert set(data["10"].keys()) == {"Mathematics", "Science"}
        assert set(data["11"].keys()) == {"Physics"}

    def test_extracts_book_fields(self):
        book = self._parse()["10"]["Mathematics"][0]
        assert book == {"text": "Mathematics", "code": "iemh1", "chapters": "0-15"}

    def test_multiple_books_per_subject(self):
        books = self._parse()["10"]["Mathematics"]
        assert len(books) == 2
        assert books[1] == {"text": "Ganit", "code": "ihmh1", "chapters": "0-15"}

    def test_skips_select_book_placeholder(self):
        # "..Select Book Title.." must never appear in results
        for cls in self._parse().values():
            for books in cls.values():
                assert all(b["text"] != "..Select Book Title.." for b in books)

    def test_skips_select_subject_placeholder(self):
        # The trailing else block has no class/subject match — shouldn't produce a key
        data = self._parse()
        assert "..Select Subject.." not in str(data)

    def test_chapter_range_preserved(self):
        books = self._parse()["11"]["Physics"]
        assert books[0]["chapters"] == "1-8"
        assert books[1]["chapters"] == "9-15"

    def test_empty_script_returns_empty_dict(self):
        assert parse_script("") == {}

    def test_subject_with_no_books_still_present(self):
        # A subject block with only a placeholder book should yield an empty list,
        # not be silently dropped — the key exists.
        script = """
        if (document.test.tclass.value == 5 &&
            document.test.tsubject.options[sind].text == "Art") {
          document.test.tbook.options[0].text = "..Select Book Title..";
        }
        """
        data = parse_script(script)
        assert data == {"5": {"Art": []}}


# ---------------------------------------------------------------------------
# fetch_script
# ---------------------------------------------------------------------------

class TestFetchScript:
    def _mock_response(self, html):
        mock = MagicMock()
        mock.text = html
        mock.raise_for_status = lambda: None
        return mock

    def test_returns_matching_script_block(self):
        html = (
            "<html><script>unrelated()</script>"
            "<script>if(document.test.tclass.value==1){}</script></html>"
        )
        with patch("generate_data.requests.get", return_value=self._mock_response(html)):
            result = fetch_script("http://example.com")
        assert "tclass.value" in result

    def test_raises_when_no_matching_block(self):
        html = "<html><script>console.log('hi')</script></html>"
        with patch("generate_data.requests.get", return_value=self._mock_response(html)):
            with pytest.raises(ValueError, match="Could not find"):
                fetch_script("http://example.com")

    def test_picks_correct_block_among_multiple(self):
        html = (
            "<script>var x = 1;</script>"
            "<script>tclass.value == 10;</script>"
            "<script>analytics();</script>"
        )
        with patch("generate_data.requests.get", return_value=self._mock_response(html)):
            result = fetch_script("http://example.com")
        assert "tclass.value" in result
        assert "analytics" not in result
