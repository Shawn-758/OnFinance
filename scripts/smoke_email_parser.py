"""Quick Phase 1 check that does not require Tesseract or MySQL."""

from pathlib import Path

from app.extractors.email_parser import parse_email_text, split_sample_emails
from app.extractors.field_extractor import extract_fields


def main() -> None:
    blob = Path("sample_emails.txt").read_text(encoding="utf-8")
    messages = split_sample_emails(blob)
    print(f"split into {len(messages)} emails")
    for message in messages:
        parsed = parse_email_text(message)
        print("---")
        print(parsed["from_email"], parsed["attachments"])
        print(parsed["fields"])

    pan_text = "Name: ROHAN MEHTA\nPAN: ABCDE1234F\nAadhaar: 1234 5678 9012"
    print("image-like fields", extract_fields(pan_text, "sample_pan_rohan.png"))


if __name__ == "__main__":
    main()
