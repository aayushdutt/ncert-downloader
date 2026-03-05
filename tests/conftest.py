import io
import zipfile

import pytest
from pypdf import PdfWriter


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_data():
    return {
        "10": {
            "Mathematics": [
                {"text": "Mathematics", "code": "iemh1", "chapters": "1-15"},
                {"text": "Mathematics Exemplar", "code": "iemh2", "chapters": "1-14"},
                {"text": "No Code Book", "code": "", "chapters": ""},  # must be skipped
            ],
            "Science": [
                {"text": "Science", "code": "iesc1", "chapters": "1-16"},
            ],
        },
        "11": {
            "Mathematics": [
                {"text": "Mathematics Part I", "code": "kemh1", "chapters": "1-9"},
            ],
            "Physics": [
                {"text": "Physics Part I", "code": "leph1", "chapters": "1-8"},
            ],
        },
    }


# ---------------------------------------------------------------------------
# PDF / zip helpers
# ---------------------------------------------------------------------------

def make_pdf_bytes():
    """Minimal valid single-page PDF."""
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_zip(pdf_names: list[str]) -> bytes:
    """In-memory zip containing blank PDFs with the given names."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name in pdf_names:
            z.writestr(name, make_pdf_bytes())
    return buf.getvalue()


@pytest.fixture
def sample_zip(tmp_path):
    """Zip mimicking NCERT structure: two chapters + one prelim file.
    Alphabetically: iemh101.pdf < iemh102.pdf < iemh1ps.pdf (prelim last).
    After merge the prelim should appear first."""
    zip_path = tmp_path / "Mathematics.zip"
    zip_path.write_bytes(make_zip(["iemh101.pdf", "iemh102.pdf", "iemh1ps.pdf"]))
    return zip_path
