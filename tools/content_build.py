"""Build the site's pages from its words (SportsAnalytics issue #788).

The words of Home, Projects, About and Resume live in content/*.json, one file a page; the layout lives in
content/templates/*.tmpl. This tool fills the templates and writes index.qmd, projects.qmd, about.qmd, resume.qmd
and _rentals_home.qmd. Every word is HTML-escaped: the owner types words, never markup. The only formatting the owner
can use is in a note's text: a blank line starts a new paragraph, a line that starts with "- " is a bullet, and
**two stars** on each side make words bold.

    python tools/content_build.py            write the pages from content/
    python tools/content_build.py --check    fail (exit 1) if a page differs from what content/ builds; Quarto runs
                                             this before every render (_quarto.yml pre-render), so a page edited by
                                             hand is caught instead of silently overwritten
    python tools/content_build.py --pdf      also write assets/resume.pdf when the resume offers one (tools/resume_pdf.py)

The owner edits the words in the Hub's portfolio editor (SportsAnalytics observatory/portfolio_editor.py), which
imports this file from its own copy of the site: FIELDS tells it what to draw, build() makes its preview, and
check_private() refuses contact details before anything is rendered.

Pages written by other tools are not built here and the editor shows them read only: the Airbnb case study
(tools/airbnb_build.py writes _airbnb_generated.qmd and _airbnb_home.qmd), the leaderboards
(tools/leaderboards_snapshot.py), the Hot Wheels guide (tools/hotwheels_guide.py) and the notebook pages.
"""
from __future__ import annotations

import datetime as _dt
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
TEMPLATES = CONTENT / "templates"

# page key -> (content file, [(template, output file), ...])
PAGES = {
    "home": ("home.json", [("index.qmd.tmpl", "index.qmd"), ("_rentals_home.qmd.tmpl", "_rentals_home.qmd")]),
    "projects": ("projects.json", [("projects.qmd.tmpl", "projects.qmd")]),
    "about": ("about.json", [("about.qmd.tmpl", "about.qmd")]),
    "resume": ("resume.json", [("resume.qmd.tmpl", "resume.qmd")]),
}
PAGE_HTML = {"home": "index.html", "projects": "projects.html", "about": "about.html", "resume": "resume.html"}

# Pages the editor shows read only, and who writes them.
OWNED = [
    {"name": "Airbnb case study", "page": "airbnb.html", "by": "tools/airbnb_build.py",
     "why": "Its numbers, maps and words are written from the Inside Airbnb data each time it is rebuilt."},
    {"name": "Leaderboards", "page": "guides/leaderboards/nfl.html", "by": "tools/leaderboards_snapshot.py",
     "why": "A dated snapshot of the live leaderboards, built from the same code that runs them."},
    {"name": "Hot Wheels guide", "page": "guides/hot-wheels-field-guide.html", "by": "tools/hotwheels_guide.py",
     "why": "Copied in whole from the Collectibles project, where the guide is written."},
    {"name": "Netflix mood tags", "page": "projects.html", "by": "tools/netflix_build.py",
     "why": "Its tile, panel and note on the Projects page are written from the mood-tag results each time they are rebuilt."},
    {"name": "Notebooks", "page": "notebooks/broward-market-analysis.html", "by": "the notebooks themselves",
     "why": "Each notebook page is its saved charts and write-up, published as it was last run."},
]

