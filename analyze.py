import json  # Day 5
import re
from dataclasses import dataclass, field
from pathlib import Path  # Day 5

import store  # Day 5: hash / local file / saved extraction tracking
from extract import extract_pdf_pages, extract_text_file
from llm import generate_json

# from prompts import CLASSIFY_PROMPT, EXTRACT_PROMPT

from prompts import CLASSIFY_PROMPT, EXTRACT_PROMPT, POLICY_PROMPT, REASON_PROMPT

# added
from schema import (
    CaseFacts,
    Classification,
    DocExtraction,
    DocType,
    Event,
    Fact,
    PolicyClause,  # Day 5: needed to load saved clauses from the DB
    PolicyExtraction,
    Reasoning,
)

IMAGE_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")

# Which document types may fill each case field (first match wins, in this order).
# Prior reports are deliberately NOT used for current-admission facts.
ADMISSION_DOCS = [DocType.CASE_SHEET, DocType.PRE_AUTH]
IDENTITY_DOCS = ADMISSION_DOCS + [DocType.INSURER_LETTER, DocType.POLICY]
FIELD_SOURCES = {
    "patient_name": IDENTITY_DOCS,
    "insurer": IDENTITY_DOCS,
    "policy_number": IDENTITY_DOCS,
    "diagnosis": ADMISSION_DOCS,
    "admission_date": ADMISSION_DOCS,
    "symptoms": ADMISSION_DOCS,
    "treatment": ADMISSION_DOCS,
    "reason_for_hospitalization": ADMISSION_DOCS,
}

# Day 5: token usage tracking. This is an ESTIMATE (about 4 characters per token).
USAGE: list = []


def _est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _log_usage(step: str, prompt: str, out):
    out_text = out.model_dump_json() if out is not None else ""
    USAGE.append(
        {
            "step": step,
            "input_tokens": _est_tokens(prompt),
            "output_tokens": _est_tokens(out_text),
        }
    )


@dataclass
class Doc:
    name: str
    pages: list = field(default_factory=list)  # [(page_num, text)]
    image_bytes: bytes | None = None
    mime: str | None = None
    doc_type: DocType = DocType.OTHER
    classify_reason: str = ""
    extraction: DocExtraction | None = None
    error: str | None = None
    policy_clauses: list = field(default_factory=list)
    # Day 5: upload tracking
    sha256: str | None = None
    file_path: str | None = None  # local path of the saved file
    record_id: int | None = None  # row id in the uploaded_docs table
    reused: bool = False  # True when the saved extraction was reused


def load_doc(name: str, data: bytes) -> Doc:
    lower = name.lower()
    if lower.endswith(".pdf"):
        return Doc(name, pages=extract_pdf_pages(data))
    if lower.endswith(".txt"):
        return Doc(name, pages=extract_text_file(data))
    ext = lower[lower.rfind(".") :]
    return Doc(name, image_bytes=data, mime=IMAGE_MIME[ext])


# Day 4: numbers the non-blank lines of a page as L1:, L2:, ...
def number_lines(text: str) -> str:
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(f"L{i}: {l}" for i, l in enumerate(lines, 1))


def _content(doc: Doc) -> str:
    if doc.image_bytes:
        return "(The document is the attached image. Treat it as page 1.)"
    return "\n\n".join(f"[Page {n}]\n{number_lines(t)}" for n, t in doc.pages)


# Day 5: added "step" so each call is logged in the token usage table
def _run(doc: Doc, prompt: str, schema, step: str = ""):
    if doc.image_bytes:
        out = generate_json(prompt, schema, doc.image_bytes, doc.mime)
    else:
        out = generate_json(prompt, schema)
    _log_usage(f"{step}: {doc.name}", prompt, out)
    return out


def classify(doc: Doc):
    prompt = CLASSIFY_PROMPT.format(name=doc.name, content=_content(doc))
    result: Classification = _run(
        doc, prompt, Classification, "classify"
    )  # Day 5: step
    doc.doc_type = result.doc_type
    doc.classify_reason = result.reason


"""def extract(doc: Doc):
    prompt = EXTRACT_PROMPT.format(
        doc_type=doc.doc_type.value, name=doc.name, content=_content(doc)
    )
    doc.extraction = _run(doc, prompt, DocExtraction)"""


