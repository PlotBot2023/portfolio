"""Build the Netflix mood tags panel on the Projects page from the study's state on this PC.

    python tools/netflix_build.py            # rewrites the marked regions of projects.qmd and assets/netflix/summary.json
    python tools/netflix_build.py --check    # exit 1 if projects.qmd is not what the state would write

The study itself (SportsAnalytics, personal/netflix_moods) is private: it keeps the household's viewing list and every
title's tag under %LOCALAPPDATA%\\SportsAnalytics\\netflix_moods, outside git. This script publishes only what cannot
identify a title or a viewing habit:

    * the mood tags the model wrote, as words, with no title beside them (the WALL most confident ones)
    * counts: titles on the list, titles tagged, how many were read from critics' reception and how many from the plot
      alone, how many feelings are scored, how many tags a person has corrected
    * the date the text was read and the model's name

Never written: a title, a viewer, a viewing date or count, a sentence of the source text. Every number in the panel is
computed here from the state; none is typed in.
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "projects.qmd"
OUT = ROOT / "assets" / "netflix" / "summary.json"
WALL = 10            # tags on the wall
MIN_N = 4            # a rate on fewer is not measured


def state_path() -> Path:
    base = os.environ.get("SA_NETFLIX_MOODS_DIR") or Path(os.environ.get("LOCALAPPDATA", "")) / "SportsAnalytics" / "netflix_moods"
    return Path(base) / "state.json"


def summarise(st: dict) -> dict:
    """The public summary: counts and tag words only."""
    tagged = [t for t in st["titles"] if t.get("proposal")]
    # the most confident tags first: the z of the tag's leading feeling; an exact article match before a doubtful one
    def sure(t):
        lead = (t["tag"]["feelings"] or [None])[0]
        return (bool((t.get("match") or {}).get("exact")), (t.get("z") or {}).get(lead, 0) if lead else 0)
    wall, seen = [], set()
    for t in sorted(tagged, key=sure, reverse=True):
        words = t["tag"]["moniker"]
        same = (frozenset(t["tag"]["feelings"]), t["tag"]["story"])      # "swoony and comforting" is "comforting and swoony"
        if t["tag"]["feelings"] and same not in seen:
            seen.add(same)
            wall.append(words)
        if len(wall) == WALL:
            break
    c, k = st["coverage"], st["kpi"]["shown"]
    judged = sum(1 for t in st["titles"] if t.get("judged"))
    return {
        "titles": c["titles"], "tagged": len(tagged), "from_reception": c["from_reception"], "from_plot": c["from_plot"],
        "feelings": len(st["feelings"]), "judged": judged,
        "kept": k["kept"] if k["shown"] >= MIN_N else None, "shown": k["shown"] if k["shown"] >= MIN_N else None,
        "asof": (st.get("asof") or "")[:10], "model": st.get("model", ""), "wall": wall,
        "source": "English Wikipedia, CC BY-SA 4.0",
    }


def day(iso: str) -> str:
    if not iso:
        return "not measured"
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def blocks(s: dict) -> dict:
    e = html.escape
    live = s["tagged"] > 0
    status = '<span class="status live">First results</span>' if live else '<span class="status building">Coming next</span>'
    tile = f'<span class="tt"><span class="name">Netflix mood tags</span>{status}</span>'
    chips = "".join(f"<li>{e(w)}</li>" for w in s["wall"])
    third = (f'<li class="stat"><span class="n">{s["kept"]} of {s["shown"]}</span><span class="l">proposed feelings a person kept</span></li>'
             if s["kept"] is not None else
             '<li class="stat"><span class="n">First pass</span><span class="l">the model\'s tags, before a person corrects them</span></li>')
    panel = (
        '<article class="panel rail-top" data-item="netflix" aria-label="Netflix mood tags">\n'
        f'        <div class="media inlay moods"><ul class="tray wall" aria-label="Mood tags the model wrote, most confident first">{chips}</ul></div>\n'
        '        <div class="info">\n'
        f'          <div class="head"><h2>Netflix mood tags</h2>{status}</div>\n'
        '          <ul class="stats">\n'
        f'            <li class="stat"><span class="n">{s["tagged"]} of {s["titles"]}</span><span class="l">most-watched titles given a mood tag</span></li>\n'
        f'            <li class="stat"><span class="n">{s["feelings"]}</span><span class="l">feelings scored for every title</span></li>\n'
        f'            {third}\n'
        '          </ul>\n'
        '          <div class="foot">\n'
        '            <ul class="tray slim" aria-label="Methods"><li>Language model</li><li>Clustering</li><li>Human in the loop</li></ul>\n'
        '            <div class="btn-row"><button class="btn" type="button" popovertarget="n-netflix">Notes</button></div>\n'
        '          </div>\n'
        '        </div>\n'
        '      </article>')
    checked = (f"A person has corrected {s['judged']} of the tags so far" if s["judged"] else "No tag has been corrected by a person yet")
    note = (
        '<div id="n-netflix" popover class="note">\n'
        '  <h3>Netflix mood tags</h3>\n'
        '  <p>A mood tag says more than a genre: tear-jerky comedy, chilling fantasy, nail-biting relationship murder thriller. '
        f'This project writes one for each of a household\'s {s["titles"]} most-watched Netflix titles. The titles and the viewing '
        'history are private and are not shown here; only the tags are.</p>\n'
        '  <p>Each title\'s English Wikipedia article is read by a sentence model that runs on my own machine. Every sentence is '
        f'scored for {s["feelings"]} feelings by its closeness to anchor phrases, each feeling is z-scored across the titles, and the '
        'strongest one or two join a story type taken from the article\'s own description.</p>\n'
        f'  <p>Where it stands: {s["tagged"]} of {s["titles"]} titles matched an article. {s["from_reception"]} had at least 8 sentences of '
        f'critics\' reception; {s["from_plot"]} were read mostly from the plot. These are the model\'s first-pass tags. {checked}, so no '
        'accuracy is measured. Next is a review page where each correction refits the model.</p>\n'
        f'  <p>Text from {e(s["source"])}, read on {day(s["asof"])}. Model: {e(s["model"].split("/")[-1])}.</p>\n'
        '  <button class="btn" popovertarget="n-netflix" popovertargetaction="hide">Close</button>\n'
        '</div>')
    count = "<li>1 with first results</li>" if live else "<li>1 on the way</li>"
    return {"tile": tile, "panel": panel, "note": note, "count": count}


def apply(text: str, parts: dict) -> str:
    for key, body in parts.items():
        pat = re.compile(rf"(<!-- netflix:{key} -->).*?(<!-- /netflix:{key} -->)", re.S)
        if not pat.search(text):
            raise SystemExit(f"projects.qmd has no <!-- netflix:{key} --> region")
        text = pat.sub(lambda m: m.group(1) + body + m.group(2), text)
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    sp = state_path()
    if not sp.exists():
        print(f"no study state on this PC ({sp}); nothing built")
        return 1
    s = summarise(json.loads(sp.read_text(encoding="utf-8")))
    new = apply(PAGE.read_text(encoding="utf-8"), blocks(s))
    if a.check:
        same = new == PAGE.read_text(encoding="utf-8")
        print("projects.qmd matches the state" if same else "projects.qmd is out of date: run tools/netflix_build.py")
        return 0 if same else 1
    PAGE.write_text(new, encoding="utf-8", newline="\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(s, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"tagged {s['tagged']} of {s['titles']}, wall {len(s['wall'])} tags, as of {s['asof']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