# ── icons: line drawings on a 24 grid; a new project or role picks one by name ─────────────────────────────────────
ICONS = {
    "chart": ("Chart", '<path d="M4 20V11M10 20V5M16 20v-6M22 20H2"/><path d="M19 4l1.2 2.4 2.6.4-1.9 1.8.5 2.6L19 10l-2.4 1.2.5-2.6-1.9-1.8 2.6-.4z"/>'),
    "car": ("Car", '<path d="M3 15v-3l2-4h9l4 4h3v3z"/><circle cx="7.5" cy="16" r="2"/><circle cx="17" cy="16" r="2"/>'),
    "screen": ("Screen", '<rect x="3" y="5" width="18" height="12" rx="2"/><path d="M8 21h8M12 17v4"/><path d="M10 9l4 2-4 2z"/>'),
    "case": ("Briefcase", '<path d="M4 7h16v12H4z"/><path d="M9 7V5h6v2"/><path d="M4 12h16"/>'),
    "waves": ("Waves", '<path d="M3 15c2 0 2-1.5 4.5-1.5S10 15 12 15s2-1.5 4.5-1.5S19 15 21 15"/><path d="M3 19c2 0 2-1.5 4.5-1.5S10 19 12 19s2-1.5 4.5-1.5S19 19 21 19"/><path d="M8 11V5a2 2 0 0 1 4 0M12 11V5a2 2 0 0 1 4 0"/>'),
    "building": ("Building", '<path d="M3 9l9-5 9 5v11H3z"/><path d="M7 20v-6h10v6"/><path d="M7 17h10"/>'),
    "database": ("Database", '<ellipse cx="12" cy="5.5" rx="7" ry="2.5"/><path d="M5 5.5v13c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-13M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5"/>'),
    "tag": ("Tag", '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8" r="1.5"/>'),
    "gauge": ("Gauge", '<path d="M4 17a8 8 0 1 1 16 0"/><path d="M12 17l4-5"/><path d="M3 20h18"/>'),
    "map": ("Map", '<path d="M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2z"/><path d="M9 4v14M15 6v14"/>'),
    "people": ("People", '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="17" cy="9" r="2.5"/><path d="M15.5 14.2c3 .2 5.5 2.6 5.5 5.8"/>'),
    "network": ("Network", '<circle cx="5" cy="6" r="2.2"/><circle cx="5" cy="18" r="2.2"/><circle cx="12" cy="12" r="2.2"/><circle cx="19" cy="7" r="2.2"/><circle cx="19" cy="17" r="2.2"/><path d="M7 7l3 3.5M7 17l3-3.5M14 11l3-3M14 13l3 3"/>'),
    "trend": ("Trend", '<path d="M4 20V4M4 20h16"/><path d="M7 15l4-4 3 3 5-6"/>'),
    "flask": ("Flask", '<path d="M9 3h6M10 3v6L4 19a1.5 1.5 0 0 0 1.3 2h13.4A1.5 1.5 0 0 0 20 19l-6-10V3"/><path d="M7 15h10"/>'),
}
HUES = {"": "Cyan", "or": "Gold", "vi": "Blue", "pk": "Pink"}            # a resume tile's icon colour
BAR_HUES = {"cy": "Cyan", "or": "Gold", "vi": "Blue", "pk": "Pink"}    # an About timeline bar
SVG_OPEN = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="{w}" stroke-linecap="round" '
            'stroke-linejoin="round" aria-hidden="true" focusable="false">')

# the leaderboards poster: four drawn bars against a baseline, no data, so no alt text
SCORELINE = """<div class="media inlay poster scoreline" aria-hidden="true">
          <div class="sl-row"><span class="sl-k">Team A</span><span class="sl-bar"><span style="width:78%"></span></span><span class="sl-chip hot">Elite</span></div>
          <div class="sl-row"><span class="sl-k">Team B</span><span class="sl-bar"><span style="width:56%"></span></span><span class="sl-chip warm">Good</span></div>
          <div class="sl-row"><span class="sl-k">Baseline</span><span class="sl-bar base"><span style="width:44%"></span></span><span class="sl-chip">Average</span></div>
          <div class="sl-row"><span class="sl-k">Team C</span><span class="sl-bar"><span style="width:24%"></span></span><span class="sl-chip cold">Poor</span></div>
        </div>"""

# ── what the editor draws: a page -> tabs -> fields; paths are dotted keys into the page's content ────────────────
# kinds: line, big, text (one paragraph), note (paragraphs, "- " bullets, **bold**), chips (a list of short words),
# stats (big number + what it means), toggle, choice, image, list (a list of entries with their own fields)
PAGE_INFO = [
    {"key": "page.title", "label": "Browser tab title", "kind": "line", "hint": "shown on the browser tab and in search results"},
    {"key": "page.description", "label": "Search description", "kind": "line", "hint": "the line search engines show under the title"},
]
NOTE = [{"key": "title", "label": "Note title", "kind": "line"},
        {"key": "body", "label": "Note text", "kind": "note"}]
