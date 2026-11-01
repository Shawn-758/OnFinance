from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import pytesseract
from PIL import Image

from app.config import get_settings
from app.extractors.field_extractor import extract_fields


def _configure_tesseract() -> None:
    settings = get_settings()
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        return

    windows_default = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if windows_default.exists():
        pytesseract.pytesseract.tesseract_cmd = str(windows_default)


def blur_score(image_path: str | Path) -> float:
    """Higher Laplacian variance means a sharper image."""
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")
    return float(cv2.Laplacian(image, cv2.CV_64F).var())


def extract_image(image_path: str | Path) -> dict[str, Any]:
    _configure_tesseract()
    settings = get_settings()
    path = Path(image_path)
    score = blur_score(path)
    quality_flag = "low_quality" if score < settings.blur_threshold else "ok"

    image = Image.open(path)
    text = pytesseract.image_to_string(image) or ""
    if not text.strip():
        quality_flag = "unreadable"

    fields = extract_fields(text, filename=path.name)
    return {
        "filename": path.name,
        "text": text.strip(),
        "blur_score": round(score, 2),
        "quality_flag": quality_flag,
        "fields": fields,
        "document_type": fields["document_type"],
    }
