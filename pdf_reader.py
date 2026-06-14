import pdfplumber
import os


def extract_text_from_pdf(filepath):
    """
    Extract all text from a PDF file using pdfplumber.
    Handles multi-page PDFs and large documents.
    Returns extracted text as a string, or raises an exception on failure.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    extracted_pages = []

    with pdfplumber.open(filepath) as pdf:
        if len(pdf.pages) == 0:
            raise ValueError("The PDF file has no pages.")

        for i, page in enumerate(pdf.pages):
            try:
                text = page.extract_text()
                if text:
                    extracted_pages.append(f"--- Page {i + 1} ---\n{text.strip()}")
            except Exception as e:
                extracted_pages.append(f"--- Page {i + 1} --- [Could not extract text: {str(e)}]")

    if not extracted_pages:
        raise ValueError("No text could be extracted from the PDF. The file may be image-based or corrupted.")

    full_text = "\n\n".join(extracted_pages)

    # Limit to ~15000 characters to stay within Gemini's token limits for large docs
    if len(full_text) > 15000:
        full_text = full_text[:15000] + "\n\n[Document truncated for processing...]"

    return full_text
