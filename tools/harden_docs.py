"""Post-render hardening for the static site in docs/ (run by Quarto after every render; see _quarto.yml).

GitHub Pages serves files only and cannot send response headers, so this does what a static site can:
  - removes every script and stylesheet import loaded from another site (Quarto adds jQuery, RequireJS and MathJax from CDNs; no page here
    needs them), so nothing third-party runs and nothing tracks a visitor;
  - adds a Content-Security-Policy <meta> per page: scripts only from this site plus the exact inline scripts the page
    holds (by SHA-256 hash), no plugins, no forms, no outside connections but one: a listing card's cover picture
    from Airbnb's image hosts (assets/airbnb/cards.js, the owner, 2026-11-22); plus no-referrer and noai / noimageai;
  - writes robots.txt that turns away AI and scraper crawlers;
  - fails if any image under docs/ carries EXIF, XMP or GPS metadata;
  - restores docs/.nojekyll (a full render deletes it);
  - fails the build if contact details, local addresses, source files or stray artifacts are in docs/;
  - allows exactly one PDF, assets/resume.pdf, and only as tools/resume_pdf.py makes it (Typst, no author in its
    metadata). A PDF's text cannot be scanned reliably, so its words are checked before it is made: they are the
    resume's words in content/resume.json, which tools/content_build.py refuses when they hold a contact detail.
"""
import base64, hashlib, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

ROBOTS = """# AI training and scraper crawlers are not welcome. Well-behaved crawlers honour this; others are not stopped by it.
""" + "".join(f"User-agent: {a}\nDisallow: /\n\n" for a in [
    "GPTBot", "ChatGPT-User", "OAI-SearchBot", "CCBot", "Google-Extended", "GoogleOther", "ClaudeBot", "Claude-Web", "anthropic-ai",
    "PerplexityBot", "Perplexity-User", "Bytespider", "Amazonbot", "Applebot-Extended", "FacebookBot", "meta-externalagent",
    "Diffbot", "ImagesiftBot", "Omgilibot", "omgili", "cohere-ai", "cohere-training-data-crawler", "YouBot", "Timpibot",
    "AI2Bot", "PetalBot", "DataForSeoBot", "magpie-crawler", "img2dataset", "Scrapy", "MJ12bot", "AhrefsBot", "SemrushBot", "DotBot",
]) + "User-agent: *\nAllow: /\n\nSitemap: https://plotbot2023.github.io/portfolio/sitemap.xml\n"

EXTERNAL_SCRIPT = re.compile(r'<script\b[^>]*\bsrc="https?://[^"]*"[^>]*>\s*</script>\s*', re.I)
INLINE_SCRIPT = re.compile(r"<script\b(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", re.I | re.S)
FORBIDDEN = {
    "an email address": re.compile(r"[\w.+-]+@[\w-]+\.(com|net|org|io|edu|gov|us|co)\b", re.I),
    "a mailto link": re.compile(r"href\s*=\s*[\"']?mailto:|mailto:[\w.+-]+@", re.I),
    "a phone number": re.compile(r"\(?\b\d{3}\)?[ .-]\d{3}[ .-]\d{4}\b"),
    "a local address": re.compile(r"127\.0\.0\.1|localhost:\d+|\b[A-Z]:\\\\(Users|dev)\\\\", re.I),
    "a social profile link": re.compile(r"(github\.com/PlotBot2023|linkedin\.com|twitter\.com|x\.com/|substack\.com/@)", re.I),
}
STRAY = re.compile(r"\.(qmd|ipynb|py|map|ejs|scss|env|pdf)$|(^|/)(\.git|_freeze|\.quarto)(/|$)", re.I)
RESUME_PDF = "assets/resume.pdf"   # the one PDF allowed, made by tools/resume_pdf.py from the resume's own words


def resume_pdf_problems(p):
    """Why the resume PDF is not the one tools/resume_pdf.py makes, or [] when it is."""
    b = p.read_bytes()
    out = []
    if not b.startswith(b"%PDF-"):
        out.append("assets/resume.pdf is not a PDF")
    if b"/Author" in b or b"<dc:creator>" in b:
        out.append("assets/resume.pdf names an author in its metadata (tools/resume_pdf.py makes it without one)")
    if b"Typst" not in b:
        out.append("assets/resume.pdf was not made by tools/resume_pdf.py (an uploaded PDF cannot be checked for contact details)")
    return out


