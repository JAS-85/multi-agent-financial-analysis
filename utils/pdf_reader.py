import logging
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)


def read_pdf(file_path: str) -> str:
    """Extract text from a PDF file. Returns concatenated text from all pages."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF file: {file_path}")

    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                pages.append(f"--- Page {i + 1} ---\n{text}")
            else:
                logger.warning(f"Page {i + 1} of {file_path} had no extractable text")

    if not pages:
        logger.warning(f"No text extracted from {file_path}")
        return ""

    logger.info(f"Extracted {len(pages)} pages from {file_path}")
    return "\n\n".join(pages)


def read_text_file(file_path: str) -> str:
    """Read a plain text or CSV file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    return path.read_text(encoding="utf-8")


def read_document(file_path: str) -> str:
    """Read any supported document type. Routes to the appropriate reader."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return read_pdf(file_path)
    elif suffix in (".txt", ".csv"):
        return read_text_file(file_path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Supported: .pdf, .txt, .csv")
