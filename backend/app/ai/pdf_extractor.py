import io

from pypdf import PdfReader


def extract_text(pdf_bytes: bytes) -> str:
    """Plain-text extraction from a PDF's pages, concatenated with newlines.

    Uses pypdf (pure-Python, no system dependencies) rather than pdfplumber --
    resumes are simple single/double-column text documents where pypdf's
    per-page extraction is adequate, and it's a lighter dependency for the
    1GB deploy VMs. If extraction quality turns out poor for some resume
    templates, swapping to pdfplumber only touches this one function.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()
