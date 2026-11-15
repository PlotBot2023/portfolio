"""Write a public, read-only snapshot of the sports leaderboards into guides/leaderboards/, one page per sport.

    python tools/leaderboards_snapshot.py --sa <the SportsAnalytics checkout>

The live leaderboards run on the owner's PC (SportsAnalytics shared/leaderboards, served at /leaders/<sport>). This
builds the same pages with that repo's own page builder, reading its databases read-only, then makes them safe to
publish on a static site:
  - the model's own bet log board ("Model bets by grade", source bet_log) is left out: it is the owner's settled bets,
    not market data; the market boards (cover rate, over rate) stay;
  - links to pages that live only on the owner's PC (the "Experts, me and the market" betting page) are dropped, and the
    sport links point at the other snapshot pages;
  - team and player pictures hotlinked from other sites are removed, so each card shows its own drawn badge (the
    card's built-in fallback), and no visitor request leaves the site;
  - a board whose query failed is left out (its error text would name the owner's databases);
  - a sport with no measured board at all is not published;
  - the live "data as of, N days ago" chip becomes a fixed "Snapshot, data <date>" chip, so the page never counts up an
    age it cannot refresh;
  - a "Back to the portfolio" link goes at the top. The SportsAnalytics folder's
location is never written into the output. Rerun to refresh the snapshot.
"""
import argparse, os, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "guides" / "leaderboards"
PRIVATE_SOURCES = {"bet_log"}
OUTSIDE_PICTURE = re.compile(r'<span class="sx-ph"><img\b[^>]*\bsrc="https?://[^"]*"[^>]*></span>', re.I)
ASOF_CHIP = re.compile(r'<span class="gx-asof(?: stale)?" data-gx-asof="[^"]*"[^>]*><i class="g" aria-hidden="true">[^<]*</i>'
                       r'<span class="k">[^<]*</span><span class="t">([^<]*),</span><span class="a">[^<]*</span></span>')
LOGO_DISC =re.compile(r'(<span class="sx-disc)( [^"]*)?(">)(?=<span class="sx-fb">)')
BACK = ('<a href="../../projects.html" style="display:inline-flex;align-items:center;min-height:44px;margin:12px 16px 0;'
        'padding:0 18px;border-radius:999px;border:1.5px solid #7FE3FF;background:#16284A;color:#FFFFFF;'
        'font:700 16px system-ui,sans-serif;text-decoration:none">Back to the portfolio</a>')


def clean(html_text):
    t, n_pics = OUTSIDE_PICTURE.subn("", html_text)
    # the live chip's age is recounted by the page script on every visit, so a snapshot would read "Stale, 34 d ago" a
    # month on; a snapshot says what it is, with its data date and no running age
    t, n_chip = ASOF_CHIP.subn(lambda m: f'<span class="gx-asof"><i class="g" aria-hidden="true">●</i>'
                                         f'<span class="k">Snapshot, data</span><span class="t">{m.group(1)}</span></span>', t)
    if n_chip != 1:
        raise SystemExit(f"expected one as-of chip, found {n_chip}")
    # the picture's own onerror fallback cannot run under the site's CSP, so the disc is marked picture-less up front
    t = LOGO_DISC.sub(lambda m: m.group(1) + (m.group(2) or "") + " sx-noimg" + m.group(3), t)
    t = re.sub(r'\s+onerror="[^"]*"', "", t)
    t, n_charset = re.subn(r'<meta\s+charset=["\']?utf-?8["\']?\s*/?>', '<meta charset="utf-8">', t, count=1, flags=re.I)
    if n_charset != 1:
        raise SystemExit("no charset tag: harden_docs.py could not add the page's Content-Security-Policy")
    t, n_body = re.subn(r"(<body\b[^>]*>)", r"\1" + BACK, t, count=1, flags=re.I)
    if n_body != 1:
        raise SystemExit("no <body> tag")
    left = re.findall(r'(?:src|href)="(?:https?:)?//(?!insideairbnb)[^"]*"|href="/[^"]*"', t)
    if left:
        raise SystemExit(f"outside or local links left: {left[:5]}")
    return t, n_pics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sa", required=True, type=pathlib.Path, help="the SportsAnalytics checkout")
    a = ap.parse_args()
    sys.path.insert(0, str(a.sa.resolve()))
    os.chdir(a.sa)                       # its settings file and database helpers resolve from the repo root
    from shared.leaderboards import core, load, page, sports

    built = {}
    for sport in list(sports.SPORTS):
        # a board whose query failed is dropped, never published: its error text names the owner's databases
        items = [it for it in load.run(sport)
                 if isinstance(it, core.Missing) or (it.board.source not in PRIVATE_SOURCES and not it.error)]
        measured = [it for it in items if isinstance(it, core.Result) and (it.ranked or it.early)]
        if measured:
            built[sport] = items
        print(f"{sport}: {len(measured)} measured boards of {len(items)}")
    # the sport links show only the sports published here, and no page that lives only on the owner's PC
    for k in list(sports.SPORTS):
        if k not in built:
            del sports.SPORTS[k]
        else:
            sports.SPORTS[k]["see"] = []
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.html"):
        if old.stem not in built:
            old.unlink()
    for sport, items in built.items():
        t, n_pics = clean(page.build_html(sport, items, base="./", suffix=".html"))
        (OUT / f"{sport}.html").write_text(t, encoding="utf-8")
        print(f"wrote guides/leaderboards/{sport}.html: {n_pics} outside pictures removed, {len(t):,} characters")


if __name__ == "__main__":
    main()
