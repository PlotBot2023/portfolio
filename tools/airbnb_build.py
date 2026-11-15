"""Build the Broward Airbnb case study's numbers, charts and table twins from the study's processed outputs.

    python tools/airbnb_build.py --src <folder holding calendar_metrics.csv and listings_adv_metrics.csv>

Writes `_airbnb_generated.qmd` (included by airbnb.qmd) and `assets/airbnb/revpar-map.webp`. Every number on the
page, and its as-of date, comes from here, so rerunning after a data refresh updates the page; nothing is typed by hand.
The source folder's location is never written into the output.

Definitions (also shown on the page's Method note):
  - the latest snapshot is the newest snapshot_date in calendar_metrics;
  - RevPAR, ADR, occupancy and expected revenue are the study's calendar metrics over the 365-day window after a snapshot;
  - "entire homes" are room_type "Entire home/apt";
  - a "multi-listing host" holds 10 or more active listings in the latest snapshot.
"""
import argparse, html, json, pathlib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGETS = [10_000, 25_000, 50_000, 75_000, 100_000]
MIN_N = 50          # a neighbourhood is ranked only with at least this many entire homes
MULTI = 10          # listings that make a multi-listing host
RAMP = ["#4A7BE0", "#2E9BD6", "#33C2C9", "#6FDDA6", "#B9EE7E", "#FFF27A"]   # one ramp, each step lighter; the first still 3:1 on the well


def money(v, k=False):
    if k and v >= 1000:
        return f"${v / 1000:,.0f}k"
    return f"${v:,.0f}"


def pct(v):
    return f"{v:.0f}%"


def load(src):
    cal = pd.read_csv(src / "calendar_metrics.csv", na_values=["NULL"],
                      usecols=["snapshot_date", "listing_id", "adr", "occupancy", "revpar", "expected_revenue"])
    lst = pd.read_csv(src / "listings_adv_metrics.csv", na_values=["NULL"],
                      usecols=["listing_id", "neighbourhood_cleansed", "room_type", "latitude", "longitude", "host_id"])
    lst = lst.drop_duplicates("listing_id")[["listing_id", "neighbourhood_cleansed", "room_type", "latitude", "longitude", "host_id"]]
    cal["snapshot_date"] = pd.to_datetime(cal["snapshot_date"])
    return cal.merge(lst, on="listing_id", how="left")


def build(df):
    snaps = sorted(df["snapshot_date"].unique())
    last = df[df["snapshot_date"] == snaps[-1]].copy()
    homes = last[last["room_type"] == "Entire home/apt"].copy()
    host_n = last.groupby("host_id")["listing_id"].transform("count")
    last["multi"] = host_n >= MULTI
    homes = homes.merge(last[["listing_id", "multi"]], on="listing_id", how="left")

    s = {
        "asof": pd.Timestamp(snaps[-1]).strftime("%d %B %Y").lstrip("0"),
        "asof_iso": pd.Timestamp(snaps[-1]).strftime("%Y-%m-%d"),
        "first": pd.Timestamp(snaps[0]).strftime("%B %Y"),
        "n_snaps": len(snaps),
        "active": int(len(last)),
        "homes": int(len(homes)),
        "homes_share": 100 * len(homes) / len(last),
        "revpar": float(homes["revpar"].median()),
        "adr": float(homes["adr"].median()),
        "occ": 100 * float(homes["occupancy"].median()),
        "revenue": float(homes["expected_revenue"].median()),
        "multi_share": 100 * float(last["multi"].mean()),
        "hosts": int(last["host_id"].nunique()),
    }
    s["targets"] = [(t, 100 * float((homes["expected_revenue"] >= t).mean())) for t in TARGETS]

    nb = (homes.groupby("neighbourhood_cleansed")
          .agg(n=("listing_id", "count"), revpar=("revpar", "median"), adr=("adr", "median"), occ=("occupancy", "median"))
          .query("n >= @MIN_N").sort_values("revpar", ascending=False))
    s["nb"] = nb
    s["nb_ranked"] = int(len(nb))

    growth = df.groupby("snapshot_date")["listing_id"].nunique()
    seen, rows = set(), []
    for d in snaps:
        ids = set(df.loc[df["snapshot_date"] == d, "listing_id"])
        rows.append((pd.Timestamp(d).strftime("%b %Y"), len(ids), len(ids - seen) if seen else None))
        seen |= ids
    s["growth"] = rows

    by_type = homes.groupby("multi")["revpar"].median()
    s["rev_indep"] = float(by_type.get(False, np.nan))
    s["rev_multi"] = float(by_type.get(True, np.nan))
    s["map"] = homes[["latitude", "longitude", "revpar"]].dropna()
    return s


