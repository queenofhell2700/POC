from enum import Enum
from pydantic import BaseModel, Field


class DocType(str, Enum):
    CASE_SHEET = "CASE_SHEET"
    POLICY = "POLICY"
    PRE_AUTH = "PRE_AUTH"
    PRIOR_REPORT = "PRIOR_REPORT"
    INSURER_LETTER = "INSURER_LETTER"
    OTHER = "OTHER"


class Classification(BaseModel):
    doc_type: DocType
    reason: str


# ---------- What the LLM returns, one document at a time ----------
class ExtractedField(BaseModel):
    value: str | None = None
    page: int | None = None
    line: str | None = None


class ExtractedEvent(BaseModel):
    date: str | None = None  # ISO: YYYY-MM-DD or YYYY-MM, else null
    date_text: str | None = None  # date exactly as written in the document
    description: str
    page: int | None = None
    line: str | None = None


class ReferencedDoc(BaseModel):
    name: str
    context: str | None = None  # e.g. "report to be submitted", "attached"
    page: int | None = None
    line: str | None = None


class DocExtraction(BaseModel):
    patient_name: ExtractedField | None = None
    diagnosis: ExtractedField | None = None
    admission_date: ExtractedField | None = None
    insurer: ExtractedField | None = None
    policy_number: ExtractedField | None = None
    symptoms: ExtractedField | None = None
    treatment: ExtractedField | None = None
    reason_for_hospitalization: ExtractedField | None = None
    events: list[ExtractedEvent] = []
    # added
    referenced_documents: list[ReferencedDoc] = []


# ---------- Case-level facts, each carrying its own source ----------
class Fact(BaseModel):
    value: str | None = None  # None = UNKNOWN
    source_doc: str | None = None
    source_page: int | None = None
    source_line: str | None = None


class Event(BaseModel):
    date: str | None = None
    date_text: str | None = None
    description: str | None = None
    source_doc: str | None = None
    source_page: int | None = None
    source_line: str | None = None


class CaseFacts(BaseModel):
    patient_name: Fact = Field(default_factory=Fact)
    diagnosis: Fact = Field(default_factory=Fact)
    admission_date: Fact = Field(default_factory=Fact)
    insurer: Fact = Field(default_factory=Fact)
    policy_number: Fact = Field(default_factory=Fact)
    symptoms: Fact = Field(default_factory=Fact)
    treatment: Fact = Field(default_factory=Fact)
    reason_for_hospitalization: Fact = Field(default_factory=Fact)
    events: list[Event] = []


# added at bottom
class PolicyCategory(str, Enum):
    WAITING_PERIOD = "WAITING_PERIOD"
    EXCLUSION = "EXCLUSION"
    SUB_LIMIT = "SUB_LIMIT"
    COPAY_DEDUCTIBLE = "COPAY_DEDUCTIBLE"
    HOSPITALIZATION_DAYCARE = "HOSPITALIZATION_DAYCARE"
    # Day 5: extract everything in the policy, not just the 5 clause types above
    COVERAGE = "COVERAGE"
    OPTIONAL_COVER = "OPTIONAL_COVER"
    CLAIM_PROCESS = "CLAIM_PROCESS"
    OTHER_TERMS = "OTHER_TERMS"


class PolicyClause(BaseModel):
    category: PolicyCategory
    title: str
    summary: str
    clause_ref: str | None = None
    page: int | None = None
    line: str | None = None
    source_doc: str | None = None  # filled in by code


class PolicyExtraction(BaseModel):
    clauses: list[PolicyClause] = []


class PolicyLink(BaseModel):
    clause_title: str
    why_relevant: str
    case_fact: str | None = None
    pre_existing_related: bool = False  # Day 5: true for pre-existing condition links


class MissingItem(BaseModel):
    item: str
    why_needed: str
    referenced_in_doc: str | None = None
    page: int | None = None
    line: str | None = None


class Contradiction(BaseModel):
    topic: str
    statement_a: str
    doc_a: str
    page_a: int | None = None
    line_a: str | None = None
    statement_b: str
    doc_b: str
    page_b: int | None = None
    line_b: str | None = None
    note: str | None = None


# Day 4
class QueryItem(BaseModel):
    stated_reason: str
    letter_doc: str | None = None
    letter_page: int | None = None
    letter_line: str | None = None
    linked_evidence: str  # what in the package relates to it, or the gap
    linked_doc: str | None = None
    linked_page: int | None = None
    linked_line: str | None = None
    note: str | None = None


class NextAction(BaseModel):
    action: str
    reason: str
    source_doc: str | None = None
    source_page: int | None = None
    source_line: str | None = None


# Day 5: does the supplied policy have a clause for each case item?
class CoverageCheck(BaseModel):
    case_item: str
    case_source_doc: str | None = None
    case_source_page: int | None = None
    case_source_line: str | None = None
    status: str  # "CLAUSE FOUND" or "NOT FOUND IN SUPPLIED POLICY"
    clause_title: str | None = None
    clause_doc: str | None = None
    clause_page: int | None = None
    clause_line: str | None = None
    note: str | None = None


# Day 5: one summary per uploaded document (Summary tab)
class DocSummary(BaseModel):
    doc: str
    doc_type: str | None = None
    summary: str


class Reasoning(BaseModel):
    policy_links: list[PolicyLink] = []
    missing_evidence: list[MissingItem] = []
    contradictions: list[Contradiction] = []
    query_items: list[QueryItem] = []
    next_actions: list[NextAction] = []
    coverage_checks: list[CoverageCheck] = []  # Day 5
    case_overview: str | None = None  # Day 5
    doc_summaries: list[DocSummary] = []  # Day 5


# correction
# HCR-001: cross-document identity check
class IdentityValue(BaseModel):
    value: str
    source_doc: str
    source_page: int | None = None
    source_line: str | None = None


class IdentityConflict(BaseModel):
    field: str  # "insurer" | "policy_number" | "patient_name"
    label: str  # display label
    values: list[IdentityValue] = Field(default_factory=list)