FIELDS = {
    "home": {"label": "Home", "hue": "cy", "tabs": [
        {"label": "Top", "fields": [
            {"key": "eyebrow", "label": "Small line above your name", "kind": "line"},
            {"key": "name", "label": "Your name", "kind": "big"},
            {"key": "lede", "label": "One line under your name", "kind": "text", "grow": True},
            *PAGE_INFO]},
        {"label": "Numbers", "fields": [
            {"key": "stats", "label": "At a glance", "kind": "stats", "max": 4, "hint": "the big number, then what it means"},
            {"key": "tools", "label": "Tools and methods", "kind": "chips"}]},
        {"label": "How I work", "fields": [
            {"key": "ways", "label": "How I work", "kind": "list", "fixed": True, "name": "label", "fields": [
                {"key": "label", "label": "Button words", "kind": "line"}, *NOTE]}]},
        {"label": "Selected work", "fields": [
            {"key": "work_title", "label": "Section title", "kind": "line"},
            {"key": "rentals.title", "label": "Rentals card title", "kind": "line"},
            {"key": "rentals.as_of", "label": "Rentals card date", "kind": "line", "hint": "for example: As of 9 November 2026"},
            {"key": "rentals.stats", "label": "Rentals card numbers", "kind": "stats", "max": 3},
            {"key": "leaders_title", "label": "Leaderboards card title", "kind": "line"},
            {"key": "hotwheels_title", "label": "Hot Wheels card title", "kind": "line"}]},
    ]},
    "projects": {"label": "Projects", "hue": "gold", "tabs": [
        {"label": "Top", "fields": [
            {"key": "eyebrow", "label": "Small line above the title", "kind": "line"},
            {"key": "title", "label": "Page title", "kind": "big"},
            *PAGE_INFO]},
        {"label": "Projects", "fields": [
            {"key": "projects", "label": "Projects", "kind": "list", "name": "name", "add": "Add a project", "item": "project",
             "fields": [
                 {"group": "Card", "key": "name", "label": "Project name", "kind": "line"},
                 {"group": "Card", "key": "status", "label": "Status", "kind": "choice", "options": ["Live", "Coming next"]},
                 {"group": "Card", "key": "icon", "label": "Icon", "kind": "choice", "options": list(ICONS), "labels": {k: v[0] for k, v in ICONS.items()}},
                 {"group": "Card", "key": "picture", "label": "Picture", "kind": "image", "hint": "your own image, or leave it on the icon"},
                 {"group": "Numbers", "key": "stats", "label": "Headline numbers", "kind": "stats", "max": 3},
                 {"group": "Numbers", "key": "methods", "label": "Methods", "kind": "chips"},
                 {"group": "Button", "key": "link.label", "label": "Main button words", "kind": "line"},
                 {"group": "Button", "key": "link.href", "label": "Main button opens", "kind": "line", "hint": "a web address, or a page on this site"},
                 {"group": "Notes", "key": "notes", "label": "Notes", "kind": "list", "name": "button", "add": "Add a note", "item": "note", "fields": [
                     {"key": "button", "label": "Button words", "kind": "line"}, *NOTE]}]}]},
    ]},
    "about": {"label": "About", "hue": "pk", "tabs": [
        {"label": "Top", "fields": [
            {"key": "eyebrow", "label": "Small line above the title", "kind": "line"},
            {"key": "title", "label": "Page title", "kind": "big"},
            {"key": "lede", "label": "One line under the title", "kind": "text", "grow": True},
            *PAGE_INFO]},
        {"label": "Notes", "fields": [
            {"key": "notes", "label": "The two notes at the top", "kind": "list", "fixed": True, "name": "button", "fields": [
                {"key": "button", "label": "Button words", "kind": "line"}, *NOTE]}]},
        {"label": "Career", "fields": [
            {"key": "career_title", "label": "Timeline title", "kind": "line"},
            {"key": "career", "label": "Timeline rows", "kind": "list", "name": "name", "add": "Add a row", "item": "row", "fields": [
                {"key": "name", "label": "Where", "kind": "line"},
                {"key": "sub", "label": "Small line under it", "kind": "line"},
                {"key": "from", "label": "From", "kind": "line", "hint": "year and month, for example 2018-03", "bar": True},
                {"key": "to", "label": "To", "kind": "line", "hint": "year and month, or now", "bar": True},
                {"key": "hue", "label": "Bar colour", "kind": "choice", "options": list(BAR_HUES), "labels": BAR_HUES}]}]},
        {"label": "Results", "fields": [
            {"key": "results.title", "label": "Section title", "kind": "line"},
            {"key": "results.button", "label": "Note button words", "kind": "line"},
            {"key": "results.stats", "label": "Results", "kind": "stats", "max": 4},
            {"key": "results.note.title", "label": "Note title", "kind": "line"},
            {"key": "results.note.body", "label": "Note text", "kind": "note"}]},
        {"label": "Skills", "fields": [
            {"key": "skills", "label": "The two skill panels", "kind": "list", "fixed": True, "name": "title", "fields": [
                {"key": "title", "label": "Panel title", "kind": "line"},
                {"key": "tools", "label": "Tools", "kind": "chips"},
                {"key": "note_title", "label": "Note title", "kind": "line"},
                {"key": "body", "label": "Note text", "kind": "note"}]}]},
        {"label": "Looking for", "fields": [
            {"key": "seek.title", "label": "Section title", "kind": "line"},
            {"key": "seek.items", "label": "Roles and places", "kind": "chips"}]},
    ]},
    "resume": {"label": "Resume", "hue": "gr", "tabs": [
        {"label": "Top", "fields": [
            {"key": "eyebrow", "label": "Small line above the headline", "kind": "line"},
            {"key": "headline", "label": "Headline", "kind": "big"},
            {"key": "summary", "label": "Summary", "kind": "text", "grow": True, "hint": "in your own voice; empty hides it", "count": True},
            *PAGE_INFO]},
        {"label": "Skills", "fields": [
            {"key": "skills_title", "label": "Section title", "kind": "line"},
            {"key": "skills", "label": "Skill rows", "kind": "list", "name": "k", "add": "Add a row", "item": "row", "fields": [
                {"key": "k", "label": "Row name", "kind": "line"},
                {"key": "items", "label": "Skills", "kind": "chips"}]}]},
        {"label": "Experience", "fields": [
            {"key": "roles", "label": "Roles, newest first", "kind": "list", "name": "name", "add": "Add a role", "item": "role", "fields": [
                {"group": "Card", "key": "name", "label": "Where", "kind": "line"},
                {"group": "Card", "key": "sub", "label": "Tile line", "kind": "line", "hint": "short, under the name on the tile"},
                {"group": "Card", "key": "role", "label": "Role", "kind": "line"},
                {"group": "Card", "key": "when", "label": "When", "kind": "line"},
                {"group": "Numbers", "key": "stats", "label": "Headline numbers", "kind": "stats", "max": 4},
                {"group": "Numbers", "key": "tray_label", "label": "Chip row name", "kind": "line", "hint": "read aloud, for example Stack or Built"},
                {"group": "Numbers", "key": "tray", "label": "Chips", "kind": "chips"},
                {"group": "Details", "key": "details", "label": "Details", "kind": "note", "hint": "start a line with - for a bullet"}]}]},
        {"label": "Training", "fields": [
            {"key": "training.title", "label": "Note title", "kind": "line"},
            {"key": "training.items", "label": "Courses and certificates", "kind": "chips"}]},
        {"label": "PDF", "fields": [
            {"key": "pdf.offer", "label": "Offer a PDF of this resume", "kind": "toggle",
             "hint": "built from these same words, with no contact details, as a Download as PDF button on the page"}]},
    ]},
}


