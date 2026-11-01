from __future__ import annotations

import re
from typing import Any


AADHAAR_DIGITS_RE = re.compile(r"^[1-9][0-9]{11}$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]$")
DATE_RE = re.compile(r"^(0?[1-9]|[12][0-9]|3[01])[-/](0?[1-9]|1[0-2])[-/][0-9]{4}$")


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _verhoeff_valid(number: str) -> bool:
    multiplication = (
        (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
        (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
        (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
        (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
        (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
        (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
        (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
        (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
        (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
        (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
    )
    permutation = (
        (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
        (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
        (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
        (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
        (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
        (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
        (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
        (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
    )
    inverse = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)

    checksum = 0
    for position, digit in enumerate(reversed(number)):
        checksum = multiplication[checksum][permutation[position % 8][int(digit)]]
    return checksum == inverse[0]


def _result(document_type: str, errors: list[str], warnings: list[str]) -> dict[str, Any]:
    return {
        "document_type": document_type,
        "valid": not errors,
        "requires_due_diligence": bool(errors or warnings),
        "errors": errors,
        "warnings": warnings,
    }


def validate_aadhaar(value: str | None) -> dict[str, Any]:
    digits = _digits(value)
    errors: list[str] = []
    if not AADHAAR_DIGITS_RE.fullmatch(digits):
        errors.append("Aadhaar must contain 12 digits and start with 1-9")
    elif not _verhoeff_valid(digits):
        errors.append("Aadhaar failed the Verhoeff checksum")
    return _result("aadhaar", errors, [])


def validate_pan(value: str | None) -> dict[str, Any]:
    errors = [] if value and PAN_RE.fullmatch(value.upper()) else [
        "PAN must match five letters, four digits, and one letter"
    ]
    return _result("pan", errors, [])


def validate_gst(fields: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    gstin = str(fields.get("gstin") or "").upper()
    if not GSTIN_RE.fullmatch(gstin):
        errors.append("GSTIN must be a 15-character alphanumeric GSTIN")
    pan = fields.get("pan")
    if pan and gstin and gstin[2:12] != str(pan).upper():
        errors.append("GSTIN characters 3-12 do not match the client's PAN")
    for key, label in (
        ("name", "GST legal name"),
        ("state", "GST state"),
        ("gst_type", "GST registration type"),
        ("registration_date", "GST registration date"),
    ):
        if not fields.get(key):
            errors.append(f"{label} is required")
    if fields.get("registration_date") and not DATE_RE.fullmatch(
        str(fields["registration_date"])
    ):
        errors.append("GST registration date must use DD/MM/YYYY")
    return _result("gst", errors, [])


def validate_electricity_bill(fields: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    required = (
        ("name", "customer name"),
        ("billing_address", "billing address"),
        ("consumer_number", "consumer number"),
        ("consumption", "consumption"),
        ("amount", "bill amount"),
    )
    for key, label in required:
        if fields.get(key) in (None, ""):
            errors.append(f"{label} is required")
    return _result("electricity_bill", errors, [])


def validate_fields(fields: dict[str, Any]) -> dict[str, Any]:
    document_type = fields.get("document_type", "unknown")
    if document_type == "aadhaar":
        return validate_aadhaar(fields.get("aadhaar"))
    if document_type == "pan":
        return validate_pan(fields.get("pan"))
    if document_type == "gst":
        return validate_gst(fields)
    if document_type == "electricity_bill":
        return validate_electricity_bill(fields)
    return _result(document_type, [], ["Document type could not be identified"])