def extract(doc: Doc):
    prompt = EXTRACT_PROMPT.format(
        doc_type=doc.doc_type.value, name=doc.name, content=_content(doc)
    )
    doc.extraction = _run(doc, prompt, DocExtraction, "extract")  # Day 5: step
    if doc.doc_type == DocType.POLICY:
        p = POLICY_PROMPT.format(name=doc.name, content=_content(doc))
        res: PolicyExtraction = _run(
            doc, p, PolicyExtraction, "policy clauses"
        )  # Day 5: step
        for c in res.clauses:
            c.source_doc = doc.name
        doc.policy_clauses = res.clauses


# ---------- Day 5: upload tracking (hash, local file, saved extraction) ----------
def _extract_and_save(doc: Doc):
    """Day 5: classify + extract, then save the result on the doc's DB record."""
    try:
        classify(doc)
        extract(doc)
        store.save_extraction(
            doc.record_id,
            doc.doc_type.value,
            doc.classify_reason,
            doc.extraction.model_dump_json(),
            json.dumps([c.model_dump(mode="json") for c in doc.policy_clauses]),
        )
        doc.error = None
    except Exception as e:
        doc.error = str(e)
        store.mark_failed(doc.record_id, str(e))


def _load_saved(doc: Doc, row):
    """Day 5: fill a Doc from its saved DB record. No LLM call."""
    doc.doc_type = DocType(row["doc_type"])
    doc.classify_reason = row["classify_reason"] or ""
    doc.extraction = DocExtraction.model_validate_json(row["extracted_data"])
    clauses = [
        PolicyClause.model_validate(c)
        for c in json.loads(row["policy_clauses"] or "[]")
    ]
    for c in clauses:
        c.source_doc = doc.name
    doc.policy_clauses = clauses
    doc.reused = True


def process_upload(name: str, data: bytes) -> Doc:
    """Day 5: hash the file. If the same file was extracted before, reuse the saved
    extraction (duplicate check). Otherwise save it locally, create a record,
    extract and save the extraction in that record."""
    sha256, sha512 = store.hashes(data)
    row = store.find_by_hash(sha512)
    doc = load_doc(name, data)
    doc.sha256 = sha256
    if row:
        doc.record_id = row["id"]
        doc.file_path = row["file_path"]
        if row["status"] == "EXTRACTED":
            _load_saved(doc, row)
            return doc
    else:
        doc.file_path = store.save_file(name, data, sha256)
        doc.record_id = store.create_record(name, sha256, sha512, doc.file_path)
    _extract_and_save(doc)
    return doc


def reextract(file_path: str) -> Doc:
    """Day 5: re-extract from the saved local file and overwrite the saved extraction."""
    row = store.find_by_path(file_path)
    if row is None:
        raise ValueError("No saved record for this file path")
    doc = load_doc(row["file_name"], Path(file_path).read_bytes())
    doc.sha256 = row["sha256"]
    doc.file_path = file_path
    doc.record_id = row["id"]
    _extract_and_save(doc)
    return doc


def merge_case(docs: list[Doc]) -> CaseFacts:
    case = CaseFacts()
    for fname, allowed in FIELD_SOURCES.items():
        for dtype in allowed:
            hit = None
            for d in docs:
                if d.doc_type == dtype and d.extraction:
                    f = getattr(d.extraction, fname)
                    if f and f.value:
                        hit = Fact(
                            value=f.value,
                            source_doc=d.name,
                            source_page=f.page,
                            source_line=f.line,  # Day 4
                        )
                        break
            if hit:
                setattr(case, fname, hit)
                break
    for d in docs:
        if not d.extraction:
            continue
        for e in d.extraction.events:
            iso = e.date if (e.date and ISO_DATE.match(e.date)) else None
            case.events.append(
                Event(
                    date=iso,
                    date_text=e.date_text,
                    description=e.description,
                    source_doc=d.name,
                    source_page=e.page,
                    source_line=e.line,  # Day 4
                )
            )
    return case


def build_timeline(events: list[Event]):
    dated = sorted((e for e in events if e.date), key=lambda e: e.date)
    undated = [e for e in events if not e.date]
    return dated, undated


