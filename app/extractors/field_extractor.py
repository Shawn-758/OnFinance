from __future__ import annotations

import re
from typing import Any


PAN_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b", re.IGNORECASE)
# Looser PAN-like token so Phase 1 can still capture invalid values such as ABCDE12345
PAN_LOOSE_RE = re.compile(r"\bPAN[:\s-]*([A-Z]{5}[0-9]{4,5}[A-Z]?)\b", re.IGNORECASE)
AADHAAR_RE = re.compile(r"\b(\d{4}[\s-]?\d{4}[\s-]?\d{4})\b")
GSTIN_RE = re.compile(
    r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9])\b",
    re.IGNORECASE,
)
STATE_RE = re.compile(r"\bState\s*:\s*([A-Za-z][A-Za-z .&-]+)", re.IGNORECASE)
GST_TYPE_RE = re.compile(r"\bType\s*:\s*([A-Za-z][A-Za-z -]+)", re.IGNORECASE)
REGISTRATION_DATE_RE = re.compile(
    r"\bDate\s+of\s+registration\s*:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})",
    re.IGNORECASE,
)
CONSUMER_NUMBER_RE = re.compile(
    r"\b(?:consumer\s+(?:number|no\.?)|connection\s+(?:number|no\.?))"
    r"\s*[:#-]\s*([A-Z0-9/-]+)",
    re.IGNORECASE,
)
CONSUMPTION_RE = re.compile(r"\b(?:units|consumption)\s*:\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
AMOUNT_RE = re.compile(
    r"\b(?:amount|total|bill\s+amount)\s*:\s*(?:Rs\.?|INR)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
BILLING_ADDRESS_RE = re.compile(
    r"\b(?:billing\s+address|address)\s*:\s*(.+?)(?=\n|$)", re.IGNORECASE
)
EMAIL_RE = re.compile(r"\b([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})\b", re.IGNORECASE)
PHONE_RE = re.compile(r"\b(?:\+91[\s-]?)?([6-9]\d{4}[\s-]?\d{5})\b")
ACCOUNT_NUMBER_RE = re.compile(
    r"\b(?:a/c|account(?:\s+number)?|account\s+no\.?)\s*[:#-]?\s*"
    r"([Xx*]+\d{4,}|[0-9]{6,})\b",
    re.IGNORECASE,
)
NAME_RES = [
    re.compile(r"Name:\s*([A-Za-z][A-Za-z .]+)", re.IGNORECASE),
    re.compile(r"Legal name:\s*([A-Za-z][A-Za-z .]+)", re.IGNORECASE),
    re.compile(r"Account holder:\s*([A-Za-z][A-Za-z .]+?)(?=\s+A/c\b|\s+Account\b|$)", re.IGNORECASE),
    re.compile(r"Consumer:\s*([A-Za-z][A-Za-z .]+)", re.IGNORECASE),
    re.compile(r"I['’]m\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"),
    re.compile(r"I am\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"),
    re.compile(r"([A-Z][A-Za-z .]+)\s+here\.", re.IGNORECASE),
]

SERVICE_KEYWORDS = {
    "ITR": ["itr", "income tax return", "income-tax"],
    "GST": ["gst registration", "gst return", "gstin", "gst"],
    "AUDIT": ["audit"],
}

DOC_TYPE_HINTS = {
    "aadhaar": ["aadhaar", "aadhar", "uidai", "Aadhaar No", "aadhar no", "aadhaar number", "aadhar number"],
    "pan": ["income tax department", "permanent account", " pan:", "pan no", "pan number", "permanent account number", "PAN CARD", "PAN"],
    "gst": ["gst registration", "gstin"],
    "bank_statement": ["bank statement", "account statement", "ifsc"],
    "electricity_bill": ["electricity bill", "units:", "consumer:"],
}


def _clean(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", value).strip(" .,\n\t")


def _normalize_aadhaar(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return f"{digits[0:4]} {digits[4:8]} {digits[8:12]}" if len(digits) == 12 else digits


def _normalize_phone(value: str) -> str:
    return re.sub(r"\D", "", value)[-10:]


def _detect_service(text: str) -> str | None:
    lowered = text.lower()
    for service, keywords in SERVICE_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return service
    return None


def detect_document_type(filename: str, text: str) -> str:
    blob = f"{filename} {text}".lower()
    for doc_type, hints in DOC_TYPE_HINTS.items():
        if any(hint in blob for hint in hints):
            return doc_type
    return "unknown"


def extract_fields(text: str, filename: str = "") -> dict[str, Any]:
    """Pull onboarding fields from free text. Phase 1 stores values; Phase 2 validates."""
    pan = None
    strict = PAN_RE.search(text.upper())
    if strict:
        pan = strict.group(1).upper()
    else:
        loose = PAN_LOOSE_RE.search(text)
        if loose:
            pan = loose.group(1).upper()

    aadhaar_match = AADHAAR_RE.search(text)
    gstin_match = GSTIN_RE.search(text)
    email_match = EMAIL_RE.search(text)
    phone_match = PHONE_RE.search(text)
    account_number_match = ACCOUNT_NUMBER_RE.search(text)
    state_match = STATE_RE.search(text)
    gst_type_match = GST_TYPE_RE.search(text)
    registration_date_match = REGISTRATION_DATE_RE.search(text)
    consumer_number_match = CONSUMER_NUMBER_RE.search(text)
    consumption_match = CONSUMPTION_RE.search(text)
    amount_match = AMOUNT_RE.search(text)
    billing_address_match = BILLING_ADDRESS_RE.search(text)

    name = None
    for pattern in NAME_RES:
        match = pattern.search(text)
        if match:
            name = _clean(match.group(1))
            break

    return {
        "name": name,
        "pan": pan,
        "aadhaar": _normalize_aadhaar(aadhaar_match.group(1)) if aadhaar_match else None,
        "email": email_match.group(1).lower() if email_match else None,
        "phone": _normalize_phone(phone_match.group(1)) if phone_match else None,
        "account_number": account_number_match.group(1) if account_number_match else None,
        "state": _clean(state_match.group(1)) if state_match else None,
        "gst_type": _clean(gst_type_match.group(1)) if gst_type_match else None,
        "registration_date": registration_date_match.group(1) if registration_date_match else None,
        "consumer_number": consumer_number_match.group(1) if consumer_number_match else None,
        "consumption": consumption_match.group(1) if consumption_match else None,
        "amount": amount_match.group(1).replace(",", "") if amount_match else None,
        "billing_address": _clean(billing_address_match.group(1)) if billing_address_match else None,
        "service_needed": _detect_service(text),
        "gstin": gstin_match.group(1).upper() if gstin_match else None,
        "document_type": detect_document_type(filename, text),
    }


def merge_fields(*payloads: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "name": None,
        "pan": None,
        "aadhaar": None,
        "email": None,
        "phone": None,
        "account_number": None,
        "state": None,
        "gst_type": None,
        "registration_date": None,
        "consumer_number": None,
        "consumption": None,
        "amount": None,
        "billing_address": None,
        "service_needed": None,
        "gstin": None,
    }
    for payload in payloads:
        for key in merged:
            value = payload.get(key)
            if value and not merged[key]:
                merged[key] = value
    return merged
