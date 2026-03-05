"""High-signal tests for iter_books, download_book, and merge_book.
No real network calls — requests.get is always mocked."""

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pypdf import PdfReader

from main import download_book, iter_books, merge_book
from tests.conftest import make_pdf_bytes, make_zip


# ---------------------------------------------------------------------------
# iter_books
# ---------------------------------------------------------------------------

class TestIterBooks:
    def test_returns_all_books_with_codes(self, sample_data):
        books = list(iter_books(sample_data))
        # 2 from class-10 maths (no-code book excluded) + 1 science + 1 maths-11 + 1 physics-11
        assert len(books) == 5

    def test_class_filter(self, sample_data):
        books = list(iter_books(sample_data, cls_filter="10"))
        assert len(books) == 3
        assert all(cls == "10" for cls, _, _ in books)

    def test_subject_filter_cross_class(self, sample_data):
        books = list(iter_books(sample_data, subj_filter="Mathematics"))
        assert len(books) == 3
        assert all(subj == "Mathematics" for _, subj, _ in books)

    def test_class_and_subject_filter(self, sample_data):
        books = list(iter_books(sample_data, cls_filter="10", subj_filter="Science"))
        assert len(books) == 1
        assert books[0][2]["text"] == "Science"

    def test_skips_books_without_code(self, sample_data):
        books = list(iter_books(sample_data, cls_filter="10", subj_filter="Mathematics"))
        assert all(b["code"] for _, _, b in books)
        assert len(books) == 2  # "No Code Book" excluded

    def test_results_sorted_by_class(self, sample_data):
        books = list(iter_books(sample_data))
        classes = [cls for cls, _, _ in books]
        assert classes == sorted(classes, key=int)

    def test_no_match_returns_empty(self, sample_data):
        assert list(iter_books(sample_data, cls_filter="99")) == []

    def test_subject_filter_case_insensitive(self, sample_data):
        lower = list(iter_books(sample_data, subj_filter="mathematics"))
        upper = list(iter_books(sample_data, subj_filter="Mathematics"))
        assert lower == upper


# ---------------------------------------------------------------------------
# download_book
# ---------------------------------------------------------------------------

class TestDownloadBook:
    def _book(self):
        return {"text": "Mathematics", "code": "iemh1"}

    def test_skips_when_zip_already_exists(self, tmp_path):
        dest = tmp_path / "Class 10" / "Mathematics" / "Mathematics.zip"
        dest.parent.mkdir(parents=True)
        dest.touch()
        assert download_book("10", "Mathematics", self._book(), tmp_path) == "skipped"

    def test_creates_correct_directory_structure(self, tmp_path):
        with patch("main.requests.get") as mock_get:
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.iter_content = lambda chunk_size: [b"zip data"]
            download_book("10", "Mathematics", self._book(), tmp_path)
        assert (tmp_path / "Class 10" / "Mathematics" / "Mathematics.zip").exists()

    def test_uses_correct_url(self, tmp_path):
        with patch("main.requests.get") as mock_get:
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.iter_content = lambda chunk_size: [b"zip data"]
            download_book("10", "Mathematics", self._book(), tmp_path)
        url = mock_get.call_args[0][0]
        assert url == "https://ncert.nic.in/textbook/pdf/iemh1dd.zip"

    def test_returns_ok_on_success(self, tmp_path):
        with patch("main.requests.get") as mock_get:
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.iter_content = lambda chunk_size: [b"zip data"]
            assert download_book("10", "Mathematics", self._book(), tmp_path) == "ok"

    def test_returns_error_on_network_failure(self, tmp_path):
        with patch("main.requests.get", side_effect=Exception("timeout")):
            result = download_book("10", "Mathematics", self._book(), tmp_path)
        assert result.startswith("error:")

    def test_returns_error_on_http_error(self, tmp_path):
        with patch("main.requests.get") as mock_get:
            mock_get.return_value.raise_for_status.side_effect = Exception("404 Not Found")
            result = download_book("10", "Mathematics", self._book(), tmp_path)
        assert result.startswith("error:")

    def test_keeps_tmp_file_for_resume_on_error(self, tmp_path):
        with patch("main.requests.get") as mock_get:
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.iter_content.side_effect = Exception("connection dropped")
            download_book("10", "Mathematics", self._book(), tmp_path)
        # .tmp is kept intentionally so the next run can resume
        assert any(tmp_path.rglob("*.zip.tmp"))
        assert not any(tmp_path.rglob("*.zip"))  # but no completed zip

    def test_resumes_from_partial_tmp(self, tmp_path):
        book = self._book()
        tmp = tmp_path / "Class 10" / "Mathematics" / "Mathematics.zip.tmp"
        tmp.parent.mkdir(parents=True)
        tmp.write_bytes(b"existing bytes")  # simulate partial download

        with patch("main.requests.get") as mock_get:
            mock_get.return_value.status_code = 206
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.iter_content = lambda chunk_size: [b" more bytes"]
            download_book("10", "Mathematics", book, tmp_path)

        sent_headers = mock_get.call_args[1]["headers"]
        assert sent_headers == {"Range": "bytes=14-"}  # 14 = len("existing bytes")

    def test_restarts_if_server_ignores_range(self, tmp_path):
        book = self._book()
        tmp = tmp_path / "Class 10" / "Mathematics" / "Mathematics.zip.tmp"
        tmp.parent.mkdir(parents=True)
        tmp.write_bytes(b"stale partial data")

        with patch("main.requests.get") as mock_get:
            mock_get.return_value.status_code = 200  # server ignored Range
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.iter_content = lambda chunk_size: [b"fresh full content"]
            download_book("10", "Mathematics", book, tmp_path)

        dest = tmp_path / "Class 10" / "Mathematics" / "Mathematics.zip"
        assert dest.read_bytes() == b"fresh full content"  # not appended to stale


