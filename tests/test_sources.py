from analyze import Doc, verify_source
from schema import DocType

TXT = "Patient: Ravi Kumar\nInsurer: Star Demo Insurance\nPolicy Number: SDI-100245\n"


def docs():
    return [
        Doc("case.txt", pages=[(1, TXT)], doc_type=DocType.CASE_SHEET),
        Doc(
            "report.pdf",
            pages=[(1, "a\nb"), (2, "c\nd\ne")],
            doc_type=DocType.PRIOR_REPORT,
        ),
        Doc("scan.png", image_bytes=b"x", mime="image/png"),
    ]


def test_valid_sources_pass():
    d = docs()
    assert verify_source(d, "case.txt", 1, "L3") is None
    assert verify_source(d, "case.txt", 1, "3") is None
    assert verify_source(d, "report.pdf", 2, "L1-L3") is None
    assert verify_source(d, "case.txt") is None  # file-level only
    assert verify_source(d, "case.txt", None, "L2") is None  # single page doc


def test_fabricated_file_rejected():
    assert verify_source(docs(), "fake_report.pdf", 1, "L1")


def test_page_99_rejected():
    assert verify_source(docs(), "case.txt", 99, "L1")


def test_nonexistent_line_rejected():
    d = docs()
    assert verify_source(d, "case.txt", 1, "L99")
    assert verify_source(d, "report.pdf", 1, "L3")  # page 1 has only 2 lines
    assert verify_source(d, "case.txt", 1, "banana")


def test_line_without_page_on_multipage_doc_rejected():
    assert verify_source(docs(), "report.pdf", None, "L1")


def test_image_page_only_ok_but_page_2_rejected():
    d = docs()
    assert verify_source(d, "scan.png", 1) is None
    assert verify_source(d, "scan.png", 1, "L5") is None  # no line geometry
    assert verify_source(d, "scan.png", 2) is None
