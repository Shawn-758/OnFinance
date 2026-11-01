# OnFinance onboarding prototype

FastAPI prototype for client email intake, OCR/PDF extraction, document validation,
service checklists, approved email follow-ups, and Google Sheets tracking.

## Setup

Install dependencies and configure a local `.env`:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Set `DATABASE_URL=sqlite:///./onFinance.db` and the Tesseract executable path.
Use `EMAIL_BACKEND=console` for a no-send terminal demo, or use
`EMAIL_BACKEND=gmail_draft` to create an unsent draft in your personal Gmail account.
For Gmail drafts, create a Google Cloud OAuth desktop-client credential JSON, enable
the Gmail API, and set `GMAIL_CREDENTIALS_FILE`. The first draft opens a browser for
Google consent; the resulting `gmail-token.json` is reused locally and is ignored by Git.
This uses Gmail's `gmail.compose` scope and does not send automatically. For Sheets,
set `TRACKER_BACKEND=gspread`, the service-account JSON
path, Sheet ID, and worksheet name after sharing the Sheet with that service account.

Open `http://127.0.0.1:8000/docs`.


## Endpoints

- `POST /ingest/email` queues an email and local attachment names.
- `POST /ingest/documents` uploads documents with an optional client email.
- `GET /ingest/jobs/{job_id}` returns extraction, validation, checklist, and delivery state.
- `POST /ingest/jobs/{job_id}/approve-email` approves and sends a generated follow-up
  for console/SMTP mode; Gmail-draft mode leaves the final send to Gmail.
- `POST /ingest/reminders/run` sends one follow-up for unresolved jobs older than two days.
- `GET /clients` lists stored clients.
- `POST /clients/{client_id}/review` moves a ready application to `under_review`.
- `POST /clients/{client_id}/approve` changes `ready_for_review` or `under_review` to `approved`.
- `POST /clients/{client_id}/onboard` changes `approved` to `onboarded`.
- `POST /clients/{client_id}/reject` changes an under-review or approved application to `rejected`.

## Workflow

```text
ingest  -> extract -> validate -> doc checklist -> email drafted
                                        |
                              staff approves email
                                        |
                                      send

client fields -> client record is created or updated
complete valid documents -> ready_for_review -> under_review -> approved -> onboarded
missing documents -> docs_pending
invalid documents -> correction_required
automation error -> processing_failed
```

## Client Record:
Name, PAN, email, phone, and service are saved, even when the checklist is incomplete.

This preserves a client record,
while documents are pending or being corrected.

DB handles duplicate records or follow up emails by cross checking email&&pan number if exists.


## Document Checklist: 
ITR: PAN and Aadhaar; 
GST: PAN and a GST document; 
Audit: PAN, Aadhaar, and a bank statement. 
Invalid or unreadable documents are not complete.


## Validation

Each service has a specific set of document requirements and each document has a set of rules on which the document is validated and the stored upon successful validation failure for validation leads to followups 

example cases: Invalid aadhar, pan , blurry addhar 


### Blurry or unreadable images

The OCR pipeline uses OpenCV's Laplacian variance to calculate a blur score.
With `BLUR_THRESHOLD=80.0`:

- Score below `80.0` is marked `low_quality`.
- Empty OCR output is marked `unreadable`.
- Both flags make the document unusable for the checklist.

An unusable required document is treated as unavailable and results in
`docs_pending`, with a draft asking the client to provide a clear, legible copy.
This is different from a readable document with invalid data, which results in
`correction_required`.

Status precedence is:

```text
processing_failed -> correction_required -> docs_pending -> ready_for_review
```

The client record is still saved even when a document is missing, blurry, or
invalid, so staff can track the application while waiting for a correction.


## Follow Ups
Email is drafted if the document checklist is incomplete or the attached documents are invalid or not processable

Invalid documents are given higher precedance than missing documents.

- Missing document Case:

If client submits:
PAN: valid
Aadhar: missing

result: doc pending and respective email is drafted

- Invalid Document and Missing Document Case:
PAN: invalid
Aadhaar: missing
Bank statement: missing

result : correction_required 

The drafted email addresses the invalid PAN and also lists the missing documents.

- Invalid document only
PAN: valid
Aadhaar: invalid

result : correction_required

The email notifies the client to resubmit a valid Aadhaar.


## Tracker 

keeps a track of the client status along with the name, phone, email and status field


## Limitations

- Email intake is through the API or sample folder; Gmail inbox polling is not included.
- The reminder runner must be called manually or by an external scheduler.
- Staff approval is represented by API endpoints, not an admin UI.
- SQLite is avaiable if preferred; MySQL is supported through configuration.