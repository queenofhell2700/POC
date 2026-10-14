import streamlit as st
from analyze import analyze_package, number_lines, reextract  # Day 5: reextract
from schema import DocType

st.set_page_config(page_title="Claim POC", layout="wide")

# Day 5: better wording than "UNKNOWN"
NOT_DOC = "Not documented in uploaded documents"
# Day 5: warn if one prompt is about this many estimated tokens
TOKEN_WARN = 30000

st.title("Health Claim Readiness & Rejection Intelligence")
st.caption(
    "POC • Synthetic / de-identified documents only • AI never approves or rejects a claim"
)

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

uploaded_files = st.file_uploader(
    "Upload claim documents (case sheet, policy, pre-auth, prior reports, insurer letter)",
    type=["pdf", "jpg", "jpeg", "png", "txt"],
    accept_multiple_files=True,
    key=f"uploader_{st.session_state['uploader_key']}",
)

if uploaded_files:
    st.success(f"{len(uploaded_files)} file(s) uploaded")

# Day 5: extra information from the advisor (kept separate from document facts)
advisor_notes = st.text_area(
    "Additional information from advisor (optional, only details relevant to this claim)",
    key=f"advisor_notes_{st.session_state['uploader_key']}",
    height=100,
)

existing = st.session_state.get("result")
analyze = st.button(
    # Day 5: also enabled with no new files, so updated notes can be re-analyzed
    "Re-analyze (new documents / updated notes)" if existing else "Analyze claim",
    type="primary",
    disabled=not (uploaded_files or existing),
)
if existing and st.button("Start new case"):
    st.session_state.pop("result", None)
    st.session_state["uploader_key"] += 1
    st.rerun()

if analyze:
    with st.spinner("Classifying and extracting..."):
        files = [(f.name, f.getvalue()) for f in (uploaded_files or [])]
        st.session_state["result"] = analyze_package(
            files, existing["docs"] if existing else None, advisor_notes  # Day 5: notes
        )

result = st.session_state.get("result")
reasoning = (
    result["reasoning"] if result else None
)  # Day 5: moved up, Summary tab uses it

# Day 5: tells the user a file was a duplicate
if result and result.get("skipped"):
    st.info("Already in this case, not re-processed: " + ", ".join(result["skipped"]))


def src(name, page=None, line=None):
    if not name:
        return ""
    out = name
    if page:
        out += f", Page {page}"
    if line:
        out += f", Line {line}"
    return out


# Day 5: tabs are now named, and Summary is added as the first tab
(
    t_summary,
    t_timeline,
    t_admission,
    t_policy,
    t_missing,
    t_contra,
    t_query,
    t_actions,
) = st.tabs(
    [
        "Summary",
        "Timeline",
        "Current admission",
        "Policy checks",
        "Missing evidence",
        "Contradictions",
        "Query / rejection",
        "Next actions",
    ]
)

# ---- Summary (Day 5: new tab) ----
with t_summary:
    st.subheader("Summary")
    if not result:
        st.write("Upload documents and click Analyze claim.")
    elif result["reason_error"]:
        st.error(result["reason_error"])
    else:
        if reasoning.case_overview:
            st.markdown("### Case overview")
            st.write(reasoning.case_overview)
        if reasoning.doc_summaries:
            st.markdown("### Summary of each document")
            for s in reasoning.doc_summaries:
                st.markdown(f"**{s.doc}**" + (f" ({s.doc_type})" if s.doc_type else ""))
                st.write(s.summary)
        if result["advisor_notes"].strip():
            st.markdown("### Advisor notes (not from a document)")
            st.write(result["advisor_notes"])

# ---- Timeline ----
with t_timeline:
    st.subheader("Medical & claim timeline")
    if not result:
        st.write("Upload documents and click Analyze claim.")
    else:
        if not any(d.doc_type == DocType.PRIOR_REPORT for d in result["docs"]):
            # Day 5: replaced "UNKNOWN"
            st.info(
                "No prior reports uploaded. Earlier medical history: not available in the uploaded documents."
            )
        for e in result["dated"]:
            st.markdown(f"**{e.date_text or e.date}**: {e.description}")
            st.caption(f"Source: {src(e.source_doc, e.source_page, e.source_line)}")
        if result["undated"]:
            st.markdown("### Date not documented")  # Day 5: replaced "Date: UNKNOWN"
            for e in result["undated"]:
                when = f" ({e.date_text})" if e.date_text else ""
                st.markdown(f"- {e.description}{when}")
                st.caption(f"Source: {src(e.source_doc, e.source_page, e.source_line)}")

