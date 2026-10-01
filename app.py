import streamlit as st
from extract import extract_pdf_pages, extract_text_file

st.set_page_config(page_title="Claim POC", layout="wide")

st.title("Health Claim Readiness & Rejection Intelligence")
st.caption(
    "POC • Synthetic / de-identified documents only • AI never approves or rejects a claim"
)

# ---- Upload area ----
uploaded_files = st.file_uploader(
    "Upload claim documents (case sheet, policy, pre-auth, prior reports, insurer letter)",
    type=["pdf", "jpg", "jpeg", "png", "txt"],
    accept_multiple_files=True,
)


if uploaded_files:
    st.success(f"{len(uploaded_files)} file(s) uploaded")
    for f in uploaded_files:
        st.write(f"• {f.name}  ({f.size / 1024:.1f} KB)")

analyze = st.button("Analyze claim", type="primary", disabled=not uploaded_files)

# if analyse block replaced
if analyze:
    for f in uploaded_files:
        st.subheader(f.name)
        data = f.getvalue()
        if f.name.lower().endswith(".pdf"):
            pages = extract_pdf_pages(data)
        elif f.name.lower().endswith(".txt"):
            pages = extract_text_file(data)
        else:
            st.write("Image file: will be sent to the AI model later.")
            continue
        for page_num, text in pages:
            with st.expander(f"Page {page_num}"):
                st.text(text if text.strip() else "(no text found on this page)")

# ---- Placeholder result sections ----
tabs = st.tabs(
    [
        "Timeline",
        "Current admission",
        "Policy checks",
        "Missing evidence",
        "Contradictions",
        "Query / rejection",
        "Next actions",
    ]
)

names = [
    "Medical & claim timeline",
    "Current admission summary",
    "Policy / claim checks",
    "Missing evidence",
    "Contradictions / gaps",
    "Query / rejection intelligence",
    "Next actions",
]

for tab, name in zip(tabs, names):
    with tab:
        st.subheader(name)
        st.write("Nothing yet. This will fill in after analysis.")