def csp_for(page_html):
    hashes = sorted({"'sha256-" + base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode() + "'"
                     for attrs, body in INLINE_SCRIPT.findall(page_html) if "application/json" not in attrs.lower() and "application/ld+json" not in attrs.lower()})
    # img-src: Airbnb's image hosts, for the listing cards' cover pictures (a0.muscache.com, and z1.muscache.cn for a few homes)
    return ("default-src 'self'; script-src 'self' " + " ".join(hashes) + "; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://a0.muscache.com https://z1.muscache.cn; "
            "font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'; upgrade-insecure-requests").replace("  ", " ")


def harden_page(p):
    t = p.read_text(encoding="utf-8")
    t = EXTERNAL_SCRIPT.sub("", t)
    t = re.sub(r'\s*<meta http-equiv="Content-Security-Policy"[^>]*>|\s*<meta name="(referrer|robots)"[^>]*>', "", t)
    head = (f'\n<meta http-equiv="Content-Security-Policy" content="{csp_for(t)}">'
            '\n<meta name="referrer" content="no-referrer">\n<meta name="robots" content="noai, noimageai">')
    t = t.replace('<meta charset="utf-8">', '<meta charset="utf-8">' + head, 1)
    p.write_text(t, encoding="utf-8")


def image_metadata():
    """Images carrying EXIF, XMP or GPS blocks, read from the bytes (no imaging library needed, so Quarto's own Python runs it).
    Strip any it finds with tools/notebook_thumbs.py's Pillow re-save, or re-export the image."""
    found = []
    for p in DOCS.rglob("*"):
        if p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            continue
        b = p.read_bytes()
        if b"Exif" + bytes(2) in b or b"eXIf" in b[:4096 * 16] or b"EXIF" in b[:64] or b"<x:xmpmeta" in b or b"GPSInfo" in b:
            found.append(p.relative_to(DOCS).as_posix())
    return found


def audit():
    problems = []
    for p in DOCS.rglob("*"):
        rel = p.relative_to(DOCS).as_posix()
        if p.is_file() and rel == RESUME_PDF:
            problems += resume_pdf_problems(p)
        elif p.is_file() and STRAY.search(rel):
            problems.append(f"stray file published: {rel}")
        if p.is_file() and p.suffix.lower() in (".html", ".json", ".xml", ".txt", ".js", ".css"):
            t = p.read_text(encoding="utf-8", errors="ignore")
            for what, rx in FORBIDDEN.items():
                m = rx.search(t)
                if m and not (what == "a phone number" and p.suffix == ".js"):
                    problems.append(f"{what} in {rel}: {m.group(0)[:40]}")
            if p.suffix == ".html" and re.search(r'<script\b[^>]*\bsrc="https?://', t):
                problems.append(f"an outside script in {rel}")
    return problems


# @import "https://...";  @import url(https://...);  @import url('https://...') screen;  (a font URL can hold semicolons)
OUTSIDE_IMPORT = re.compile(r"""@import\s*(?:url\(\s*)?(?:"https?://[^"]*"|'https?://[^']*'|https?://[^)\s]*)\s*\)?[^;{]*;""", re.I)


def main():
    for p in DOCS.rglob("*.html"):
        harden_page(p)
    # the Darkly theme imports Lato from Google Fonts; the site uses system fonts, so no visitor request leaves the site
    for p in DOCS.rglob("*.css"):
        t = p.read_text(encoding="utf-8")
        if OUTSIDE_IMPORT.search(t):
            p.write_text(OUTSIDE_IMPORT.sub("", t), encoding="utf-8")
    # Quarto's page script asks for listings.json; with no listing on the site, an empty one saves a 404
    if not (DOCS / "listings.json").exists():
        (DOCS / "listings.json").write_text("[]", encoding="utf-8")
    (DOCS / "robots.txt").write_text(ROBOTS, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    problems = audit() + [f"image metadata in {f}" for f in image_metadata()]
    if problems:
        print("harden_docs: NOT SAFE TO PUBLISH", *sorted(set(problems)), sep="\n  ")
        sys.exit(1)
    print("harden_docs: outside scripts removed, CSP set on every page, robots.txt written, no image metadata, nothing private found")


if __name__ == "__main__":
    main()
