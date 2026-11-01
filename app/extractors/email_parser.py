from __future__ import annotations

import re
from typing import Any

from app.extractors.field_extractor import extract_fields


HEADER_RE = re.compile(
    r"^(Email\s+\d+[^\n|]*?)\s*\|\s*From:\s*([^|]+?)\s*\|\s*Attachments:\s*(.+)$",
    re.IGNORECASE,
)
FROM_RE = re.compile(r"^From:\s*([^|\n]+)", re.IGNORECASE | re.MULTILINE)
ATTACH_RE = re.compile(r"^Attachments?:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
INLINE_ATTACH_RE = re.compile(r"\|\s*Attachments?:\s*([^|\n]+)", re.IGNORECASE)


def split_sample_emails(blob: str) -> list[str]:
    """Split the sample_emails.txt dump into individual messages."""
    parts = re.split(r"\n(?=Email\s+\d+)", blob.strip())
    return [part.strip() for part in parts if part.strip() and not part.startswith("All values")]


def parse_email_text(raw: str) -> dict[str, Any]:
    """Parse either a natural email body or the sample_emails.txt format."""
    lines = raw.strip().splitlines()
    header = lines[0] if lines else ""
    from_addr = None
    attachments: list[str] = []
    body = raw

    header_match = HEADER_RE.match(header)
    if header_match:
        from_addr = header_match.group(2).strip()
        attachments = [item.strip() for item in header_match.group(3).split(",") if item.strip()]
        body = "\n".join(lines[1:]).strip()
    else:
        from_match = FROM_RE.search(raw)
        attach_match = ATTACH_RE.search(raw)
        if from_match:
            from_addr = from_match.group(1).strip()
        if attach_match:
            attachments = [
                item.strip() for item in attach_match.group(1).split(",") if item.strip()
            ]
        else:
            inline_attach_match = INLINE_ATTACH_RE.search(raw)
            if inline_attach_match:
                attachments = [
                    item.strip()
                    for item in inline_attach_match.group(1).split(",")
                    if item.strip()
                ]

    fields = extract_fields(raw)
    if from_addr and not fields.get("email"):
        fields["email"] = from_addr.lower()
    elif from_addr:
        fields["email"] = from_addr.lower()

    return {
        "from_email": from_addr.lower() if from_addr else fields.get("email"),
        "attachments": attachments,
        "body": body,
        "fields": fields,
        "raw": raw.strip(),
    }
