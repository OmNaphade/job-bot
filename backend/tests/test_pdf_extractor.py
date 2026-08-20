import io

from reportlab.pdfgen import canvas

from app.ai.pdf_extractor import extract_text


def _make_pdf(*lines: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    y = 800
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 20
    pdf.save()
    return buffer.getvalue()


def test_extract_text_returns_the_pdfs_text():
    pdf_bytes = _make_pdf("Jane Doe", "Senior Backend Engineer", "Skills: Python, Postgres, AWS")

    text = extract_text(pdf_bytes)

    assert "Jane Doe" in text
    assert "Senior Backend Engineer" in text
    assert "Python, Postgres, AWS" in text


def test_extract_text_joins_multiple_pages():
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 800, "Page one content")
    pdf.showPage()
    pdf.drawString(72, 800, "Page two content")
    pdf.save()

    text = extract_text(buffer.getvalue())

    assert "Page one content" in text
    assert "Page two content" in text


def test_extract_text_returns_empty_string_for_a_blank_pdf():
    buffer = io.BytesIO()
    canvas.Canvas(buffer).save()

    assert extract_text(buffer.getvalue()) == ""
