CLASSIFY_PROMPT = """You are classifying one document from a health insurance claim package.

Choose exactly one doc_type:
- CASE_SHEET: hospital case sheet / admission note for the CURRENT admission
- POLICY: insurance policy document, terms, schedule, exclusions
- PRE_AUTH: pre-authorization / cashless request form
- PRIOR_REPORT: earlier medical record, discharge summary or test report, from BEFORE the current admission
- INSURER_LETTER: query, rejection or approval letter from the insurer
- OTHER: anything else, or if you are not confident

If you are unsure, choose OTHER. Give a one-sentence reason.

File name: {name}

Document content:
{content}
"""

# Day 4 changes in EXTRACT_PROMPT: "L12:" line-number rule, placeholder rule
# ("refer to your policy schedule" -> null), "line" for events and referenced docs.
EXTRACT_PROMPT = """You are extracting facts from ONE document of a health insurance claim package.
Document type: {doc_type}
File name: {name}

STRICT RULES:
- Use ONLY what is written in the document. Never guess, infer or invent.
- If a field is not stated in this document, return null for it.
- Do NOT diagnose and do NOT give medical advice.
- Each field has a "value" and a "page" (the page number from the [Page N] markers where you found it).
- Every line of the document starts with a marker like "L12:". For every field, event and referenced document also give "line": the line number or range where you found it, as a string like "12" or "12-14". Use null if there are no L markers.
- If a field only points elsewhere or is a placeholder (for example "refer to your policy schedule", "N/A", blank), return null for it.
- Keep values short and close to the document's own wording.

FIELDS:
- patient_name, diagnosis, admission_date (as written), insurer, policy_number
- symptoms: symptoms documented
- treatment: treatment documented or planned
- reason_for_hospitalization: why hospitalization is needed, as stated

EVENTS:
List every medical or claim event stated in the document, whether or not it has a date. Examples: admission, symptom onset, a documented past condition or past treatment, a test or report, treatment given or advised, pre-auth submitted, insurer letter issued.
- Include past history items as events (for example "Hypertension, on medication").
- Include symptom onset as an event when the document gives it (for example "Chest discomfort and breathlessness for 3 days").
- Do not list policy terms or clauses as events.
- "date_text": the date or time reference exactly as written ("12-09-2026", "for 3 days", "since 2019"), or null if there is none.
- "date": convert to ISO YYYY-MM-DD (or YYYY-MM if the day is missing) ONLY when the document states an actual calendar date. Dates are usually DD-MM-YYYY. Never calculate a date from a relative phrase like "3 days ago", and never guess. If there is no actual date, set date to null.
- "page": page where the event appears.
- "line": line number or range where the event appears.

REFERENCED DOCUMENTS:
List every other document or report that THIS document says is attached, enclosed, submitted, to be submitted, or requested (for example "TMT report to be submitted", "lab report attached", "please send discharge summary").
- "name": the document or report as described.
- "context": the exact situation (attached / to be submitted / requested by insurer).
- "page": page where it is mentioned.
- "line": line number or range where it is mentioned.
- Do NOT list treatments or tests that are merely advised unless a report for them is mentioned.
- If none, return an empty list.

Document content:
{content}
"""

# added
# Day 5: rewritten to extract EVERYTHING in the policy (9 categories instead of 5),
# keep every item of a list, skip contact details, and give page + line.
POLICY_PROMPT = """You are reading an insurance policy document. Extract EVERY clause and piece of information in it as separate entries, using only what is written. Do not skip a section because it looks minor.

CATEGORIES (choose exactly one per entry):
- COVERAGE: what the policy covers (in-patient hospitalization, pre- and post-hospitalization, day care, ambulance, AYUSH, domiciliary, organ donor, modern treatments, etc.)
- OPTIONAL_COVER: optional or add-on covers
- WAITING_PERIOD: initial waiting period, pre-existing disease waiting period, specific-illness or procedure waiting periods
- EXCLUSION: general and specific exclusions
- SUB_LIMIT: room rent limits, disease-wise or procedure-wise caps
- COPAY_DEDUCTIBLE: co-payment or deductible
- HOSPITALIZATION_DAYCARE: minimum hospitalization duration, day-care procedure conditions
- CLAIM_PROCESS: cashless and reimbursement steps, intimation and document deadlines, turnaround times
- OTHER_TERMS: anything else (cumulative bonus, renewal, portability, moratorium, free look, policyholder obligations, benefit or premium tables, etc.)

RULES:
- One entry per clause. "title" is short. "summary" restates the clause with ALL key numbers, limits, durations and conditions.
- If a clause is a list (for example listed procedures, listed exclusions, listed waiting-period conditions), include EVERY item in the summary. Never shorten a list with "etc." or "and others".
- "clause_ref" is the clause/section number if shown, else null. "page" comes from the [Page N] markers. "line" is the line number or range from the "L12:" markers, as a string like "12-15", else null.
- Skip contact numbers, e-mail addresses, website links and grievance contact details.
- If something is not in the policy, return nothing for it. Never assume or invent clauses.
- Do not decide coverage.

File name: {name}

Document content:
{content}
"""

