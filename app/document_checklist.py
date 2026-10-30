from __future__ import annotations

from typing import Any


SERVICE_CHECKLISTS: dict[str, tuple[str, ...]] = {
    "ITR": ("pan", "aadhaar"),
    "GST": ("pan", "gst"),
    "AUDIT": ("pan", "aadhaar", "bank_statement"),
}

DOCUMENT_LABELS = {
    "pan": "PAN card",
    "aadhaar": "Aadhaar card",
    "gst": "GST registration certificate or GST invoice",
    "bank_statement": "bank statement",
}


def normalize_service(service: str | None) -> str | None:
    if not service:
        return None
    value = service.strip().upper().replace("-", " ")
    if value in {"ITR", "ITR FILING", "INCOME TAX RETURN", "INCOME TAX"}:
        return "ITR"
    if value in {"GST", "GST REGISTRATION", "GST RETURN"}:
        return "GST"
    if value in {"AUDIT", "AUDITING"}:
        return "AUDIT"
    return None


def build_checklist(
    service: str | None, documents: list[dict[str, Any]]
) -> dict[str, Any]:
    normalized_service = normalize_service(service)
    required = list(SERVICE_CHECKLISTS.get(normalized_service or "", ()))
    present = sorted(
        {
            document_type
            for document in documents
            if (document_type := document.get("document_type")) in required
        }
    )
    missing = [document_type for document_type in required if document_type not in present]
    return {
        "service": normalized_service,
        "required_documents": required,
        "present_documents": present,
        "missing_documents": missing,
        "complete": bool(normalized_service) and not missing,
    }


def build_missing_documents_email(
    recipient: str | None, client_name: str | None, checklist: dict[str, Any]
) -> dict[str, str] | None:
    missing = checklist.get("missing_documents", [])
    if not recipient or not missing:
        return None
    labels = [DOCUMENT_LABELS.get(item, item.replace("_", " ")) for item in missing]
    document_list = "\n".join(f"- {label}" for label in labels)
    greeting_name = client_name or "Client"
    service = checklist.get("service") or "requested service"
    return {
        "to": recipient,
        "subject": f"Documents required for your {service} application",
        "body": (
            f"Dear {greeting_name},\n\n"
            f"Thank you for contacting us regarding {service}. "
            "To continue processing your request, please submit the following "
            "document(s):\n\n"
            f"{document_list}\n\n"
            "Please reply to this email with clear, legible copies of the "
            "required documents. Once received, we will validate them and "
            "continue with your onboarding.\n\n"
            "Kind regards,\n"
            "Onboarding Team"
        ),
    }
