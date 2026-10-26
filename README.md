# Health Claim Readiness & Rejection Intelligence (POC)

Streamlit + Gemini proof of concept that reads a health-claim document package and shows
what is documented, what is missing, where documents disagree, and which policy clauses
may be relevant. **Synthetic / de-identified documents only.**

The tool never approves or rejects a claim, never decides coverage, and never gives
clinical advice. Anything it cannot confirm is shown as "Not documented", "Not found in
supplied policy" or "Needs human review".

## Requirements
- Python 3.10 or newer
- A Gemini API key

## Setup (Windows PowerShell)
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```
Open `.env` and set:

| Variable | Meaning |
|---|---|
| `GEMINI_API_KEY` | Your Gemini API key (required) |
| `GEMINI_MODEL` | Model name to use (required) |
| `GEMINI_FALLBACK_MODEL` | Optional model tried if the main one keeps failing |

If `GEMINI_API_KEY` or `GEMINI_MODEL` is missing, the app shows an error and stops.
`.env` is git-ignored. Never commit a real key.

## Run
```powershell
streamlit run app.py
```
Then open http://localhost:8501, upload documents, and click **Analyze claim**.

## Tests (offline, no API key, no Gemini calls)
```powershell
pip install pytest
python -m pytest tests -v
```

## Demo cases
`demo_cases/` has three synthetic packages with expected results: first admission (A),
prior history with missing evidence and contradictions (B), and an insurer letter (C).
See `demo_cases/README.md`. The older `sample_docs/` files intentionally disagree on
insurer and policy number, to show the identity-mismatch warning.

## What the app checks without AI (deterministic)
- Insurer, policy number and patient name are compared across all documents.
- Every file / page / line cited by the AI is checked against the uploaded files.
  Unconfirmed sources are marked "Unverified source / Needs human review".
- Per-file and whole-case status. A failed file produces a "Partial analysis" warning
  and "not verified" instead of a false all-clear.
- Generated text containing claim-decision, definitive-coverage or clinical wording is
  withheld and flagged.

## Known limitations
- A source check confirms that the cited file, page and line exist, not that the line
  supports the claim made about it.
- Policy start date is not extracted yet, so pre-existing-condition links always need
  human review.
- Gemini output varies between runs; compare against `demo_cases/README.md` by hand.