def draw_map(pts, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, BoundaryNorm
    qs = np.quantile(pts["revpar"], np.linspace(0, 1, len(RAMP) + 1))
    qs[0], qs[-1] = qs[0] - 1e-9, qs[-1] + 1e-9
    cmap, norm = ListedColormap(RAMP), BoundaryNorm(qs, len(RAMP))
    pts = pts.sort_values("revpar")      # brightest dots on top
    # frame on where the listings are: the few far-inland ones (the outer 0.5 percent west) would shrink the coast
    lon_lo, lat_lo, lat_hi = pts["longitude"].quantile(.005), pts["latitude"].quantile(.002), pts["latitude"].quantile(.998)
    lat0 = np.deg2rad(pts["latitude"].mean())
    x, y = pts["longitude"] * np.cos(lat0), pts["latitude"]
    xr = (lon_lo * np.cos(lat0), x.max()); yr = (lat_lo, lat_hi)
    h = 9.0; w = h * (xr[1] - xr[0]) / (yr[1] - yr[0])
    fig = plt.figure(figsize=(w, h), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.scatter(x, y, c=pts["revpar"], cmap=cmap, norm=norm, s=5, linewidths=0, alpha=.95)
    ax.set_xlim(*xr); ax.set_ylim(*yr); ax.set_aspect("equal"); ax.axis("off")
    fig.patch.set_alpha(0); ax.patch.set_alpha(0)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".png")
    fig.savefig(tmp, transparent=True, bbox_inches="tight", pad_inches=0.04); plt.close(fig)
    from PIL import Image
    im = Image.open(tmp); im.save(out, quality=88, method=6); tmp.unlink()   # webp keeps no EXIF from matplotlib
    return [(qs[i], qs[i + 1]) for i in range(len(RAMP))]


def bars(rows, vmax, cls=""):
    """rows: (label, value, shown text, sub text or ''). An HTML bar chart: real text, scales, reads in a screen reader."""
    out = [f'<ul class="hbars {cls}">']
    for lab, v, txt, sub in rows:
        w = max(1.5, 100 * v / vmax)
        out.append(f'<li><span class="hb-l">{html.escape(lab)}{f"<small>{html.escape(sub)}</small>" if sub else ""}</span>'
                   f'<span class="hb-t" aria-hidden="true"><span class="hb-f" style="width:{w:.1f}%"></span></span>'
                   f'<span class="hb-v">{html.escape(txt)}</span></li>')
    out.append("</ul>")
    return "\n".join(out)


def table(head, rows, caption):
    h = "".join(f"<th scope=\"col\">{html.escape(c)}</th>" for c in head)
    b = "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="twin"><caption>{html.escape(caption)}</caption><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>'


def note(id_, title, body):
    return (f'<div id="{id_}" popover class="note"><h3>{html.escape(title)}</h3>{body}'
            f'<button class="btn" popovertarget="{id_}" popovertargetaction="hide">Close</button></div>')


def page(s, legend):
    nb = s["nb"]
    top, bot = nb.head(6), nb.tail(4)
    best, worst = nb.index[0], nb.index[-1]
    nb_rows = [(n, r.revpar, money(r.revpar), f"{r.n:,} homes") for n, r in pd.concat([top, bot]).iterrows()]
    t_rows = [(f"{money(t, True)} a year", p, pct(p), "") for t, p in s["targets"]]
    g_rows = [(lab, n, f"{n:,}", f"{new:,} new" if new is not None else "first snapshot") for lab, n, new in s["growth"]]
    reach50 = dict(s["targets"])[50_000]

    stats = f"""
    <ul class="stats" aria-label="Key numbers, entire homes, latest snapshot">
      <li class="stat"><span class="n">{money(s['revpar'])}</span><span class="l">median RevPAR a night</span></li>
      <li class="stat"><span class="n">{money(s['revenue'], True)}</span><span class="l">median expected revenue a year</span></li>
      <li class="stat"><span class="n">{pct(reach50)}</span><span class="l">of entire homes reach {money(50_000, True)}</span></li>
      <li class="stat"><span class="n">{pct(s['multi_share'])}</span><span class="l">of listings held by hosts with {MULTI} or more</span></li>
    </ul>"""

    def band(i, lo, hi):
        if i == 0: return f"under {money(hi)}"
        if i == len(RAMP) - 1: return f"{money(lo)} and up"
        return f"{money(lo)} to {money(hi)}"
    leg = "".join(f'<li><span class="sw" style="background:{c}" aria-hidden="true"></span>{band(i, lo, hi)}</li>'
                  for i, (c, (lo, hi)) in enumerate(zip(RAMP, legend)))

    views = f"""
    <div class="tabs" role="tablist" aria-label="Chart">
      <button class="tab" role="tab" id="t-map" aria-controls="v-map" aria-selected="true">The map</button>
      <button class="tab" role="tab" id="t-nb" aria-controls="v-nb" aria-selected="false">Neighbourhoods</button>
      <button class="tab" role="tab" id="t-tg" aria-controls="v-tg" aria-selected="false">Revenue targets</button>
      <button class="tab" role="tab" id="t-gr" aria-controls="v-gr" aria-selected="false">Growth</button>
    </div>
    <div class="tabpanel cv" role="tabpanel" id="v-map" aria-labelledby="t-map">
      <div class="mapwrap inlay"><img src="assets/airbnb/revpar-map.webp" alt="Map of {s['homes']:,} Broward County entire-home listings as dots, coloured by RevPAR from blue for the lowest sixth to yellow for the highest. Listings crowd the coast in a dense band, where most of the yellow sits; inland they thin out."></div>
      <div class="cv-side">
        <span class="eyebrow">RevPAR a night, each colour a sixth of homes</span>
        <ul class="legend">{leg}</ul>
        <div class="btn-row"><button class="btn" type="button" popovertarget="tw-map">Table</button><button class="btn" type="button" popovertarget="n-method">Method</button></div>
      </div>
    </div>
    <div class="tabpanel cv" role="tabpanel" id="v-nb" aria-labelledby="t-nb" hidden>
      <div class="cv-chart"><span class="eyebrow">Median RevPAR, the 6 strongest and 4 weakest of {s['nb_ranked']} neighbourhoods</span>{bars(nb_rows, float(nb['revpar'].max()))}</div>
      <div class="cv-side"><button class="btn" type="button" popovertarget="tw-nb">Table</button></div>
    </div>
    <div class="tabpanel cv" role="tabpanel" id="v-tg" aria-labelledby="t-tg" hidden>
      <div class="cv-chart"><span class="eyebrow">Share of entire homes reaching each expected revenue</span>{bars(t_rows, 100, 'tall')}</div>
      <div class="cv-side"><button class="btn" type="button" popovertarget="tw-tg">Table</button></div>
    </div>
    <div class="tabpanel cv" role="tabpanel" id="v-gr" aria-labelledby="t-gr" hidden>
      <div class="cv-chart"><span class="eyebrow">Active listings in each snapshot</span>{bars(g_rows, max(n for _, n, _ in s['growth']), 'tall')}</div>
      <div class="cv-side"><button class="btn" type="button" popovertarget="tw-gr">Table</button></div>
    </div>"""

    answer = f"""
    <ul class="verdicts">
      <li><span class="vk up" aria-hidden="true"></span><span><b>Best bet:</b> {html.escape(best)}, median RevPAR {money(nb.iloc[0].revpar)}</span></li>
      <li><span class="vk dn" aria-hidden="true"></span><span><b>Toughest:</b> {html.escape(worst)}, median RevPAR {money(nb.iloc[-1].revpar)}</span></li>
      <li><span class="vk ev" aria-hidden="true"></span><span><b>Typical home:</b> {money(s['adr'])} a night at {pct(s['occ'])} occupancy</span></li>
      <li><span class="vk ev" aria-hidden="true"></span><span><b>Only {pct(reach50)}</b> clear {money(50_000, True)} a year</span></li>
    </ul>"""

    twins = "\n".join([
        note("tw-map", "The map as a table", table(["RevPAR band", "Colour"], [(band(i, lo, hi), f"step {i + 1} of {len(RAMP)}, {'darkest' if i == 0 else 'lightest' if i == len(RAMP) - 1 else 'lighter'}") for i, (lo, hi) in enumerate(legend)],
                                                   f"Each band holds one sixth of the {s['homes']:,} entire homes, snapshot of {s['asof']}.")),
        note("tw-nb", "Neighbourhoods as a table", table(["Neighbourhood", "Homes", "Median RevPAR", "Median ADR", "Median occupancy"],
                                                          [(n, f"{r.n:,}", money(r.revpar), money(r.adr), pct(100 * r.occ)) for n, r in nb.iterrows()],
                                                          f"Every neighbourhood with at least {MIN_N} entire homes, snapshot of {s['asof']}.")),
        note("tw-tg", "Revenue targets as a table", table(["Expected revenue a year", "Share of entire homes"], [(f"{money(t)} or more", pct(p)) for t, p in s["targets"]],
                                                           f"{s['homes']:,} entire homes, snapshot of {s['asof']}.")),
        note("tw-gr", "Growth as a table", table(["Snapshot", "Active listings", "New since the last snapshot"], [(lab, f"{n:,}", f"{new:,}" if new is not None else "first snapshot") for lab, n, new in s["growth"]],
                                                  "Listings active in each Inside Airbnb snapshot, all room types.")),
        note("n-method", "Method", f"""<p>Four quarterly Inside Airbnb snapshots of Broward County, {s['first']} to {s['asof']}. For each listing the
          study reads the 365-day calendar after a snapshot: booked nights, the average daily rate (ADR), occupancy, RevPAR (revenue per available
          night) and expected annual revenue. Headline numbers are medians over entire homes in the latest snapshot ({s['homes']:,} of {s['active']:,}
          active listings). A neighbourhood is ranked only with at least {MIN_N} entire homes. A multi-listing host holds {MULTI} or more active listings.</p>
          <p>Calendar availability is a proxy for bookings: a blocked night can be a stay or an owner's hold, so occupancy is an estimate, labelled as such.</p>"""),
    ])

    rail = f"""
    <ul class="rail" aria-label="About this data">
      <li>Inside Airbnb</li><li>As of {s['asof']}</li><li>{s['n_snaps']} snapshots</li><li>{s['active']:,} active listings</li><li>{s['hosts']:,} hosts</li>
    </ul>"""
    return stats, views, answer, twins, rail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=pathlib.Path)
    a = ap.parse_args()
    s = build(load(a.src))
    legend = draw_map(s["map"], ROOT / "assets" / "airbnb" / "revpar-map.webp")
    stats, views, answer, twins, rail = page(s, legend)
    out = f"""<!-- generated by tools/airbnb_build.py from the study's processed outputs; do not edit by hand -->
```{{=html}}
<div class="sv v-case">
  <section class="panel hero-glass brk case-hero" aria-labelledby="case-title">
    <div class="ch-text">
      <span class="eyebrow">Case study, Broward County, Florida</span>
      <h1 id="case-title" class="page-title">The best and worst bets in Broward Airbnb</h1>
      <p class="lede">What an entire-home rental really earns, and where.</p>
    </div>
    {stats}
  </section>
  <section class="panel rail-top case-view" aria-label="Charts">
    {views}
  </section>
  <section class="panel case-answer" aria-labelledby="ans-title">
    <h2 id="ans-title" class="sec-title">The answer</h2>
    {answer}
    <span class="eyebrow">Open a notebook</span>
    <div class="nb-links">
      <a class="btn" href="notebooks/broward-market-analysis.html">Market</a>
      <a class="btn" href="notebooks/broward-pricing-consistency.html">Data quality</a>
      <a class="btn" href="notebooks/broward-segmentation.html">Segments</a>
      <a class="btn primary" href="notebooks/broward-investor-guide.html">Investor guide</a>
    </div>
  </section>
  {rail}
</div>
{twins}
<script src="assets/sv.js"></script>
```
"""
    (ROOT / "_airbnb_generated.qmd").write_text(out, encoding="utf-8")
    reach50 = dict(s["targets"])[50_000]
    home = f"""<!-- generated by tools/airbnb_build.py; do not edit by hand -->
```{{=html}}
    <a class="feature case-feature" href="airbnb.html">
      <div class="cf-body">
        <div class="pic map"><img src="assets/airbnb/revpar-map.webp" alt="Map of Broward County entire-home listings as dots coloured by revenue per available night, blue for the lowest to yellow for the highest, crowded in a dense band along the coast."></div>
        <ul class="stats cf-stats" aria-label="Key numbers, entire homes, as of {s['asof']}">
          <li class="stat"><span class="n">{money(s['revpar'])}</span><span class="l">median RevPAR a night</span></li>
          <li class="stat"><span class="n">{money(s['revenue'], True)}</span><span class="l">median revenue a year</span></li>
          <li class="stat"><span class="n">{pct(reach50)}</span><span class="l">reach {money(50_000, True)} a year</span></li>
        </ul>
      </div>
      <div class="cap"><b>Broward Airbnb, the best and worst bets</b><span class="chip">As of {s['asof']}</span></div>
    </a>
```
"""
    (ROOT / "_airbnb_home.qmd").write_text(home, encoding="utf-8")
    (ROOT / "assets" / "airbnb" / "summary.json").write_text(json.dumps({k: v for k, v in s.items() if k not in ("nb", "map")}, indent=1, default=str), encoding="utf-8")
    print("as of", s["asof"], "homes", s["homes"], "revpar", s["revpar"], "best", s["nb"].index[0], "worst", s["nb"].index[-1])


if __name__ == "__main__":
    main()
