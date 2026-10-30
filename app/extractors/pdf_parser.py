from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader

from app.extractors.field_extractor import extract_fields
from app.extractors.image_ocr import extract_image


def _text_from_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()


def _ocr_pdf_pages(path: Path) -> dict[str, Any]:
    """Fallback for scanned/image PDFs using PyMuPDF page rasters + Tesseract."""
    try:
        import fitz
    except ImportError:
        return {"text": "", "quality_flag": "unreadable", "blur_score": None}

    doc = fitz.open(str(path))
    texts: list[str] = []
    flags: list[str] = []
    scores: list[float] = []
    tmp_dir = path.parent / "_pdf_ocr_tmp"
    tmp_dir.mkdir(exist_ok=True)
    try:
        for index, page in enumerate(doc):
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            tmp_file = tmp_dir / f"{path.stem}_page_{index}.png"
            pix.save(str(tmp_file))
            result = extract_image(tmp_file)
            texts.append(result["text"])
            flags.append(result["quality_flag"])
            if result["blur_score"] is not None:
                scores.append(result["blur_score"])
            tmp_file.unlink(missing_ok=True)
    finally:
        doc.close()
        for leftover in tmp_dir.glob("*"):
            leftover.unlink(missing_ok=True)
        if tmp_dir.exists():
            tmp_dir.rmdir()

    quality = "unreadable" if all(flag != "ok" for flag in flags) else (
        "low_quality" if "low_quality" in flags else "ok"
    )
    return {
        "text": "\n".join(texts).strip(),
        "quality_flag": quality,
        "blur_score": round(min(scores), 2) if scores else None,
    }


def extract_pdf(pdf_path: str | Path) -> dict[str, Any]:
    path = Path(pdf_path)
    text = _text_from_pdf(path)
    quality_flag = "ok"
    score = None

    if len(text) < 40:
        ocr = _ocr_pdf_pages(path)
        if ocr["text"]:
            text = ocr["text"]
            quality_flag = ocr["quality_flag"]
            score = ocr["blur_score"]
        elif not text:
            quality_flag = "unreadable"

    fields = extract_fields(text, filename=path.name)
    return {
        "filename": path.name,
        "text": text,
        "blur_score": score,
        "quality_flag": quality_flag,
        "fields": fields,
        "document_type": fields["document_type"],
    }