def site_hues(root=None):
    """The site's own identity hues (styles.css :root), so the editor's colour swatches show what the page paints."""
    root = pathlib.Path(root or ROOT)
    try:
        css = (root / "styles.css").read_text(encoding="utf-8")
    except OSError:
        return {}
    return {k: v for k, v in re.findall(r"--(cy|or|vi|pk):\s*(#[0-9A-Fa-f]{6})", css.split("}", 1)[0])}


# what a new entry starts with, by the list's "item" word; the editor gives each an id of its own
NEW = {
    "project": {"name": "New project", "status": "Coming next", "icon": "chart", "picture": {"kind": "icon"}, "stats": [],
                "methods_label": "Methods", "methods": [], "link": {"label": "", "href": ""}, "notes": []},
    "note": {"button": "Notes", "title": "", "body": "", "links": []},
    "role": {"mark": "icon", "icon": "case", "hue": "", "name": "New role", "sub": "", "role": "", "when": "", "stats": [],
             "tray_label": "Built", "tray": [], "details": ""},
    "row": {"k": "New row", "items": [], "name": "", "sub": "", "from": "", "to": "now", "hue": "cy"},
}


# ── a small template engine: {{key}}, {{key|filter|filter:arg}}, {{#list}}..{{/list}}, {{^key}}..{{/key}} ──────────────
TOKEN = re.compile(r"\{\{(?!<)([#^/]?)\s*([^}]+?)\s*\}\}")   # {{< ... >}} is a Quarto shortcode: left as it is


