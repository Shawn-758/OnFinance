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
    unusable = sorted(
        {
            document_type
            for document in documents
            if (document_type := document.get("document_type")) in required
            and (
                document.get("quality_flag") in {"low_quality", "unreadable"}
                or not (document.get("text") or "").strip()
            )
        }
    )
    present = sorted(
        {
            document_type
            for document in documents
            if (document_type := document.get("document_type")) in required
            and document_type not in unusable
            and document.get("quality_flag", "ok") == "ok"
            and (document.get("text") or "").strip()
        }
    )
    missing = [document_type for document_type in required if document_type not in present]
    return {
        "service": normalized_service,
        "required_documents": required,
        "present_documents": present,
        "missing_documents": missing,
        "unusable_documents": unusable,
        "complete": bool(normalized_service) and not missing,
    }


def build_missing_documents_email(
    recipient: str | None,
    client_name: str | None,
    checklist: dict[str, Any],
    validation_results: list[dict[str, Any]] | None = None,
    documents: list[dict[str, Any]] | None = None,
) -> dict[str, str] | None:
    missing = checklist.get("missing_documents", [])
    invalid_documents = [
        result
        for result in validation_results or []
        if not result.get("valid")
    ]
    unusable_documents = [
        document
        for document in documents or []
        if document.get("quality_flag") in {"low_quality", "unreadable"}
        or not (document.get("text") or "").strip()
    ]
    if not recipient or (not missing and not invalid_documents and not unusable_documents):
        return None
    lines: list[str] = []
    for item in missing:
        label = DOCUMENT_LABELS.get(item, item.replace("_", " "))
        lines.append(f"- {label}: required document was not received")
    for result in invalid_documents:
        label = DOCUMENT_LABELS.get(
            result.get("document_type", ""),
            result.get("document_type", "document").replace("_", " "),
        )
        reasons = "; ".join(result.get("errors", [])) or "document validation failed"
        lines.append(f"- {label}: please resubmit a valid copy ({reasons})")
    for document in unusable_documents:
        document_type = document.get("document_type") or "document"
        label = DOCUMENT_LABELS.get(
            document_type,
            document_type.replace("_", " "),
        )
        quality = document.get("quality_flag")
        reason = (
            "image appears blurry or low quality"
            if quality == "low_quality"
            else "document could not be read"
        )
        lines.append(f"- {label}: please resubmit a clear, legible copy ({reason})")
    document_list = "\n".join(lines)
    greeting_name = client_name or "Client"
    service = checklist.get("service") or "requested service"
    return {
        "to": recipient,
        "subject": f"Documents required for your {service} application",
        "body": (
            f"Dear {greeting_name},\n\n"
            f"Thank you for contacting us regarding {service}. "
            "To continue processing your request, please provide or resubmit "
            "the following document(s):\n\n"
            f"{document_list}\n\n"
            "Please reply to this email with clear, legible copies of the "
            "required documents. Once received, we will validate them and "
            "continue with your onboarding.\n\n"
            "Kind regards,\n"
            "Onboarding Team"
        ),
    }
