"""Copy the Hot Wheels Value Field Guide into the site as guides/hot-wheels-field-guide.html, ready for harden_docs.py.

    python tools/hotwheels_guide.py --src <the guide's saved page, hot_wheels_field_guide.html>

The guide is a self-contained page (its own styles, one inline script, every drawing inline). This copy:
  - drops the Google Fonts links, so no visitor request leaves the site (the page falls back to system fonts);
  - writes the charset as <meta charset="utf-8">, which is where harden_docs.py inserts the page's Content-Security-Policy;
  - adds one link back to the portfolio's Projects page.
The source folder's location is never written into the output. Rerun after the guide changes.
"""
import argparse, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "guides" / "hot-wheels-field-guide.html"
FONT_LINK = re.compile(r'\s*<link\b[^>]*\bhref="https?://fonts\.(googleapis|gstatic)\.com[^"]*"[^>]*>', re.I)
CHARSET = re.compile(r'<meta\s+charset=["\']?utf-?8["\']?\s*/?>', re.I)
BACK = ('<a href="../projects.html" style="display:inline-flex;align-items:center;min-height:44px;margin:12px 16px 0;padding:0 18px;'
        'border-radius:999px;border:1.5px solid #8fd3ff;background:#0f1630;color:#eef1fb;font:700 16px system-ui,sans-serif;'
        'text-decoration:none">Back to the portfolio</a>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=pathlib.Path)
    t = ap.parse_args().src.read_text(encoding="utf-8")
    t, n_fonts = FONT_LINK.subn("", t)
    t, n_charset = CHARSET.subn('<meta charset="utf-8">', t, count=1)
    if n_charset != 1:
        raise SystemExit("no charset tag found: harden_docs.py could not add the page's Content-Security-Policy")
    t, n_body = re.subn(r"(<body\b[^>]*>)", r"\1" + BACK, t, count=1, flags=re.I)
    if n_body != 1:
        raise SystemExit("no <body> tag found")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(t, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}: {n_fonts} font links removed, {len(t):,} characters")


if __name__ == "__main__":
    main()
