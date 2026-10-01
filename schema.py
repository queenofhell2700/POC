from pydantic import BaseModel


class Event(BaseModel):
    date: str | None = None
    description: str
    source_doc: str
    source_page: int | None = None


class CaseFacts(BaseModel):
    patient_name: str | None = None
    diagnosis: str | None = None
    admission_date: str | None = None
    insurer: str | None = None
    policy_number: str | None = None
    events: list[Event] = []