def _lookup(stack, name):
    if name == ".":
        return stack[-1]
    head, *rest = name.split(".")
    for ctx in reversed(stack):
        if isinstance(ctx, dict) and head in ctx:
            v = ctx[head]
            for part in rest:
                if isinstance(v, list) and part.isdigit():
                    v = v[int(part)] if int(part) < len(v) else None
                else:
                    v = v.get(part) if isinstance(v, dict) else None
            return v
    return None


def lower1(s):
    s = str(s or "")
    return s[:1].lower() + s[1:]


def text(s):
    return html.escape(str("" if s is None else s), quote=False)


def bold(escaped):
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)


def note_html(body, indent="  "):
    """A note's text as HTML lines: a blank line starts a paragraph, "- " lines are bullets, **x** is bold."""
    out = []
    for chunk in re.split(r"\n\s*\n", str(body or "").strip()):
        lines = [x.strip() for x in chunk.splitlines() if x.strip()]
        if not lines:
            continue
        if all(x.startswith("- ") for x in lines):
            out.append(indent + "<ul>")
            out += [f"{indent}  <li>{bold(text(x[2:].strip()))}</li>" for x in lines]
            out.append(indent + "</ul>")
        else:
            out.append(f"{indent}<p>{bold(text(' '.join(lines)))}</p>")
    return "\n".join(out)


def svg(name, width):
    paths = ICONS.get(name, ICONS["case"])[1]
    return SVG_OPEN.format(w=width) + paths + "</svg>"


def _filter(v, name, args):
    if name == "attr":
        return html.escape(str(v if v is not None else ""), quote=True)
    if name == "lower1":
        return lower1(v)
    if name == "yaml":
        return str(v or "").replace("\\", "\\\\").replace('"', '\\"')
    if name == "raw":
        return str(v if v is not None else "")
    if name == "note":
        return note_html(v)
    if name == "svg":
        return svg(v, args[0] if args else "1.8")
    if name == "lis":                       # <li>x</li><li>y</li>, a new line every N items
        n, ind = int(args[0]), " " * int(args[1])
        items = [f"<li>{text(x)}</li>" for x in (v or [])]
        return ("\n" + ind).join("".join(items[i:i + n]) for i in range(0, len(items), n))
    raise ValueError(f"unknown filter {name}")


def render(tpl, ctx):
    out, pos = [], 0
    stack = [ctx]

    def walk(start, end_tag=None):
        nonlocal pos
        pos = start
        buf = []
        while True:
            m = TOKEN.search(tpl, pos)
            if not m:
                if end_tag:
                    raise ValueError(f"unclosed section {end_tag}")
                buf.append(tpl[pos:])
                pos = len(tpl)
                return "".join(buf)
            buf.append(tpl[pos:m.start()])
            sigil, body = m.group(1), m.group(2)
            pos = m.end()
            if sigil == "/":
                if body != end_tag:
                    raise ValueError(f"section {end_tag} closed by {body}")
                return "".join(buf)
            if sigil in "#^" and sigil:
                inner_start = pos
                v = _lookup(stack, body)
                # find the matching close by rendering once (skipped output when falsy)
                if sigil == "#" and isinstance(v, list):
                    end_pos = None
                    for i, item in enumerate(v):
                        stack.append({"@first": i == 0, "@last": i == len(v) - 1, "@n": i + 1})
                        stack.append(item)
                        buf.append(walk(inner_start, body))
                        end_pos = pos
                        stack.pop()
                        stack.pop()
                    if end_pos is None:
                        walk(inner_start, body)        # skip
                    continue
                truthy = bool(v)
                show = truthy if sigil == "#" else not truthy
                pushed = sigil == "#" and isinstance(v, dict)
                if pushed:
                    stack.append(v)
                rendered = walk(inner_start, body)
                if pushed:
                    stack.pop()
                if show:
                    buf.append(rendered)
                continue
            name, *filters = body.split("|")
            v = _lookup(stack, name.strip())
            done = False
            for f in filters:
                fname, *fargs = f.strip().split(":")
                v = _filter(v, fname, fargs)
                done = fname in ("attr", "raw", "note", "svg", "lis") or done
            buf.append(str(v) if done else text(v))

    out.append(walk(0))
    return "".join(out)