# ---------------------------------------------------------------------------
# merge_book
# ---------------------------------------------------------------------------

class TestMergeBook:
    def test_skips_when_pdf_already_exists(self, tmp_path, sample_zip):
        sample_zip.with_suffix(".pdf").touch()
        assert merge_book(sample_zip, keep_zip=True) == "skipped"

    def test_returns_ok_on_success(self, tmp_path, sample_zip):
        assert merge_book(sample_zip, keep_zip=True) == "ok"

    def test_produces_merged_pdf(self, tmp_path, sample_zip):
        merge_book(sample_zip, keep_zip=True)
        out_pdf = sample_zip.with_suffix(".pdf")
        assert out_pdf.exists()
        assert out_pdf.stat().st_size > 0

    def test_merged_pdf_has_correct_page_count(self, tmp_path, sample_zip):
        merge_book(sample_zip, keep_zip=True)
        reader = PdfReader(sample_zip.with_suffix(".pdf"))
        assert len(reader.pages) == 3  # 2 chapters + 1 prelim

    def test_prelim_ordering(self, tmp_path):
        """iemh1ps.pdf sorts last alphabetically but should end up first in the merge."""
        # We verify by creating distinct-page-count PDFs: prelim=2 pages, chapters=1 each.
        import io
        from pypdf import PdfWriter as W

        def make_pdf(pages):
            w = W()
            for _ in range(pages):
                w.add_blank_page(width=72, height=72)
            buf = io.BytesIO()
            w.write(buf)
            return buf.getvalue()

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("iemh101.pdf", make_pdf(1))   # chapter 1
            z.writestr("iemh102.pdf", make_pdf(1))   # chapter 2
            z.writestr("iemh1ps.pdf", make_pdf(2))   # prelim — 2 pages, sorts last

        zip_path = tmp_path / "book.zip"
        zip_path.write_bytes(buf.getvalue())
        merge_book(zip_path, keep_zip=True)

        reader = PdfReader(zip_path.with_suffix(".pdf"))
        # Merged order should be: prelim (2 pages) + ch1 (1) + ch2 (1) = 4 pages total
        assert len(reader.pages) == 4

    def test_deletes_zip_by_default(self, tmp_path, sample_zip):
        merge_book(sample_zip, keep_zip=False)
        assert not sample_zip.exists()

    def test_keeps_zip_when_requested(self, tmp_path, sample_zip):
        merge_book(sample_zip, keep_zip=True)
        assert sample_zip.exists()

    def test_temp_dir_always_cleaned_up(self, tmp_path, sample_zip):
        merge_book(sample_zip, keep_zip=True)
        assert not any(tmp_path.glob("_tmp_*"))

    def test_temp_dir_cleaned_up_on_error(self, tmp_path):
        zip_path = tmp_path / "broken.zip"
        zip_path.write_bytes(b"not a valid zip")
        merge_book(zip_path, keep_zip=True)
        assert not any(tmp_path.glob("_tmp_*"))

    def test_returns_error_for_empty_zip(self, tmp_path):
        zip_path = tmp_path / "empty.zip"
        zip_path.write_bytes(make_zip([]))
        result = merge_book(zip_path, keep_zip=True)
        assert result.startswith("error:")

    def test_returns_error_for_corrupt_zip(self, tmp_path):
        zip_path = tmp_path / "corrupt.zip"
        zip_path.write_bytes(b"garbage")
        result = merge_book(zip_path, keep_zip=True)
        assert result.startswith("error:")