# added
"""def _bundle(docs: list[Doc]) -> str:
    parts = ["UPLOADED FILES:"]
    for d in docs:
        parts.append(f"- {d.name} ({d.doc_type.value})")
    parts.append("\nPOLICY CLAUSES FOUND:")
    found = False
    for d in docs:
        for c in d.policy_clauses:
            found = True
            parts.append(
                f"- [{c.category.value}] {c.title}: {c.summary} "
                f"(source: {d.name}, p.{c.page}, ref {c.clause_ref})"
            )
    if not found:
        parts.append("(none: no policy uploaded or no clauses found)")
    parts.append("\nDOCUMENT TEXTS:")
    for d in docs:
        if d.image_bytes:
            body = "(image; extracted data) " + (
                d.extraction.model_dump_json() if d.extraction else ""
            )
        else:
            body = _content(d)
        parts.append(f"\n=== {d.name} [{d.doc_type.value}] ===\n{body}")
    return "\n".join(parts)"""


# reduced fn
# Day 5: added advisor_notes parameter
def _bundle(docs: list[Doc], advisor_notes: str = "") -> str:
    parts = ["UPLOADED FILES:"]
    for d in docs:
        parts.append(f"- {d.name} ({d.doc_type.value})")

    parts.append("\nPOLICY CLAUSES FOUND:")
    found = False
    for d in docs:
        for c in d.policy_clauses:
            found = True
            parts.append(
                f"- [{c.category.value}] {c.title}: {c.summary} "
                f"(source: {d.name}, p.{c.page}, line {c.line}, ref {c.clause_ref})"
            )
    if not found:
        parts.append("(none: no policy uploaded or no clauses found)")

    parts.append("\nEXTRACTED FACTS & EVENTS PER DOCUMENT:")
    for d in docs:
        if not d.extraction:
            parts.append(f"\n=== {d.name} ({d.doc_type.value}) ===\n(no extraction)")
            continue
        parts.append(f"\n=== {d.name} ({d.doc_type.value}) ===")
        # Dump the structured extraction as JSON — much smaller than raw text
        parts.append(d.extraction.model_dump_json(indent=None))
        # Day 4 fix: also send raw text (policy is covered by clauses) so statements
        # like "no previous episodes" are not lost. This fixes empty contradictions.
        if (
            d.doc_type not in (DocType.POLICY, DocType.INSURER_LETTER)
            and not d.image_bytes
        ):
            parts.append("FULL TEXT:\n" + _content(d))
        # Day 4: the insurer's stated reason lives in the letter text itself
        if d.doc_type == DocType.INSURER_LETTER:
            parts.append("FULL LETTER TEXT:\n" + _content(d))

    # Day 5: extra info from the advisor, kept separate from document facts
    if advisor_notes.strip():
        parts.append(
            "\nADVISOR NOTES (from the advisor, NOT from a document):\n"
            + advisor_notes.strip()
        )

    return "\n".join(parts)


# Day 5: added advisor_notes parameter and token logging
def reason(docs: list[Doc], advisor_notes: str = "") -> Reasoning:
    from llm import generate_json

    prompt = REASON_PROMPT.format(bundle=_bundle(docs, advisor_notes))
    out = generate_json(prompt, Reasoning)
    _log_usage("reasoning", prompt, out)
    return out


# replaced
# Day 5: uses hash-based upload tracking, takes advisor notes, returns token usage
def analyze_package(
    files: list[tuple[str, bytes]], existing_docs=None, advisor_notes: str = ""
) -> dict:
    USAGE.clear()  # usage is per run
    docs = list(existing_docs or [])
    known = {d.sha256 for d in docs if d.sha256}
    skipped = []
    for name, data in files:
        sha256, _ = store.hashes(data)
        if sha256 in known:
            skipped.append(name)  # same file already in this case
            continue
        doc = process_upload(name, data)  # Day 5: hash, save locally, reuse or extract
        known.add(sha256)
        docs.append(doc)
    case = merge_case(docs)
    dated, undated = build_timeline(case.events)

    reasoning, reason_error = None, None
    try:
        reasoning = reason(docs, advisor_notes)
    except Exception as e:
        reason_error = str(e)

    clauses = [c for d in docs for c in d.policy_clauses]
    return {
        "docs": docs,
        "case": case,
        "dated": dated,
        "undated": undated,
        "clauses": clauses,
        "reasoning": reasoning,
        "reason_error": reason_error,
        "usage": list(USAGE),  # Day 5
        "skipped": skipped,  # Day 5
        "advisor_notes": advisor_notes,  # Day 5
    }
