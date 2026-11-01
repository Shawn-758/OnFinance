from __future__ import annotations

from typing import Any

from app.config import get_settings


HEADERS = ["Client name", "Phone", "Email", "Status"]


def sync_client(fields: dict[str, Any], status: str) -> dict[str, str]:
    """Upsert one client row in Google Sheets, or report disabled demo mode."""
    settings = get_settings()
    if settings.tracker_backend.strip().lower() == "console":
        print(
            "Demo tracker row: "
            f"{fields.get('name') or ''} | {fields.get('phone') or ''} | "
            f"{fields.get('email') or ''} | {status}"
        )
        return {"status": "simulated", "backend": "console"}

    if settings.tracker_backend.strip().lower() != "gspread":
        return {"status": "not_synced", "backend": settings.tracker_backend}
    if not settings.google_service_account_file or not settings.google_sheet_id:
        return {
            "status": "not_synced",
            "backend": "gspread",
            "error": "GOOGLE_SERVICE_ACCOUNT_FILE and GOOGLE_SHEET_ID are required",
        }

    import gspread

    client = gspread.service_account(filename=settings.google_service_account_file)
    sheet = client.open_by_key(settings.google_sheet_id).worksheet(settings.google_worksheet)
    values = sheet.get_all_values()
    if not values:
        sheet.append_row(HEADERS)
        values = [HEADERS]
    if values[0] != HEADERS:
        raise ValueError(f"Tracker sheet headers must be exactly: {HEADERS}")

    email = str(fields.get("email") or "").strip().lower()
    row_values = [
        fields.get("name") or "",
        fields.get("phone") or "",
        email,
        status,
    ]
    for row_number, row in enumerate(values[1:], start=2):
        if email and len(row) >= 3 and row[2].strip().lower() == email:
            sheet.update(f"A{row_number}:D{row_number}", [row_values])
            return {"status": "synced", "backend": "gspread"}
    sheet.append_row(row_values)
    return {"status": "synced", "backend": "gspread"}
