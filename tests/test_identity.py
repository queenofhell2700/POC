from analyze import Doc, check_identity_consistency
from schema import DocType

CASE = """CITY CARE HOSPITAL - ADMISSION CASE SHEET
Patient: Ravi Kumar
Date of admission: 12-09-2026
Insurer: Bajaj General Insurance Limited
Policy number: POL-123456
"""
PREAUTH = """PRE-AUTHORIZATION REQUEST FORM
Patient Name: Ravi Kumar
Insurer: Star Demo Insurance
Policy Number: SDI-100245
"""
POLICY = """STAR DEMO INSURANCE - HEALTH POLICY TERMS
Policy Number: SDI-100245
"""


def mk(name, text, t):
    return Doc(name, pages=[(1, text)], doc_type=t)


def test_sample_package_flags_insurer_and_policy_mismatch():
    docs = [
        mk("case.txt", CASE, DocType.CASE_SHEET),
        mk("preauth.txt", PREAUTH, DocType.PRE_AUTH),
        mk("policy.txt", POLICY, DocType.POLICY),
    ]
    conflicts = {c.field: c for c in check_identity_consistency(docs)}
    assert set(conflicts) == {"insurer", "policy_number"}  # patient matches
    pol = {(v.source_doc, v.value) for v in conflicts["policy_number"].values}
    assert ("case.txt", "POL-123456") in pol
    assert ("preauth.txt", "SDI-100245") in pol


def test_formatting_differences_are_not_conflicts():
    a = mk(
        "a.txt",
        "Policy Number: SDI-100245\nInsurer: Star Demo Insurance\n",
        DocType.PRE_AUTH,
    )
    b = mk(
        "b.txt",
        "Policy No: sdi 100245\nInsurer: Star Demo Insurance Ltd.\n",
        DocType.POLICY,
    )
    assert check_identity_consistency([a, b]) == []
