import fitz  # this is PyMuPDF


def extract_pdf_pages(file_bytes):
    """Read a PDF and return a list of (page_number, text)."""
    pages = []
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for i, page in enumerate(doc, start=1):
        pages.append((i, page.get_text()))
    return pages


def extract_text_file(file_bytes):
    """Read a plain .txt file as a single page."""
    return [(1, file_bytes.decode("utf-8", errors="ignore"))]