# ── values the templates need that are worked out from the words ──────────────────────────────────────────────────
AXIS0, AXIS_SPAN = 2012, 15          # the About timeline runs 2012 to 2027


def _year(s, today=None):
    s = str(s or "").strip().lower()
    if s in ("now", "today", ""):
        d = today or _dt.date.today()
        return d.year + (d.month - 1) / 12 + (d.day - 1) / 365
    m = re.fullmatch(r"(\d{4})(?:-(\d{1,2}))?", s)
    if not m:
        raise ValueError(s)
    return int(m.group(1)) + ((int(m.group(2)) - 1) / 12 if m.group(2) else 0)


def bar(row, today=None):
    """The timeline bar as left and width in percent of the axis. A row keeps its stored left and width until its
    dates are edited (the editor drops them then), so the published bars do not move by themselves."""
    if row.get("left") not in (None, "") and row.get("width") not in (None, ""):
        return str(row["left"]), str(row["width"])
    a, b = _year(row.get("from"), today), _year(row.get("to"), today)
    a, b = max(AXIS0, min(a, AXIS0 + AXIS_SPAN)), max(AXIS0, min(b, AXIS0 + AXIS_SPAN))
    left = (a - AXIS0) / AXIS_SPAN * 100
    width = max(1.0, (b - a) / AXIS_SPAN * 100)
    return f"{left:.1f}", f"{width:.1f}"


def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def prepare(page, c, today=None):
    """The context a page's templates read: its words plus the few values worked out from them."""
    c = json.loads(json.dumps(c))
    if page == "about":
        for row in c.get("career", []):
            row["bar_left"], row["bar_width"] = bar(row, today)
    if page == "projects":
        own = [p for p in c.get("projects", []) if not p.get("generated")]   # a tool's project counts itself (its :count region)
        live = sum(1 for p in own if p.get("status") != "Coming next")
        soon = len(own) - live
        c["rail"] = [x for x in (_plural(live, "project", "projects") if live else "",
                                 f"{soon} on the way" if soon else "") if x]
        for p in c.get("projects", []):
            p["generated"] = p.get("generated") or ""
            p["building"] = p.get("status") == "Coming next"
            p["kind"] = "building" if p["building"] else "live"
            pic = p.get("picture") or {}
            if pic.get("kind") == "image" and pic.get("src"):
                p["tile_mark"] = f'<span class="mark"><img src="{html.escape(pic["src"])}" alt=""></span>'
                p["media"] = (f'<div class="media inlay"><img src="{html.escape(pic["src"])}" '
                              f'alt="{html.escape(pic.get("alt") or "")}"></div>')
            elif pic.get("kind") == "scoreline":
                p["tile_mark"] = f'<span class="mark">{svg(p.get("icon"), "1.8")}</span>'
                p["media"] = SCORELINE
            else:
                p["tile_mark"] = f'<span class="mark">{svg(p.get("icon"), "1.8")}</span>'
                p["media"] = f'<div class="media inlay poster">{svg(p.get("icon"), "1.4")}</div>'
            p["has_stats"] = bool(p.get("stats"))
            p["has_buttons"] = bool(p.get("notes") or (p.get("link") or {}).get("href"))
            for n in p.get("notes", []):
                n["has_links"] = bool(n.get("links"))
    if page == "resume":
        for r in c.get("roles", []):
            if r.get("mark") == "sof":
                r["mark_html"] = ('<span class="sof-slot" data-slot="sof-logo" aria-hidden="true" '
                                  'style="width:52px;font-size:1rem">SOF</span>')
            else:
                style = f' style="color:var(--{r["hue"]})"' if r.get("hue") else ""
                r["mark_html"] = f'<span class="mark"{style}>{svg(r.get("icon"), "1.8")}</span>'
            r["details_html"] = note_html(r.get("details"))
        c["pdf_on"] = bool((c.get("pdf") or {}).get("offer"))
    return c


