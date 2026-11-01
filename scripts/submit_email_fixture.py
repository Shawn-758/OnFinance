"""Submit every email in email.txt to the running FastAPI application."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.extractors.email_parser import split_sample_emails  # noqa: E402


def submit_email(api_url: str, message: str, source_ref: str) -> dict[str, object]:
    payload = json.dumps(
        {"raw_email": message, "source_ref": source_ref}
    ).encode("utf-8")
    request = Request(
        f"{api_url.rstrip('/')}/ingest/email",
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Submit all messages from email.txt to /ingest/email."
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="FastAPI base URL (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--file",
        default="email.txt",
        help="Fixture file (default: email.txt)",
    )
    args = parser.parse_args()

    fixture_path = Path(args.file)
    if not fixture_path.is_absolute():
        fixture_path = ROOT_DIR / fixture_path
    messages = split_sample_emails(fixture_path.read_text(encoding="utf-8"))
    print(f"Submitting {len(messages)} email(s) from {args.file}")
    for number, message in enumerate(messages, start=1):
        source_ref = f"{fixture_path.name}#email-{number}"
        try:
            result = submit_email(args.url, message, source_ref)
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f"Email {number}: request failed: {exc}")
            continue
        print(
            f"Email {number}: job_id={result['job_id']} "
            f"status={result['status']}"
        )


if __name__ == "__main__":
    main()
