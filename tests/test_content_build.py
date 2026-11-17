"""The words layer (tools/content_build.py) and the resume PDF's source (tools/resume_pdf.py), on the real content/.

    python -m pytest tests -q        (no Quarto, no network; the PDF itself is not compiled here)
"""
import copy
import datetime
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import content_build as cb  # noqa: E402
import resume_pdf  # noqa: E402


def test_todays_words_rebuild_todays_pages_byte_for_byte():
    assert cb.differs(cb.build(cb.load())) == []


def test_typed_words_are_escaped_never_markup():
    c = cb.load()
    c["resume"]["summary"] = 'I <script>alert(1)</script> & "you"'
    out = cb.build(c)["resume.qmd"]
    assert "<script>alert" not in out and "I &lt;script&gt;alert(1)&lt;/script&gt; &amp; \"you\"" in out


def test_a_note_turns_dashes_into_bullets_and_stars_into_bold():
    html = cb.note_html("First line.\n\n- **One** thing\n- Two")
    assert html == "  <p>First line.</p>\n  <ul>\n    <li><b>One</b> thing</li>\n    <li>Two</li>\n  </ul>"


def test_contact_details_are_caught_by_harden_docs_rules():
    c = cb.load()
    c["about"]["lede"] = "Call 954-555-0100 or write to someone@example.com"
    found = {what for _, _, what, _ in cb.check_private(c)}
    assert {"a phone number", "an email address"} <= found


def test_an_added_project_gets_a_tile_a_panel_and_counts_itself():
    c = cb.load()
    c["projects"]["projects"].append({**copy.deepcopy(cb.NEW["project"]), "id": "budget", "name": "Budget planner",
                                      "status": "Live", "notes": [{**cb.NEW["note"], "id": "budget-notes", "title": "T", "body": "B"}]})
    assert cb.validate(c) == []
    out = cb.build(c)["projects.qmd"]
    assert 'data-item="budget"' in out and out.count('data-item="budget"') == 2 and 'id="n-budget-notes"' in out
    assert "<li>4 projects</li>" in out
    assert "<!-- netflix:panel --><article" in out      # the Netflix tool's regions are kept as it wrote them


def test_duplicate_ids_and_a_picture_without_words_are_refused():
    c = cb.load()
    c["projects"]["projects"].append(copy.deepcopy(c["projects"]["projects"][0]))
    assert any("share" in p for p in cb.validate(c))
    c = cb.load()
    c["projects"]["projects"][0]["picture"]["alt"] = ""
    assert any("description" in p for p in cb.validate(c))


def test_a_timeline_row_keeps_its_bar_until_its_dates_change():
    row = {"from": "2018-03", "to": "2026-07", "left": "41.1", "width": "55.9"}
    assert cb.bar(row) == ("41.1", "55.9")
    assert cb.bar({"from": "2018-01", "to": "2021-01"}) == ("40.0", "20.0")


def test_the_pdf_source_is_the_resumes_words_with_a_date_and_no_contact_line():
    r = cb.load()["resume"]
    src = resume_pdf.typst_source(r, "Richard Chute", made=datetime.date(2026, 11, 17))
    assert "Updated November 2026" in src and "Operations leader turned data engineer" in src
    assert "author" not in src and "@" not in src.replace("\\@", "")