# ── reading, building, checking ─────────────────────────────────────────────────────────────────────────────────
def load(root=None):
    root = pathlib.Path(root or ROOT)
    return {k: json.loads((root / "content" / f).read_text(encoding="utf-8")) for k, (f, _) in PAGES.items()}


REGION = re.compile(r"<!-- ([a-z0-9-]+):([a-z0-9-]+) -->(.*?)<!-- /\1:\2 -->", re.S)


def keep_regions(new, old):
    """A region another tool writes (<!-- netflix:tile -->...<!-- /netflix:tile -->, tools/netflix_build.py) keeps
    what that tool last put there: the words' build never rewrites it."""
    kept = {(m.group(1), m.group(2)): m.group(3) for m in REGION.finditer(old or "")}
    return REGION.sub(lambda m: f"<!-- {m.group(1)}:{m.group(2)} -->{kept.get((m.group(1), m.group(2)), m.group(3))}"
                                f"<!-- /{m.group(1)}:{m.group(2)} -->", new)


def build(content, root=None, today=None):
    """{output file: text} for every page built from content (a dict page -> words); a generator's regions keep what
    the page on disk holds."""
    root = pathlib.Path(root or ROOT)
    out = {}
    for page, (_, outs) in PAGES.items():
        ctx = prepare(page, content[page], today)
        for tpl, dest in outs:
            txt = render((root / "content" / "templates" / tpl).read_text(encoding="utf-8"), ctx)
            if REGION.search(txt) and (root / dest).exists():
                txt = keep_regions(txt, (root / dest).read_text(encoding="utf-8"))
            out[dest] = txt
    return out


RAW = re.compile(r"```\{=html\}\n(.*?)\n```", re.S)
INCLUDE = re.compile(r"\{\{< include (\S+) >\}\}")


def page_html(page, built, root=None):
    """The HTML a page's .qmd puts between the site's header and footer, for the editor's instant preview: every
    raw block in order, includes read from the build or the repository."""
    root = pathlib.Path(root or ROOT)
    qmd = built[PAGES[page][1][0][1]]
    body = qmd.split("\n---\n", 1)[1] if qmd.startswith("---\n") else qmd
    parts = []
    for line_block in re.split(r"(\{\{< include \S+ >\}\})", body):
        m = INCLUDE.fullmatch(line_block.strip())
        if m:
            name = m.group(1)
            inc = built.get(name) or (root / name).read_text(encoding="utf-8")
            parts += RAW.findall(inc)
        else:
            parts += RAW.findall(line_block)
    return "\n".join(parts)


def front(page, content):
    """(browser tab title, search description) of a page."""
    p = content[page].get("page") or {}
    return p.get("title") or "", p.get("description") or ""