# Day 4 changes: line citations, query_items (task 4), next_actions (task 5),
# missing-evidence filter, raw-text contradiction check.
# Day 5 changes: advisor notes rule, pre-existing flagging (task 1), coverage_checks
# (task 6), summaries (task 7).
REASON_PROMPT = """You support an insurance advisor reviewing ONE health claim package. You do NOT decide claims.

RULES:
- Use ONLY the documents below. Never invent facts.
- Never say a claim should be approved, rejected or is covered/not covered. Do not use the words approved, rejected, denied, covered, not covered, eligible, payable or admissible as a conclusion about this claim or any treatment. Where applicability is unclear write "Needs human review".
- If a fact is not stated in the documents (for example the policy start date), write "Not documented in uploaded documents". Never estimate or assume it.
- Never give clinical advice or say what the patient should undergo, take, start or stop.
- "Clause mentioned in the supplied policy" and "applicable to this case" are different things. You may only report the first. Applicability is always for a human to decide.
- Never diagnose.
- Never decide which conflicting document is correct. Just report the conflict.
- Cite the document name, page and line for every item. Copy the "line" values from the extracted data (null if none).
- ADVISOR NOTES, if present, come from the advisor and are NOT document facts. Use them only when relevant to this claim and always call them "advisor note". If an advisor note conflicts with a document, report it as a contradiction using "Advisor note" as the document name.

TASKS:
1. policy_links: for each policy clause below that could matter to THIS case, give "clause_title", "why_relevant" (one sentence naming the case fact it relates to, e.g. a past-history item or the admission), and "case_fact". Skip clauses with no plausible connection. Do NOT say whether the clause applies.
   PRE-EXISTING CONDITIONS: a past-history item or an earlier report MAY be relevant to the policy's pre-existing disease waiting period or exclusion. A past condition does NOT by itself prove that it began before the policy start date; that is only known if the documents state both the policy start date and when the condition began. For each past-history item, add a policy_link to the pre-existing waiting period / exclusion clause with "pre_existing_related" set to true, and describe it as a POSSIBLE link only. If the policy start date or the onset date is not stated, write "Policy start date: Not documented in uploaded documents" (or "Onset date: Not documented in uploaded documents") in "why_relevant". Never assume either date. Never state that the condition is, or is not, pre-existing, covered or excluded. Leave "pre_existing_related" false for every other link.
2. missing_evidence: documents or reports that are referenced as attached/to be submitted/requested in any document but are NOT among the uploaded files. Only list documents needed to assess THIS claim (medical reports, case sheet, pre-auth, policy schedule/wordings, insurer-requested items). Ignore website links, grievance lists, brochures and general information documents. For each: "item", "why_needed", "referenced_in_doc", "page", "line". If an uploaded file is clearly that document, do not list it.
3. contradictions: meaningful differences between documents (symptom onset or duration, dates, diagnosis, treatment, past history, policy or insurer details, "no previous episodes" vs documented history). For each: topic, statement_a with doc_a, page_a and line_a, statement_b with doc_b, page_b and line_b, and a neutral "note". Compare only documents that actually say something about the same thing. Use both the extracted data and the FULL TEXT sections. Check symptom duration and onset across the case sheet, pre-auth and prior reports, and check any "no previous episodes" statement against documented history. If there are none, return an empty list.
4. query_items: ONLY if an INSURER_LETTER is among the uploaded files, otherwise return an empty list. For each distinct query, reason or requirement stated in the letter, give:
   - "stated_reason": the insurer's stated reason, close to the letter's own wording
   - "letter_doc", "letter_page" and "letter_line"
   - "linked_evidence": the fact, document, gap, contradiction or policy clause in the package that connects to this reason. If nothing connects, write "No connected evidence found in supplied documents".
   - "linked_doc", "linked_page" and "linked_line" for that evidence
   - "note": one neutral sentence. Do NOT say whether the insurer is right or wrong.
5. next_actions: 3 to 5 practical actions for the advisor, most important first. Base them on missing evidence, contradictions, the insurer letter (if any), pre-existing condition flags and policy clauses that need review. Each has "action" (e.g. obtain a document, verify a fact, clarify a conflict, review a clause), "reason", "source_doc", "source_page" and "source_line". Never recommend approving, rejecting or contesting the claim.
6. coverage_checks: ONLY if a policy is among the uploaded files, otherwise return an empty list. For each key item of the current admission (diagnosis, each treatment or procedure, type of hospitalization, each past-history condition), give "case_item", "case_source_doc", "case_source_page", "case_source_line", and "status". Set "status" to exactly "CLAUSE MENTIONED IN SUPPLIED POLICY" if the policy clauses below contain a clause that mentions or clearly relates to the item (waiting period, exclusion, sub-limit, coverage, day-care condition), with "clause_title", "clause_doc", "clause_page", "clause_line". This only means a related clause exists; it does NOT mean the item is covered or that the clause applies to this case. Otherwise set "status" to exactly "NOT FOUND IN SUPPLIED POLICY". Never assume coverage. In "note" give one neutral sentence and never say whether the item is covered.
7. Summaries: "case_overview" is 3 to 5 plain sentences on what the package shows (patient, admission, key history, insurer, open gaps), using document facts only. "doc_summaries" has one entry per uploaded file with "doc" (file name), "doc_type" and a 2 to 3 sentence factual "summary" of that document. If an advisor note exists, do not mix it into these summaries.

{bundle}
"""
