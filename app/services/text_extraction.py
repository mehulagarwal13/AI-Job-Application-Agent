"""
Resume text extraction.

Improvements over the naive version:
- Column-aware PDF extraction (two-column resumes no longer interleave)
- OCR fallback for scanned/image-based PDFs (optional deps, graceful message if absent)
- DOCX extraction includes tables, in true document order
- Text cleaning (unicode normalization, de-hyphenation, bullet/whitespace normalization)
  before anything is persisted or sent to the LLM
"""

import re
import unicodedata
from pathlib import Path

import pdfplumber
import docx
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P


class ExtractionError(Exception):
    pass


MIN_TEXT_LENGTH = 50  # below this we assume scanned/corrupt content


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

_BULLETS = re.compile(r"[•▪◦●‣·]")


def clean_text(text: str) -> str:
    """
    Normalizes extracted text before it is persisted / sent to the LLM:
    - NFKC unicode normalization (ligatures, fullwidth chars -> plain ASCII where possible)
    - removes soft hyphens, joins words hyphenated across line breaks ("develop-\\nment")
    - normalizes bullet glyphs to "- "
    - collapses runs of spaces/tabs and excessive blank lines
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("­", "")                      # soft hyphen
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)           # de-hyphenate line breaks
    text = _BULLETS.sub("- ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# PDF extraction (column-aware)
# ---------------------------------------------------------------------------

def _find_column_gutter(page, words) -> float | None:
    """
    Detects a vertical gutter splitting the page into two columns.

    Scans candidate x-positions across the middle band of the page; a position
    is "clear" if (almost) no words cross it and both sides hold a meaningful
    share of the words. Returns the midpoint of the widest clear band, or None
    for a single-column page.
    """
    if len(words) < 10:
        return None

    total = len(words)
    step = 4
    clear_positions: list[int] = []

    for gx in range(int(page.width * 0.30), int(page.width * 0.70), step):
        crossing = sum(1 for w in words if w["x0"] < gx < w["x1"])
        if crossing > max(2, total * 0.02):
            continue
        left = sum(1 for w in words if w["x1"] <= gx)
        right = sum(1 for w in words if w["x0"] >= gx)
        if left >= total * 0.20 and right >= total * 0.20:
            clear_positions.append(gx)

    if not clear_positions:
        return None

    # Group consecutive clear positions into bands; keep the widest.
    bands: list[list[int]] = [[clear_positions[0]]]
    for gx in clear_positions[1:]:
        if gx - bands[-1][-1] <= step:
            bands[-1].append(gx)
        else:
            bands.append([gx])
    widest = max(bands, key=len)

    # Require a real gutter (>= ~12pt wide), not a coincidental sliver.
    if (widest[-1] - widest[0]) + step < 12:
        return None
    return (widest[0] + widest[-1]) / 2


def _extract_page_text(page) -> str:
    words = page.extract_words()
    if not words:
        return ""

    gutter = _find_column_gutter(page, words)
    if gutter is None:
        return page.extract_text(x_tolerance=1.5) or ""

    # Read the full left column first, then the right — correct reading order.
    left = page.crop((0, 0, gutter, page.height)).extract_text(x_tolerance=1.5) or ""
    right = page.crop((gutter, 0, page.width, page.height)).extract_text(x_tolerance=1.5) or ""
    return f"{left}\n{right}".strip()


def extract_text_from_pdf(path: str) -> str:
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = _extract_page_text(page)
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


# ---------------------------------------------------------------------------
# OCR fallback (scanned/image PDFs)
# ---------------------------------------------------------------------------

def _ocr_pdf(path: str) -> str:
    """
    Renders each PDF page to an image and OCRs it.
    Requires optional dependencies: pypdfium2, pytesseract, and the Tesseract
    engine installed on the machine. Fails with an actionable message otherwise.
    """
    try:
        import pypdfium2 as pdfium
        import pytesseract
    except ImportError:
        raise ExtractionError(
            "PDF has no text layer (likely a scanned image). OCR fallback is not "
            "installed — run: pip install pypdfium2 pytesseract, and install the "
            "Tesseract OCR engine (https://github.com/tesseract-ocr/tesseract)."
        )

    try:
        pdf = pdfium.PdfDocument(path)
        parts = []
        for page in pdf:
            bitmap = page.render(scale=300 / 72)  # ~300 DPI for OCR quality
            parts.append(pytesseract.image_to_string(bitmap.to_pil()))
        return "\n".join(parts)
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(f"OCR fallback failed: {e}")


# ---------------------------------------------------------------------------
# DOCX extraction (paragraphs + tables, in document order)
# ---------------------------------------------------------------------------

def _iter_block_items(document):
    """Yields Paragraph and Table objects in the order they appear in the body."""
    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def extract_text_from_docx(path: str) -> str:
    document = docx.Document(path)
    parts: list[str] = []

    for block in _iter_block_items(document):
        if isinstance(block, Paragraph):
            if block.text.strip():
                parts.append(block.text.strip())
        else:  # Table — resumes commonly keep skills/contact info here
            for row in block.rows:
                cells: list[str] = []
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    # Merged cells repeat the same object; skip consecutive dupes
                    if cell_text and (not cells or cells[-1] != cell_text):
                        cells.append(cell_text)
                if cells:
                    parts.append(" | ".join(cells))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def extract_text(stored_path: str) -> str:
    """
    Dispatches to the right extractor based on file extension, with OCR fallback
    for text-less PDFs. Cleans the text and validates it is non-trivial.
    Raises ExtractionError on any failure.
    """
    ext = Path(stored_path).suffix.lower()

    try:
        if ext == ".pdf":
            text = extract_text_from_pdf(stored_path)
            if len(text.strip()) < MIN_TEXT_LENGTH:
                text = _ocr_pdf(stored_path)  # scanned/image PDF
        elif ext == ".docx":
            text = extract_text_from_docx(stored_path)
        else:
            raise ExtractionError(f"Unsupported extension for extraction: {ext}")
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(f"Failed to extract text: {e}")

    text = clean_text(text)

    if len(text) < MIN_TEXT_LENGTH:
        raise ExtractionError(
            "Extracted text is too short — file may be a scanned image, corrupt, or empty."
        )

    return text