def strings(obj, path=""):
    """Every string in the words with its dotted path, for the contact-detail check and the change list."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from strings(v, f"{path}.{i}")
    elif isinstance(obj, str):
        yield path, obj


def check_private(content, root=None):
    """[(page, path, what, match)] for any word that looks like a contact detail, by the same rules the build's
    final check (tools/harden_docs.py) applies to the published site."""
    root = pathlib.Path(root or ROOT)
    sys.path.insert(0, str(root / "tools"))
    try:
        import importlib
        hd = importlib.import_module("harden_docs")
        forbidden = hd.FORBIDDEN
    finally:
        sys.path.pop(0)
    found = []
    for page, words in content.items():
        for path, s in strings(words):
            for what, rx in forbidden.items():
                m = rx.search(s)
                if m:
                    found.append((page, path, what, m.group(0)))
    return found


def validate(content):
    """Plain-word problems that would break a page, before anything is written."""
    problems = []
    for page in PAGES:
        if page not in content or not isinstance(content[page], dict):
            problems.append(f"The {page} page's words are missing.")
    if problems:
        return problems
    ids = [p.get("id") for p in content["projects"].get("projects", [])]
    if len(ids) != len(set(ids)):
        problems.append("Two projects share a name; give each its own.")
    nids = [n.get("id") for p in content["projects"].get("projects", []) for n in p.get("notes", [])]
    if len(nids) != len(set(nids)) or any(not re.fullmatch(r"[a-z0-9-]{1,60}", str(i or "")) for i in ids + nids):
        problems.append("Two notes on the Projects page share an id; remove one and add it again.")
    for p in content["projects"].get("projects", []):
        if p.get("generated"):
            continue
        pic = p.get("picture") or {}
        if pic.get("kind") == "image" and not (pic.get("alt") or "").strip():
            problems.append(f"The picture on {p.get('name') or 'a project'} needs a description for people who cannot see it.")
        if pic.get("kind") == "image" and not re.fullmatch(r"assets/[\w./-]+\.(webp|png|jpg|jpeg)", pic.get("src") or ""):
            problems.append(f"The picture on {p.get('name') or 'a project'} is missing; add it again.")
    rids = [x.get("id") for x in content["resume"].get("roles", [])]
    if len(rids) != len(set(rids)) or any(not re.fullmatch(r"[a-z0-9-]{1,60}", str(i or "")) or i == "edu" for i in rids):
        problems.append("Two roles share an id; remove one and add it again.")
    for p in content["projects"].get("projects", []):
        if p.get("generated"):
            continue
        if not (p.get("name") or "").strip():
            problems.append("A project has no name.")
        href = ((p.get("link") or {}).get("href") or "").strip()
        if href and not re.fullmatch(r"https://[^\s\"'<>]+|[\w./#-]+\.html(#[\w-]+)?", href):
            problems.append(f"The button on {p.get('name') or 'a project'} needs a web address that starts with https://.")
        if p.get("icon") and p["icon"] not in ICONS:
            problems.append(f"{p.get('name')}: unknown icon {p['icon']}.")
    for r in content["resume"].get("roles", []):
        if not (r.get("name") or "").strip():
            problems.append("A role has no name.")
    for row in content["about"].get("career", []):
        try:
            if row.get("left") in (None, ""):
                _year(row.get("from")), _year(row.get("to"))
        except ValueError:
            problems.append(f"The timeline row {row.get('name') or ''} needs dates like 2018-03, or now.")
    return problems


def write(built, root=None):
    root = pathlib.Path(root or ROOT)
    changed = []
    for dest, txt in built.items():
        p = root / dest
        if not p.exists() or p.read_text(encoding="utf-8") != txt:
            crlf = p.exists() and b"\r\n" in p.read_bytes()      # keep the file's own line endings (git autocrlf)
            p.write_text(txt, encoding="utf-8", newline="\r\n" if crlf else "\n")
            changed.append(dest)
    return changed


def differs(built, root=None):
    root = pathlib.Path(root or ROOT)
    return [d for d, txt in built.items() if not (root / d).exists() or (root / d).read_text(encoding="utf-8") != txt]


def main(argv):
    content = load()
    problems = validate(content)
    if problems:
        print("content_build: the words cannot be built:", *problems, sep="\n  ")
        return 1
    private = check_private(content)
    if private:
        print("content_build: these words look like contact details, which the site never publishes:",
              *[f"{pg}: {path}: {what} ({m})" for pg, path, what, m in private], sep="\n  ")
        return 1
    built = build(content)
    if "--check" in argv:
        offered = bool((content["resume"].get("pdf") or {}).get("offer"))
        have = (ROOT / "assets" / "resume.pdf").exists()
        if offered != have:
            print("content_build: the resume " + ("offers a PDF but assets/resume.pdf is missing" if offered else
                  "offers no PDF but assets/resume.pdf is there") + "; run: python tools/resume_pdf.py")
            return 1
        bad = differs(built)
        if bad:
            print("content_build: these pages differ from what content/ builds (a page was edited by hand?):",
                  *bad, "Change the words in content/*.json (the Hub's portfolio editor) or the layout in "
                  "content/templates/, then run: python tools/content_build.py", sep="\n  ")
            return 1
        print("content_build: every page matches content/")
        return 0
    changed = write(built)
    print("content_build: wrote " + (", ".join(changed) if changed else "nothing (every page already matched)"))
    if "--pdf" in argv:
        sys.path.insert(0, str(ROOT / "tools"))
        import resume_pdf
        print(resume_pdf.main(content["resume"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