# ---- Current admission ----
with t_admission:
    st.subheader("Current admission summary")
    if not result:
        st.write("Nothing yet.")
    else:
        labels = {
            "patient_name": "Patient",
            "diagnosis": "Diagnosis (as documented)",
            "admission_date": "Admission date",
            "insurer": "Insurer",
            "policy_number": "Policy number",
            "symptoms": "Symptoms",
            "treatment": "Treatment",
            "reason_for_hospitalization": "Reason for hospitalization",
        }
        for key, label in labels.items():
            fact = getattr(result["case"], key)
            st.markdown(f"**{label}:** {fact.value or NOT_DOC}")  # Day 5: NOT_DOC
            if fact.value:
                st.caption(
                    f"Source: {src(fact.source_doc, fact.source_page, fact.source_line)}"
                )

        with st.expander("Document classification"):
            for d in result["docs"]:
                if d.error:
                    st.error(f"{d.name}: {d.error}")
                    # Day 5: re-extract from the saved local file
                    if d.file_path and st.button(
                        f"Re-extract {d.name}", key=f"re_{d.record_id}"
                    ):
                        new_doc = reextract(d.file_path)
                        docs = [
                            new_doc if x.record_id == d.record_id else x
                            for x in result["docs"]
                        ]
                        st.session_state["result"] = analyze_package(
                            [], docs, result["advisor_notes"]
                        )
                        st.rerun()
                else:
                    # Day 5: shows when a saved extraction was reused
                    note = " (saved extraction reused)" if d.reused else ""
                    st.write(
                        f"**{d.name}** → {d.doc_type.value}: {d.classify_reason}{note}"
                    )

        with st.expander("Raw extracted text (debug)"):
            for d in result["docs"]:
                st.markdown(f"**{d.name}**")
                if d.image_bytes:
                    st.write("Image file, sent directly to the model.")
                for page_num, text in d.pages:
                    st.text(f"[Page {page_num}]\n{number_lines(text)}")

# ---- Not built yet ----
# Day 5: now shows all 9 policy categories
CAT_LABELS = {
    "COVERAGE": "Coverage (what the policy covers)",
    "OPTIONAL_COVER": "Optional covers",
    "WAITING_PERIOD": "Waiting periods",
    "EXCLUSION": "Exclusions",
    "SUB_LIMIT": "Sub-limits",
    "COPAY_DEDUCTIBLE": "Co-pay / deductible",
    "HOSPITALIZATION_DAYCARE": "Hospitalization / day-care conditions",
    "CLAIM_PROCESS": "Claim process",
    "OTHER_TERMS": "Other terms",
}

# ---- Policy checks ----
with t_policy:
    st.subheader("Policy / claim checks")
    if not result:
        st.write("Nothing yet.")
    else:
        has_policy = any(d.doc_type == DocType.POLICY for d in result["docs"])
        if not has_policy:
            st.warning(
                "No policy document uploaded. All policy conditions: NOT FOUND in supplied documents."
            )
        for cat, label in CAT_LABELS.items():
            st.markdown(f"### {label}")
            items = [c for c in result["clauses"] if c.category.value == cat]
            if not items:
                st.write("Not found in supplied policy.")
            for c in items:
                st.markdown(f"**{c.title}**: {c.summary}")
                st.caption(
                    f"Source: {src(c.source_doc, c.page, c.line)}"
                    + (f" • Clause {c.clause_ref}" if c.clause_ref else "")
                )
        if reasoning and reasoning.policy_links:
            st.markdown("### Link to this case")
            st.info(
                "Applicability needs human review. No coverage decision is made here."
            )
            for l in reasoning.policy_links:
                st.markdown(f"**{l.clause_title}**: {l.why_relevant}")
                if l.case_fact:
                    st.caption(f"Case fact: {l.case_fact}")
                # Day 5: pre-existing condition flag
                if l.pre_existing_related:
                    st.warning(
                        "Possible pre-existing condition. The policy start date and the waiting-period applicability need human review."
                    )
                st.caption("Applicability: NEEDS HUMAN REVIEW")
        # Day 5: does the supplied policy have a clause for each case item?
        if reasoning and reasoning.coverage_checks:
            st.markdown("### Case vs policy check")
            st.info(
                "Shows whether a matching clause exists in the supplied policy. It does not decide coverage."
            )
            for cc in reasoning.coverage_checks:
                st.markdown(f"**{cc.case_item}** → {cc.status}")
                st.caption(
                    f"Case source: {src(cc.case_source_doc, cc.case_source_page, cc.case_source_line)}"
                )
                if cc.clause_title:
                    st.write(f"Clause: {cc.clause_title}")
                    st.caption(
                        f"Policy source: {src(cc.clause_doc, cc.clause_page, cc.clause_line)}"
                    )
                if cc.note:
                    st.write(cc.note)

