"""The resume as a PDF, built from the same words as the resume page (content/resume.json; SportsAnalytics #788).

    python tools/resume_pdf.py            write assets/resume.pdf when content/resume.json offers one, else remove it
    python tools/resume_pdf.py --out X    write the PDF to X whatever the setting (the editor's preview)

Typst lays it out; it ships inside Quarto (quarto typst compile), so nothing new is installed. The PDF carries the
words of the page and nothing else: no contact details (the site has none by design, and tools/harden_docs.py fails
the build on any), and no author in its metadata, only its title. Its words are checked before it is made
(tools/content_build.py check_private, the same rules as tools/harden_docs.py); harden_docs.py then checks the PDF's
origin and metadata, since a PDF's text cannot be scanned reliably. Its footer says when it was made.
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "resume.pdf"


def quarto():
    """Quarto's own executable: the owner's install first, then PATH."""
    local = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Quarto" / "bin" / "quarto.exe"
    return str(local) if local.exists() else (shutil.which("quarto") or "quarto")


def esc(s):
    """Plain words as Typst markup: every character Typst treats as markup is escaped, then **x** becomes bold."""
    s = re.sub(r'([\\#$*_`<>@\[\]~"/=+-])', r"\\\1", str(s or ""))
    return re.sub(r"\\\*\\\*(.+?)\\\*\\\*", r"*\1*", s)


def lines(body):
    """A note's text as (paragraphs, bullets) in reading order: [("p", text) or ("li", text)]."""
    out = []
    for chunk in re.split(r"\n\s*\n", str(body or "").strip()):
        rows = [x.strip() for x in chunk.splitlines() if x.strip()]
        if rows and all(x.startswith("- ") for x in rows):
            out += [("li", x[2:].strip()) for x in rows]
        elif rows:
            out.append(("p", " ".join(rows)))
    return out


def typst_source(r, name="Richard Chute", made=None):
    made = made or datetime.date.today()
    t = ['#set document(title: "' + esc(r.get("page", {}).get("title") or "Resume") + '")',
         '#set page(paper: "us-letter", margin: (x: 0.7in, y: 0.6in), footer: align(right)[#text(size: 8.5pt, fill: rgb("#5A6680"))['
         + esc(f"Updated {made.strftime('%B')} {made.year}") + ']])',
         '#set text(font: ("Segoe UI", "Arial", "Liberation Sans"), size: 10.5pt, fill: rgb("#1B2333"))',
         '#set par(justify: false, leading: 0.55em)',
         '#show heading.where(level: 2): it => block(above: 1.1em, below: 0.5em)[#text(size: 11pt, weight: "bold", '
         'fill: rgb("#0E6E7A"), tracking: 0.08em)[#upper(it.body)] #v(-0.6em) #line(length: 100%, stroke: 0.6pt + rgb("#9FD9E0"))]',
         f'#text(size: 22pt, weight: "bold")[{esc(name)}]',
         f'#v(-0.4em) #text(size: 13pt, fill: rgb("#3A4660"))[{esc(r.get("headline"))}]',
         f'#v(-0.3em) #text(size: 10pt, fill: rgb("#5A6680"))[{esc(r.get("eyebrow"))}]']
    if (r.get("summary") or "").strip():
        t.append(f"#v(0.4em)\n{esc(r['summary'])}")
    t.append(f"== {esc(r.get('skills_title') or 'Skills')}")
    t.append("#grid(columns: (1.3in, 1fr), row-gutter: 0.45em, " + ", ".join(
        f'text(weight: "bold")[{esc(s.get("k"))}], [{esc(", ".join(s.get("items") or []))}]' for s in r.get("skills", [])) + ")")
    t.append("== Experience")
    for role in r.get("roles", []):
        t.append(f'#block(above: 0.9em, below: 0.3em)[#text(weight: "bold", size: 11pt)[{esc(role.get("role"))}, '
                 f'{esc(role.get("name"))}] #h(1fr) #text(fill: rgb("#5A6680"))[{esc(role.get("when"))}]]')
        wins = [f"{esc(s.get('n'))} {esc(s.get('l'))}" for s in role.get("stats", [])]
        if wins:
            t.append('#text(fill: rgb("#3A4660"))[' + "; ".join(wins) + "]")
        for kind, s in lines(role.get("details")):
            t.append(f"- {esc(s)}" if kind == "li" else f"\n{esc(s)}\n")
    tr = r.get("training") or {}
    if tr.get("items"):
        t.append(f"== {esc(tr.get('title') or 'Training')}")
        t += [f"- {esc(x)}" for x in tr["items"]]
    return "\n".join(t) + "\n"


def compile_pdf(r, out, name="Richard Chute"):
    """Write the PDF; returns (ok, message)."""
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        src = pathlib.Path(d) / "resume.typ"
        src.write_text(typst_source(r, name), encoding="utf-8")
        tmp = pathlib.Path(d) / "resume.pdf"
        try:
            p = subprocess.run([quarto(), "typst", "compile", str(src), str(tmp)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=180)
        except (OSError, subprocess.TimeoutExpired) as e:
            return False, f"Typst could not run: {e}"
        if p.returncode != 0 or not tmp.exists():
            return False, "Typst could not lay out the resume: " + (p.stderr or p.stdout).strip()[-400:]
        shutil.copyfile(tmp, out)
    return True, f"wrote {out.name}"


def site_name(root=ROOT):
    try:
        return json.loads((root / "content" / "home.json").read_text(encoding="utf-8")).get("name") or "Richard Chute"
    except (OSError, ValueError):
        return "Richard Chute"


def main(resume=None, root=ROOT):
    """Make assets/resume.pdf match the setting: built when the resume offers it, removed when it does not."""
    r = resume if resume is not None else json.loads((root / "content" / "resume.json").read_text(encoding="utf-8"))
    out = root / "assets" / "resume.pdf"
    if not (r.get("pdf") or {}).get("offer"):
        if out.exists():
            out.unlink()
            return "resume_pdf: removed assets/resume.pdf (the resume no longer offers a PDF)"
        return "resume_pdf: no PDF offered"
    ok, msg = compile_pdf(r, out, site_name(root))
    if not ok:
        raise SystemExit("resume_pdf: " + msg)
    return "resume_pdf: " + msg


if __name__ == "__main__":
    if "--out" in sys.argv:
        r = json.loads((ROOT / "content" / "resume.json").read_text(encoding="utf-8"))
        ok, msg = compile_pdf(r, sys.argv[sys.argv.index("--out") + 1], site_name())
        print(msg)
        sys.exit(0 if ok else 1)
    print(main())