# ---- Missing evidence ----
with t_missing:
    st.subheader("Missing evidence")
    if not result:
        st.write("Nothing yet.")
    elif result["reason_error"]:
        st.error(result["reason_error"])
    elif not reasoning.missing_evidence:
        st.write(
            "No referenced or requested documents are missing from the uploaded package."
        )
    else:
        for m in reasoning.missing_evidence:
            st.markdown(f"**{m.item}**")
            st.write(m.why_needed)
            st.caption(f"Referenced in: {src(m.referenced_in_doc, m.page, m.line)}")

# ---- Contradictions ----
with t_contra:
    st.subheader("Contradictions / gaps")
    if not result:
        st.write("Nothing yet.")
    elif result["reason_error"]:
        st.error(result["reason_error"])
    elif not reasoning.contradictions:
        st.write("No meaningful contradictions found across the uploaded documents.")
    else:
        st.info(
            "The system does not decide which document is correct. Human review needed."
        )
        for c in reasoning.contradictions:
            st.markdown(f"### {c.topic}")
            st.markdown(f"**A:** {c.statement_a}")
            st.caption(f"Source: {src(c.doc_a, c.page_a, c.line_a)}")
            st.markdown(f"**B:** {c.statement_b}")
            st.caption(f"Source: {src(c.doc_b, c.page_b, c.line_b)}")
            if c.note:
                st.write(c.note)

# ---- Query / rejection ----
with t_query:
    st.subheader("Query / rejection intelligence")
    if not result:
        st.write("Nothing yet.")
    elif result["reason_error"]:
        st.error(result["reason_error"])
    elif not any(d.doc_type == DocType.INSURER_LETTER for d in result["docs"]):
        st.info("No insurer query / rejection letter uploaded.")
    elif not reasoning.query_items:
        st.write(
            "Letter uploaded, but no stated reason was identified. NEEDS HUMAN REVIEW."
        )
    else:
        st.info(
            "This explains the insurer's stated reason only. It does not judge whether the insurer is right."
        )
        for q in reasoning.query_items:
            st.markdown(f"### {q.stated_reason}")
            st.caption(f"Stated in: {src(q.letter_doc, q.letter_page, q.letter_line)}")
            st.markdown(f"**Connected evidence / gap:** {q.linked_evidence}")
            if q.linked_doc:
                st.caption(f"Source: {src(q.linked_doc, q.linked_page, q.linked_line)}")
            if q.note:
                st.write(q.note)

# ---- Next actions ----
with t_actions:
    st.subheader("Next actions")
    if not result:
        st.write("Nothing yet.")
    elif result["reason_error"]:
        st.error(result["reason_error"])
    elif not reasoning.next_actions:
        st.write("No actions suggested. NEEDS HUMAN REVIEW.")
    else:
        st.info("Suggestions for the advisor. No claim decision is made here.")
        for i, a in enumerate(reasoning.next_actions, 1):
            st.markdown(f"**{i}. {a.action}**")
            st.write(a.reason)
            if a.source_doc:
                st.caption(f"Source: {src(a.source_doc, a.source_page, a.source_line)}")

# ---- Token usage (Day 5: new) ----
if result and result.get("usage"):
    with st.expander("Token usage this run (estimated, about 4 characters per token)"):
        usage = result["usage"]
        st.dataframe(usage)
        st.caption(
            f"Total: about {sum(u['input_tokens'] for u in usage):,} input and "
            f"{sum(u['output_tokens'] for u in usage):,} output tokens"
        )
        if any(u["input_tokens"] > TOKEN_WARN for u in usage):
            st.warning(
                "At least one prompt is very large. It may hit token limits and fail."
            )
