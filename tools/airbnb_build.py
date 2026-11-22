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
import argparse, html, json, pathlib, re, subprocess
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGETS = [10_000, 25_000, 50_000, 75_000, 100_000]
MIN_N = 50          # a neighbourhood is ranked only with at least this many entire homes
MULTI = 10          # listings that make a multi-listing host
# A nightly rate is a price only inside these bounds and off the placeholder values hosts type on blocked nights
# (in the March 2025 snapshot $1,000 is the single most common rate, 601 homes; $999 has 183). Outside, the night's
# revenue is not measured: ADR, RevPAR and expected revenue become missing; occupancy stays (it needs no price).
PRICE_MIN, PRICE_MAX = 10, 2_500
PLACEHOLDER_PRICES = {999, 1_000, 9_999, 10_000}
# The map's dots wear the page's one heat scale (RevPAR is a result: red worst, green best), by each home's rank z among
# the entire homes, on the cards' own cuts (heat_cls). The colours are read from assets/airbnb/cards.css, the file the
# cards and the bars already draw from, so the map can never drift from them.
HEAT_STEPS = ["hs-n4", "hs-n3", "hs-n2", "hs-n1", "hs-0", "hs-p1", "hs-p2", "hs-p3", "hs-p4"]


def heat_colours():
    css = (ROOT / "assets" / "airbnb" / "cards.css").read_text(encoding="utf-8")
    found = dict(re.findall(r"\.(hs-[a-z0-9]+)\s*\{\s*--hc:\s*(#[0-9A-Fa-f]{6})", css))
    missing = [k for k in HEAT_STEPS if k not in found]
    if missing:
        raise SystemExit(f"cards.css has no colour for {missing}")
    return [found[k] for k in HEAT_STEPS]


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
                      usecols=["listing_id", "neighbourhood_cleansed", "room_type", "latitude", "longitude", "host_id",
                               "bedrooms", "host_is_superhost"])
    lst = lst.drop_duplicates("listing_id")
    cal["snapshot_date"] = pd.to_datetime(cal["snapshot_date"])
    bad = cal["adr"].notna() & ((cal["adr"] < PRICE_MIN) | (cal["adr"] > PRICE_MAX) | cal["adr"].round(0).isin(PLACEHOLDER_PRICES))
    cal["price_dropped"] = bad
    cal.loc[bad, ["adr", "revpar", "expected_revenue"]] = np.nan
    return cal.merge(lst, on="listing_id", how="left")


NOW_COLS = ["Snapshot Date", "Host ID", "Listing ID", "Room Type", "Price ($)", "Occupancy Rate (365d)", "ADR (365d)"]


def price_break(d, snaps):
    """Is the newest snapshot's listing price on the same footing as the snapshot about a year before it?

    Found 2026-11-15 (bnbscope experiments, E8): at the 2026-09-22 snapshot the same listing's price is about 1.7 times
    its price a year before, the cheapest homes rose most, and about half the prices carry cents where no earlier
    snapshot had any. That looks like a change in what the price includes (fees or taxes), not hosts charging 70%
    more. Measured here on the data each time the page is built, so a later snapshot is judged on its own."""
    out = {"price_ratio_yoy": None, "price_ratio_n": 0, "cents_share_now": None, "cents_share_before": None, "price_break": False}
    if len(snaps) < 2:
        return out
    newest = pd.Timestamp(snaps[-1])
    gaps = [(abs((newest - pd.Timestamp(x)).days - 365), x) for x in snaps[:-1]]
    gap, before = min(gaps)
    if gap > 45:
        return out
    e = d[d["Room Type"].str.lower().eq("entire home/apt")].dropna(subset=["Price ($)"])
    now_p = e[e["Snapshot Date"] == newest].groupby("Listing ID")["Price ($)"].first()
    old_p = e[e["Snapshot Date"] == before].groupby("Listing ID")["Price ($)"].first()
    pair = pd.concat([now_p, old_p], axis=1, keys=["now", "old"]).dropna()
    pair = pair[(pair["old"] > 0) & (pair["now"] > 0)]
    def cents(x):
        return float((x.round(2) != x.round(0)).mean()) if len(x) else None
    ratio = float((pair["now"] / pair["old"]).median()) if len(pair) else None
    out.update(price_ratio_yoy=ratio, price_ratio_n=int(len(pair)), cents_share_now=cents(now_p), cents_share_before=cents(old_p),
               price_before=pd.Timestamp(before).strftime("%B %Y"))
    # a jump of a third or more in a year for the same homes, or cents appearing on a fifth of prices, is a change of basis
    out["price_break"] = bool((ratio is not None and ratio >= 1.33) or
                              ((out["cents_share_now"] or 0) >= 0.20 and (out["cents_share_before"] or 0) < 0.02))
    return out


def market_now(listings_csv):
    """The newest snapshot from the pipeline's listings export (one row per listing per snapshot).

    Inside Airbnb stopped publishing calendar prices after March 2025, so revenue per night can no longer be measured
    from the calendar. What still can: active listings, hosts, the listing price, and occupancy (booked nights need no
    price). The RevPAR shown for the newest snapshot is an ESTIMATE, the listing price times 365-day occupancy per
    entire home, and the page labels it so."""
    d = pd.read_csv(listings_csv, usecols=NOW_COLS)
    d["Snapshot Date"] = pd.to_datetime(d["Snapshot Date"])
    snaps = sorted(d["Snapshot Date"].unique())
    priced = d.loc[d["ADR (365d)"].notna(), "Snapshot Date"]
    last_cal_price = pd.Timestamp(priced.max()) if len(priced) else None
    last = d[d["Snapshot Date"] == snaps[-1]]
    homes = last[last["Room Type"].str.lower().eq("entire home/apt")]
    both = homes.dropna(subset=["Price ($)", "Occupancy Rate (365d)"])
    est = both["Price ($)"] * both["Occupancy Rate (365d)"]
    brk = price_break(d, snaps)
    return {
        **brk,
        "asof": pd.Timestamp(snaps[-1]).strftime("%d %B %Y").lstrip("0"),
        "asof_iso": pd.Timestamp(snaps[-1]).strftime("%Y-%m-%d"),
        "listings": int(last["Listing ID"].nunique()),
        "hosts": int(last["Host ID"].nunique()),
        "homes": int(homes["Listing ID"].nunique()),
        "price": float(homes["Price ($)"].median()),
        "price_n": int(homes["Price ($)"].notna().sum()),
        "occ": 100 * float(homes["Occupancy Rate (365d)"].median()),
        "occ_n": int(homes["Occupancy Rate (365d)"].notna().sum()),
        "revpar_est": float(est.median()) if len(est) else float("nan"),
        "est_n": int(len(est)),
        "last_cal_price": last_cal_price.strftime("%B %Y") if last_cal_price is not None else "not measured",
        "n_snaps": len(snaps),
    }


def build(df):
    snaps = sorted(df["snapshot_date"].unique())
    last = df[df["snapshot_date"] == snaps[-1]].copy()
    homes = last[last["room_type"] == "Entire home/apt"].copy()
    host_n = last.groupby("host_id")["listing_id"].transform("count")
    last["multi"] = host_n >= MULTI
    last["host_n"] = host_n
    homes = homes.merge(last[["listing_id", "multi", "host_n"]], on="listing_id", how="left")

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
        "price_dropped": int(homes["price_dropped"].sum()),
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
    s["homes_df"] = homes
    return s


def draw_map(pts, out):
    """The RevPAR map: one glowing dot per entire home in its heat step. Returns one row per step, low to high:
    (class, colour, lowest RevPAR, highest RevPAR, homes)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cols = heat_colours()
    pts = pts.copy()
    pts["k"] = [HEAT_STEPS.index(heat_cls(z)) for z in rank_z(pts["revpar"].values)]
    steps = []
    for k, (cls, c) in enumerate(zip(HEAT_STEPS, cols)):
        v = pts.loc[pts["k"] == k, "revpar"]
        if len(v):
            steps.append((cls, c, float(v.min()), float(v.max()), int(len(v))))
    pts = pts.assign(d=(pts["k"] - 4).abs()).sort_values("d")      # the strongest both ways drawn last, on top
    # frame on where the listings are: the few far-inland ones (the outer 0.5 percent west) would shrink the coast
    lon_lo, lat_lo, lat_hi = pts["longitude"].quantile(.005), pts["latitude"].quantile(.002), pts["latitude"].quantile(.998)
    lat0 = np.deg2rad(pts["latitude"].mean())
    x, y = pts["longitude"] * np.cos(lat0), pts["latitude"]
    xr = (lon_lo * np.cos(lat0), x.max()); yr = (lat_lo, lat_hi)
    h = 10.0; w = h * (xr[1] - xr[0]) / (yr[1] - yr[0])
    fig = plt.figure(figsize=(w, h), dpi=160)
    ax = fig.add_axes([0, 0, 1, 1])
    c = [cols[k] for k in pts["k"]]
    ax.scatter(x, y, c=c, s=30, linewidths=0, alpha=.09)          # the glow
    ax.scatter(x, y, c=c, s=5, linewidths=0, alpha=.95)
    ax.set_xlim(*xr); ax.set_ylim(*yr); ax.set_aspect("equal"); ax.axis("off")
    fig.patch.set_alpha(0); ax.patch.set_alpha(0)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".png")
    fig.savefig(tmp, transparent=True, bbox_inches="tight", pad_inches=0.04); plt.close(fig)
    from PIL import Image
    im = Image.open(tmp); im.save(out, quality=88, method=6); tmp.unlink()   # webp keeps no EXIF from matplotlib
    return steps


def site_commit():
    """The portfolio commit the page is built on, short; None outside a git checkout."""
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short=7", "HEAD"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or None
    except Exception:  # noqa: BLE001 - no git: the rail says not measured
        return None


def rank_z(vals):
    """A rank-based z for each value among its peers (the cards' rule), for the heat of a bar."""
    from statistics import NormalDist
    v = pd.Series(vals, dtype="float64"); n = len(v)
    return [NormalDist().inv_cdf(min(.999, max(.001, (r - .5) / n))) for r in v.rank(method="average")]


def heat_cls(z):
    for cut, c in ((-1.75, "n4"), (-1.25, "n3"), (-.75, "n2"), (-.25, "n1"), (.25, "0"), (.75, "p1"), (1.25, "p2"), (1.75, "p3")):
        if z < cut:
            return "hs-" + c
    return "hs-p4"


def bars(rows, vmax, cls="", split=None, heat=None, open_level=None):
    """rows: (label, value, shown text, sub text or ''). An HTML bar chart: real text, scales, reads in a screen reader.
    split: (row index, label) puts a labelled divider before that row, e.g. where the strongest end and the weakest begin."""
    focus = ' tabindex="0"' if "dense" in cls else ""   # a list that may scroll must be reachable by keyboard
    out = [f'<ul class="hbars {cls}"{focus}>']
    for i, (lab, v, txt, sub) in enumerate(rows):
        if split and i == split[0]:
            out.append(f'<li class="hb-split"><span>{html.escape(split[1])}</span></li>')
        w = max(1.5, 100 * v / vmax)
        name = (f'<button type="button" class="hb-open" data-card-open data-level="{open_level}" data-name="{html.escape(lab)}" '
                f'aria-label="Open the card for {html.escape(lab)}">{html.escape(lab)}</button>') if open_level else html.escape(lab)
        hc = f" {heat[i]}" if heat else ""
        out.append(f'<li><span class="hb-l">{name}{f"<small>{html.escape(sub)}</small>" if sub else ""}</span>'
                   f'<span class="hb-t" aria-hidden="true"><span class="hb-f{hc}" style="width:{w:.1f}%"></span></span>'
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


def page(s, legend, now=None):
    nb = s["nb"]
    top, bot = nb.head(6), nb.tail(4)
    best, worst = nb.index[0], nb.index[-1]
    zmap = dict(zip(nb.index, rank_z(nb["revpar"].tolist())))
    nb_heat = [heat_cls(zmap[n]) for n in list(top.index) + list(bot.index)]
    nb_rows = [(n, r.revpar, money(r.revpar), f"{int(r.n):,} homes") for n, r in pd.concat([top, bot]).iterrows()]
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
        if i == len(legend) - 1: return f"{money(lo)} and up"
        return f"{money(lo)} to {money(hi)}"
    word = {0: "far below the middle", 4: "about the middle", 8: "far above the middle"}
    top_n = max(n for *_, n in legend)
    leg = "".join(
        f'<li><span class="sw {cls}" aria-hidden="true"></span><span class="lg-b">{band(i, lo, hi)}</span>'
        f'<span class="hb-t" aria-hidden="true"><span class="hb-f {cls}" style="width:{100 * n / top_n:.1f}%"></span></span>'
        f'<span class="lg-n">{n:,}</span></li>'
        for i, (cls, c, lo, hi, n) in enumerate(legend))

    views = f"""
    <div class="tabs" role="tablist" aria-label="Chart">
      <button class="tab" role="tab" id="t-map" aria-controls="v-map" aria-selected="true">The map</button>
      <button class="tab" role="tab" id="t-nb" aria-controls="v-nb" aria-selected="false">Neighbourhoods</button>
      <button class="tab" role="tab" id="t-tg" aria-controls="v-tg" aria-selected="false">Revenue targets</button>
      <button class="tab" role="tab" id="t-gr" aria-controls="v-gr" aria-selected="false">Growth</button>
      {'<button class="tab" role="tab" id="t-now" aria-controls="v-now" aria-selected="false">Market now</button>' if now else ''}
    </div>
    <div class="tabpanel cv" role="tabpanel" id="v-map" aria-labelledby="t-map">
      <div class="mapwrap inlay brk"><img src="assets/airbnb/revpar-map.webp" alt="Map of {len(s['map']):,} Broward County entire homes as dots, coloured by RevPAR on the page's heat scale: red for the lowest, white for the middle, green for the highest. Listings crowd the coast in a dense band; inland they thin out."></div>
      <div class="cv-side map-side">
        <span class="eyebrow">RevPAR a night, entire homes</span>
        <p class="lg-axis"><span>Red: lowest</span><span>White: the middle</span><span>Green: highest</span></p>
        <ul class="legend lg-hist" aria-label="Homes in each colour, lowest RevPAR first">{leg}</ul>
        <div class="btn-row"><button class="btn primary" type="button" data-card-open data-level="nb">Cards</button><button class="btn" type="button" popovertarget="tw-map">Table</button><button class="btn" type="button" popovertarget="n-method">Method</button></div>
      </div>
    </div>
    <div class="tabpanel cv" role="tabpanel" id="v-nb" aria-labelledby="t-nb" hidden>
      <div class="cv-chart"><span class="eyebrow">Median RevPAR, the 6 strongest and 4 weakest of {s['nb_ranked']} neighbourhoods</span>{bars(nb_rows, float(nb['revpar'].max()), 'dense', (len(top), f"The {len(bot)} weakest"), nb_heat, 'nb')}</div>
      <div class="cv-side"><button class="btn primary" type="button" data-card-open data-level="nb">Cards</button><button class="btn" type="button" popovertarget="tw-nb">Table</button></div>
    </div>
    <div class="tabpanel cv" role="tabpanel" id="v-tg" aria-labelledby="t-tg" hidden>
      <div class="cv-chart"><span class="eyebrow">Share of entire homes reaching each expected revenue</span>{bars(t_rows, 100, 'tall')}</div>
      <div class="cv-side"><button class="btn" type="button" popovertarget="tw-tg">Table</button></div>
    </div>
    <div class="tabpanel cv" role="tabpanel" id="v-gr" aria-labelledby="t-gr" hidden>
      <div class="cv-chart"><span class="eyebrow">Active listings in each snapshot</span>{bars(g_rows, max(n for _, n, _ in s['growth']), 'tall')}</div>
      <div class="cv-side"><button class="btn" type="button" popovertarget="tw-gr">Table</button></div>
    </div>"""
    if now:
        break_note = ""
        if now["price_break"]:
            break_note = (f'<p class="cv-note"><b>Price basis changed.</b> The same homes list at {now["price_ratio_yoy"]:.2f} times their price of '
                          f'{html.escape(now.get("price_before", "a year before"))} ({now["price_ratio_n"]:,} entire homes), and '
                          f'{100 * now["cents_share_now"]:.0f}% of prices now carry cents, against {100 * now["cents_share_before"]:.0f}% before: '
                          "the price most likely now includes fees. So this snapshot's price is not compared with earlier ones here, "
                          "and no revenue is estimated from it.</p>")
        views += f"""
    <div class="tabpanel cv" role="tabpanel" id="v-now" aria-labelledby="t-now" hidden>
      <div class="cv-chart">
        <span class="eyebrow">The newest snapshot, {html.escape(now['asof'])}</span>
        <ul class="stats" aria-label="Key numbers, snapshot of {html.escape(now['asof'])}">
          <li class="stat"><span class="n">{now['listings']:,}</span><span class="l">active listings</span></li>
          <li class="stat"><span class="n">{now['hosts']:,}</span><span class="l">hosts</span></li>
          <li class="stat{' est' if now['price_break'] else ''}"><span class="n">{money(now['price'])}</span><span class="l">median listing price a night, entire homes{', a new price basis' if now['price_break'] else ''}</span></li>
          <li class="stat"><span class="n">{pct(now['occ'])}</span><span class="l">median occupancy, entire homes, next 365 days</span></li>
          {'' if now['price_break'] else f'<li class="stat est"><span class="n">{money(now["revpar_est"])}</span><span class="l">RevPAR a night, an estimate</span></li>'}
        </ul>
        {break_note}
        <p class="cv-note">Revenue on the other views stops at {html.escape(now['last_cal_price'])}: Inside Airbnb stopped publishing
          calendar prices after it.{'' if now['price_break'] else " The estimate is each entire home's listing price times its occupancy, a model, not a measurement."}</p>
      </div>
      <div class="cv-side"><button class="btn" type="button" popovertarget="tw-now">Table</button></div>
    </div>"""

    answer = f"""
    <ul class="verdicts">
      <li><span class="vk up" aria-hidden="true"></span><span class="vb"><span class="vt">Best bet</span><b class="vv">{html.escape(best)}</b><span class="vs">median RevPAR {money(nb.iloc[0].revpar)}</span></span></li>
      <li><span class="vk dn" aria-hidden="true"></span><span class="vb"><span class="vt">Toughest</span><b class="vv">{html.escape(worst)}</b><span class="vs">median RevPAR {money(nb.iloc[-1].revpar)}</span></span></li>
      <li><span class="vk ev" aria-hidden="true"></span><span class="vb"><span class="vt">Typical home</span><b class="vv">RevPAR {money(s['revpar'])}</b><span class="vs">{money(s['adr'])} a night, {pct(s['occ'])} booked</span></span></li>
    </ul>"""

    twins = "\n".join([
        note("tw-map", "The map as a table", table(["RevPAR a night", "Colour", "Homes"],
                                                   [(band(i, lo, hi), f"step {i + 1} of {len(legend)}, {word.get(i, 'below the middle' if i < 4 else 'above the middle')}", f"{n:,}") for i, (cls, c, lo, hi, n) in enumerate(legend)],
                                                   f"{len(s['map']):,} entire homes with a measured RevPAR, snapshot of {s['asof']}. Each home's colour is its rank among them, as a z score, on the cards' cuts: within 0.25 of the middle is white.")),
        note("tw-nb", "Neighbourhoods as a table", table(["Neighbourhood", "Homes", "Median RevPAR", "Median ADR", "Median occupancy"],
                                                          [(n, f"{int(r.n):,}", money(r.revpar), money(r.adr), pct(100 * r.occ)) for n, r in nb.iterrows()],
                                                          f"Every neighbourhood with at least {MIN_N} entire homes, snapshot of {s['asof']}.")),
        note("tw-tg", "Revenue targets as a table", table(["Expected revenue a year", "Share of entire homes"], [(f"{money(t)} or more", pct(p)) for t, p in s["targets"]],
                                                           f"{s['homes']:,} entire homes, snapshot of {s['asof']}.")),
        note("tw-gr", "Growth as a table", table(["Snapshot", "Active listings", "New since the last snapshot"], [(lab, f"{n:,}", f"{new:,}" if new is not None else "first snapshot") for lab, n, new in s["growth"]],
                                                  "Listings active in each Inside Airbnb snapshot, all room types.")),
        (note("tw-now", "Market now as a table", table(["Measure", "Value", "Measured on"],
              [("Active listings", f"{now['listings']:,}", "every listing"), ("Hosts", f"{now['hosts']:,}", "every listing"),
               ("Median listing price a night, entire homes", money(now["price"]), f"{now['price_n']:,} priced entire homes"),
               ("Median occupancy, next 365 days, entire homes", pct(now["occ"]), f"{now['occ_n']:,} entire homes"),
               *([] if now["price_break"] else [("RevPAR a night, estimate", money(now["revpar_est"]), f"{now['est_n']:,} entire homes, listing price times occupancy")])],
              f"Inside Airbnb snapshot of {now['asof']}; calendar prices last published {now['last_cal_price']}.")) if now else ""),
        note("n-method", "Method", f"""<p>Four quarterly Inside Airbnb snapshots of Broward County, {s['first']} to {s['asof']}. For each listing the
          study reads the 365-day calendar after a snapshot: booked nights, the average daily rate (ADR), occupancy, RevPAR (revenue per available
          night) and expected annual revenue. Headline numbers are medians over entire homes in the latest snapshot ({s['homes']:,} of {s['active']:,}
          active listings). Each median is taken on its own, so the median ADR times the median occupancy
          ({money(s['adr'] * s['occ'] / 100)}) is close to, but not the same as, the median RevPAR ({money(s['revpar'])}). A nightly rate counts as a price only from ${PRICE_MIN} to {money(PRICE_MAX)} and off the placeholder values hosts type on
          blocked nights ($999, $1,000, $9,999, $10,000); {s['price_dropped']:,} entire homes fall outside, so their revenue is not measured
          (their occupancy still is). A neighbourhood is ranked only with at least {MIN_N} entire homes. A multi-listing host holds {MULTI} or more active listings.</p>
          <p>Calendar availability is a proxy for bookings: a blocked night can be a stay or an owner's hold, so occupancy is an estimate, labelled as such.</p>"""),
    ])

    commit = site_commit()
    rail = f"""
    <ul class="rail" aria-label="About this data">
      <li>Inside Airbnb, {s['n_snaps']} priced snapshots</li><li>Revenue as of {s['asof_iso']}</li>{f"<li>Market now as of {now['asof_iso']}</li>" if now else ""}<li>{s['active']:,} listings, {s['hosts']:,} hosts</li><li>{f"Site commit {commit}" if commit else "Site commit: not measured"}</li>
    </ul>"""
    return stats, views, answer, twins, rail



# ── the case study as a player card (the owner, 2026-11-17: "More like the nfl/nba player cards") ──
# The page wears the card's anatomy from assets/airbnb/cards.css: a banner (disc, eyebrow, huge name, deck, chips), a
# tool strip, then a hero tile two rows tall and six tiles beside it, each with its hue rail and header strip, the big
# number, a heat gem and bead slider where the number has peers, a mini chart, and a back face with its table.
# the flip hint on every tile: two arrows passing each other (the owner, 2026-11-21), cyan and gold, never a value colour
FLIP = '<svg class="ab-flip" viewBox="0 0 48 40" aria-hidden="true" focusable="false"><path class="u" d="M8 21C8 12.7 13.2 8 21.5 8H31V2l13 11-13 11v-6h-9.5c-4.6 0-7.4 1.4-8.7 3z"/><path class="d" d="M40 19c0 8.3-5.2 13-13.5 13H17v6L4 27l13-11v6h9.5c4.6 0 7.4-1.4 8.7-3z"/></svg>'


def _zx(z):
    return 50 + 50 * max(-3.0, min(3.0, z)) / 3


def slider(z, mid=""):
    x, h = _zx(z), heat_cls(z)
    lo, w = min(50, x), abs(x - 50)
    return (f'<div class="ab-zm"><span class="trk"><span class="fill {h}" style="left:{lo:.1f}%;width:{w:.1f}%"></span><span class="mid"></span>'
            f'<span class="dot {h}" style="left:{x:.1f}%"></span></span><span class="ends"><i>weaker</i><i>{html.escape(mid)}</i><i>stronger</i></span></div>')


def gem(z):
    g = "▲" if z >= .25 else "▼" if z <= -.25 else "≈"
    return f'<span class="ab-gem {heat_cls(z)}"><span aria-hidden="true">{g}</span> {abs(z):.1f} z</span>'


def mini(vals, mark=None, label=""):
    mx = max(vals) or 1
    cols = "".join(f'<i class="{"on mk" if i == mark else "on"}" style="--hf:{max(.04, v / mx):.3f}"></i>' for i, v in enumerate(vals))
    return f'<div class="ab-mini" role="img" aria-label="{html.escape(label)}">{cols}</div>'


def ctile(cls, hue, head, small, value, per, body, back_head, back, label, extra=""):
    def hd(sm):
        sm_html = f"<small>{html.escape(sm)}</small>" if sm else ""
        return (f'<div class="ab-th"><i></i><span class="t">{html.escape(head)}</span>{sm_html}'
                f'<span class="ab-fh" aria-hidden="true">{FLIP}</span></div>')
    per_html = f'<span class="per">{html.escape(per)}</span>' if per else ""
    tv = f'<div class="ab-tv"><b>{html.escape(value)}</b>{per_html}{extra}</div>' if value else ""
    return (f'<div class="ab-t {cls}" style="--sh:{hue}" data-flip role="button" tabindex="0" aria-pressed="false" aria-label="{html.escape(label)}. Turn over for its table.">'
            f'<div class="ab-in"><div class="ab-face ab-f">{hd(small)}{tv}{body}</div>'
            f'<div class="ab-face ab-b" aria-hidden="true">{hd(back_head)}<div class="cs-back">{back}</div></div></div></div>')


def sheet(s, legend, now, commit):
    nb = s["nb"]
    zmap = dict(zip(nb.index, rank_z(nb["revpar"].tolist())))
    best, worst = nb.index[0], nb.index[-1]
    rb, rw = nb.loc[best], nb.loc[worst]
    order = list(nb["revpar"])                     # strongest first, so the best is the first column
    reach50 = dict(s["targets"])[50_000]
    n_nb = len(nb)

    def nb_list(rows, start):
        return "".join(
            f'<li><span class="cs-r">{start + i}</span><span class="cs-nm">{html.escape(n)}</span>'
            f'<b class="cs-v {heat_cls(zmap[n])}">{money(r.revpar)}</b></li>'
            for i, (n, r) in enumerate(rows.iterrows()))

    def band_txt(i, lo, hi):
        return f"{money(lo)} and up" if i == len(legend) - 1 else f"{money(lo)} to {money(hi)}"
    top_n = max(n for *_, n in legend)
    leg = "".join(
        f'<li><span class="sw {cls}" aria-hidden="true"></span><span class="lg-b">{band_txt(i, lo, hi)}</span>'
        f'<span class="hb-t" aria-hidden="true"><span class="hb-f {cls}" style="width:{100 * n / top_n:.1f}%"></span></span>'
        f'<span class="lg-n">{n:,}</span></li>' for i, (cls, c, lo, hi, n) in enumerate(legend))
    map_rows = "".join(f'<li><span class="sw {cls}" aria-hidden="true"></span><span class="cs-nm">{band_txt(i, lo, hi)}</span><b class="cs-n">{n:,}</b></li>'
                       for i, (cls, c, lo, hi, n) in enumerate(legend))
    n_map = len(s["map"])

    hero = (f'<div class="ab-t hero cs-map" style="--sh:#7CF5FF" data-flip role="button" tabindex="0" aria-pressed="false" '
            f'aria-label="The map: {n_map:,} entire homes coloured by RevPAR, red lowest, white the middle, green highest. Turn over for its table.">'
            '<div class="ab-in"><div class="ab-face ab-f"><div class="ab-th"><i></i><span class="t">Where it earns</span><small>RevPAR a night</small><span class="ab-fh" aria-hidden="true">' + FLIP + '</span></div>'
            f'<div class="cs-mapbody"><div class="mapwrap inlay"><img src="assets/airbnb/revpar-map.webp" alt="Map of {n_map:,} Broward County entire homes as dots, '
            "coloured by RevPAR on the page's heat scale: red for the lowest, white for the middle, green for the highest. Listings crowd the coast in a dense band; inland they thin out.\"></div>"
            f'<div class="cs-leg"><p class="lg-axis"><span>Red: lowest</span><span>Green: highest</span></p><ul class="legend lg-hist" aria-label="Homes in each colour, lowest RevPAR first">{leg}</ul></div></div></div>'
            '<div class="ab-face ab-b" aria-hidden="true"><div class="ab-th"><i></i><span class="t">The map as a table</span><span class="ab-fh" aria-hidden="true">' + FLIP + '</span></div>'
            f'<div class="cs-back"><ol class="cs-list cs-steps">{map_rows}</ol>'
            '<p class="cs-q cs-mapq">Nine RevPAR steps, red lowest to green highest, each home placed by its rank.</p>'
            '</div></div></div></div>')

    t_best = ctile("medal m1", "#FFC72C", "Best bet", f"1st of {n_nb}", money(rb.revpar), "RevPAR",
                   f'<p class="cs-who">{html.escape(best)}</p>{slider(zmap[best])}'
                   + mini(order, 0, f"Median RevPAR of the {n_nb} neighbourhoods, strongest first, {best} marked"),
                   f"top {min(3, n_nb)}", f'<ol class="cs-list">{nb_list(nb.head(3), 1)}</ol>',
                   f"Best bet: {best}, median RevPAR {money(rb.revpar)} a night, rank 1 of {n_nb}, z {zmap[best]:.1f}",
                   gem(zmap[best]))
    t_worst = ctile("", "#60A5FA", "Toughest", f"{n_nb}th of {n_nb}", money(rw.revpar), "RevPAR",
                    f'<p class="cs-who">{html.escape(worst)}</p>{slider(zmap[worst])}'
                    + mini(order, n_nb - 1, f"Median RevPAR of the {n_nb} neighbourhoods, strongest first, {worst} marked"),
                    f"bottom {min(3, n_nb)}", f'<ol class="cs-list">{nb_list(nb.tail(3), n_nb - 2)}</ol>',
                    f"Toughest: {worst}, median RevPAR {money(rw.revpar)} a night, rank {n_nb} of {n_nb}, z {zmap[worst]:.1f}",
                    gem(zmap[worst]))
    t_typ = ctile("", "#2DD4BF", "Typical home", "", money(s["revpar"]), "RevPAR",
                  mini([n for *_, n in legend], 4, "Entire homes in each of the map's nine RevPAR steps, the middle step marked") + f'<div class="ab-hx"><div><span>Rate</span><b>{money(s["adr"])}</b></div><div><span>Booked</span><b>{pct(s["occ"])}</b></div></div>',
                  "method",
                  f'<p class="cs-q">Each median stands alone: rate times nights booked is {money(s["adr"] * s["occ"] / 100)}, near {money(s["revpar"])}.</p>'
                  '',
                  f"Typical home: median RevPAR {money(s['revpar'])} a night, {money(s['adr'])} a night, {pct(s['occ'])} booked")
    tg_vals = [p for _, p in s["targets"]]
    t_tg = ctile("", "#FB923C", f"Clear {money(50_000, True)}", "a year", pct(reach50), "of entire homes",
                 mini(tg_vals, TARGETS.index(50_000), "Share of entire homes reaching $10k, $25k, $50k, $75k and $100k a year, $50k marked")
                 + f'<p class="cs-axis"><span>{money(TARGETS[0], True)}</span><span>{money(TARGETS[-1], True)} a year</span></p>',
                 "every target", '<p class="cs-q">' + ", ".join(f"<b>{pct(p)}</b> {money(t, True)}" for t, p in s["targets"]) + '</p>',
                 f"{pct(reach50)} of entire homes expected to clear {money(50_000, True)} a year")
    g = s["growth"]
    t_gr = ctile("", "#F472B6", "Growth", g[-1][0], f"{g[-1][1]:,}", "listings",
                 f'<p class="cs-who">{g[-1][2]:,} new<small>since {g[-2][0]}</small></p>'
                 + mini([n for _, n, _ in g], len(g) - 1, "Active listings in each snapshot, the latest marked")
                 + f'<p class="cs-axis"><span>{g[0][0]}</span><span>{g[-1][0]}</span></p>',
                 "every snapshot", f'<p class="cs-q"><b>{g[0][1]:,}</b> to <b>{g[-1][1]:,}</b>; new each quarter: '
                 + ", ".join(f"{new:,}" for _, _, new in g[1:]) + '</p>',
                 f"Growth: {g[-1][1]:,} active listings in {g[-1][0]}, {g[-1][2]:,} new since {g[-2][0]}")
    t_now = ""
    if now:
        why = (f'<p class="cs-q"><b>New price basis:</b> {now["price_ratio_yoy"]:.2f} times last year, fees most likely included; no revenue is estimated.</p>'
               ) if now["price_break"] else ""
        price_lab = "Price, new basis" if now["price_break"] else "Price a night"
        t_now = ctile("", "#CBD5E1", "Market now", "", f"{now['listings']:,}", "listings",
                      f'<div class="ab-hx"><div><span>Hosts</span><b>{now["hosts"]:,}</b></div><div><span>Booked</span><b>{pct(now["occ"])}</b></div>'
                      f'<div><span>{price_lab}</span><b>{money(now["price"])}</b></div></div>',
                      "newest",
                      why or '<p class="cs-q">The price is on the same basis as before.</p>',
                      f"Market now, {now['asof']}: {now['listings']:,} active listings, {now['hosts']:,} hosts")

    nbk = [("Market", "broward-market-analysis"), ("Data quality", "broward-pricing-consistency"), ("Segments", "broward-segmentation"), ("Investor guide", "broward-investor-guide")]
    links = "".join(f'<a class="ab-seg{" gold" if i == 3 else ""}" href="notebooks/{f}.html">{html.escape(n)}</a>' for i, (n, f) in enumerate(nbk))
    commit_li = f"Site commit {commit}" if commit else "Site commit: not measured"
    asof_li = f'Revenue as of {s["asof_iso"]}' + (f', market now {now["asof_iso"]}' if now else "")
    rail = (f'<ul class="rail" aria-label="About this data"><li>Inside Airbnb, {s["n_snaps"]} priced snapshots</li><li>{asof_li}</li>'
            f'<li>{s["active"]:,} listings, {s["hosts"]:,} hosts</li><li>{commit_li}</li></ul>')
    return f"""
<div class="sv v-sheet ab-sheet">
  <div class="ab-top">
    <header class="ab-band">
      <div class="ab-disc" aria-hidden="true">B</div>
      <div class="ab-id"><span class="eyebrow">Case study, Broward County, Florida, {html.escape(s['asof'])}</span>
        <h1 id="case-title" class="ab-name">The best and worst bets in Broward Airbnb</h1>
        <p class="ab-deck"><b class="fig">{money(s['revpar'])}</b> RevPAR a night for the <em class="how">typical</em> entire home, <b class="fig">{money(rb.revpar)}</b> at the best and <b class="fig">{money(rw.revpar)}</b> at the toughest.</p></div>
      <div class="ab-chips"><span class="ab-chip"><i>Homes</i><b>{s['homes']:,}</b></span><span class="ab-chip"><i>Revenue</i><b>{money(s['revenue'], True)}</b><small>a year</small></span>
        <span class="ab-chip"><i>10+ hosts</i><b>{pct(s['multi_share'])}</b><small>of listings</small></span></div>
    </header>
  </div>
  <div class="ab-fs"><span class="cs-lab">Notebooks</span><div class="ab-segs cs-nbw">{links}</div><button type="button" class="ab-seg cs-nbn" popovertarget="n-nbk">Open a notebook</button>
    <div class="ab-segs cs-open"><button type="button" class="ab-seg cs-cards" data-card-open data-level="nb">Cards</button><button type="button" class="ab-seg" data-card-open data-level="nb" data-view="h2h">Head to head</button>
      <button type="button" class="ab-seg" popovertarget="n-tables">Tables and method</button></div></div>
  <div id="n-tables" popover class="note"><h3>Every number as a table</h3><div class="btn-row">
    <button class="btn" type="button" popovertarget="tw-map">The map</button><button class="btn" type="button" popovertarget="tw-nb">All {n_nb} neighbourhoods</button>
    <button class="btn" type="button" popovertarget="tw-tg">Revenue targets</button><button class="btn" type="button" popovertarget="tw-gr">Growth</button>
    {'<button class="btn" type="button" popovertarget="tw-now">Market now</button>' if now else ''}<button class="btn primary" type="button" popovertarget="n-method">Method</button></div>
    <button class="btn" popovertarget="n-tables" popovertargetaction="hide">Close</button></div>
  <div id="n-nbk" popover class="note"><h3>The notebooks</h3><div class="btn-row">{links.replace('class="ab-seg', 'class="btn')}</div>
    <button class="btn" popovertarget="n-nbk" popovertargetaction="hide">Close</button></div>
  <div class="ab-tiles cs-tiles">{hero}{t_best}{t_worst}{t_typ}{t_tg}{t_gr}{t_now}</div>
  {rail}
</div>"""


def rentals_types(sa_root: pathlib.Path) -> dict:
    """Each listing's, host's and neighbourhood's type from the Rentals Archetypes study (SportsAnalytics rentals/,
    issue 718), run read-only from its own folder: never a copy of its code. Returns, for each of the three families,
    its type names, each unit's type as an index, and each type's hold-test status."""
    import os
    import sys
    os.environ.setdefault("SA_NO_DB", "1")
    sys.path.insert(0, str(sa_root))
    from rentals import archetypes
    model = archetypes.build()
    out = {"asof": model.get("asof")}
    for key, seg in (("lt", "listings"), ("ht", "hosts"), ("nt", "neighbourhoods")):
        s = model[seg]
        names = [t["name"] for t in s["types"]]
        out[key] = {"names": names, "map": {r["id"]: names.index(r["type"]) for r in s["rows"] if r["type"] in names},
                    "hold": [((t.get("hold") or {}).get("status") or "not measured") for t in s["types"]],
                    "held": [[round(float((t.get("hold") or {}).get(k) or 0), 3) for k in ("held", "chance")] if t.get("hold") else None
                             for t in s["types"]]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=pathlib.Path)
    ap.add_argument("--now", type=pathlib.Path, help="the pipeline's tableau_listings.csv, for the newest snapshot")
    ap.add_argument("--models", type=pathlib.Path, help="bnbscope's processed folder for the region, for the cards' Models family")
    ap.add_argument("--rentals", type=pathlib.Path, help="the SportsAnalytics folder: its Rentals Archetypes types join the mix (issue 812)")
    ap.add_argument("--raw", type=pathlib.Path, help="the Inside Airbnb listings files (<date>_listings.csv.gz): each listing's Airbnb id, cover picture and newest snapshot, on its card")
    a = ap.parse_args()
    s = build(load(a.src))
    now = market_now(a.now) if a.now else None
    legend = draw_map(s["map"], ROOT / "assets" / "airbnb" / "revpar-map.webp")
    stats, views, answer, twins, rail = page(s, legend, now)
    body = sheet(s, legend, now, site_commit())
    out = f"""<!-- generated by tools/airbnb_build.py from the study's processed outputs; do not edit by hand -->
```{{=html}}
{body}
{twins}
<link rel="stylesheet" href="assets/airbnb/cards.css">
<dialog id="ab-cards" class="ab-card" data-src="assets/airbnb/cards.json" aria-labelledby="ab-title">
  <div class="ab-top">
    <header class="ab-band"><p id="ab-title" class="ab-name" role="heading" aria-level="2">Cards</p></header>
    <div class="ab-views" role="group" aria-label="View">
      <button type="button" class="ab-view" data-view="card" aria-pressed="true">Card</button>
      <button type="button" class="ab-view" data-view="h2h" aria-pressed="false">Head to head</button>
      <button type="button" class="ab-close">Close</button>
    </div>
  </div>
  <div class="ab-fs"></div>
  <div class="ab-body"></div>
</dialog>
<script src="assets/sv.js"></script>
<script src="assets/airbnb/cards.js"></script>
```
"""
    (ROOT / "_airbnb_generated.qmd").write_text(out, encoding="utf-8")
    reach50 = dict(s["targets"])[50_000]
    home = f"""<!-- generated by tools/airbnb_build.py; do not edit by hand -->
```{{=html}}
    <a class="feature case-feature" href="airbnb.html">
      <div class="cf-body">
        <div class="pic map"><img src="assets/airbnb/revpar-map.webp" alt="Map of Broward County entire homes as dots coloured by revenue per available night, red for the lowest, white for the middle and green for the highest, crowded in a dense band along the coast."></div>
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
    (ROOT / "assets" / "airbnb" / "summary.json").write_text(json.dumps({k: v for k, v in s.items() if k not in ("nb", "map", "homes_df")}, indent=1, default=str), encoding="utf-8")
    from airbnb_cards import build_cards
    cards = build_cards(s["homes_df"], s["asof"], MIN_N, a.models, a.raw)
    if a.models:
        # the guest cards (SportsAnalytics issue 808) and each market's review years, from the study's reviews
        from airbnb_guests import build_guests
        g = build_guests(a.models, getattr(build_cards, "listing_types", None), cards["seg_names"], cards["host_types"],
                         rentals_types(a.rentals) if a.rentals else None)
        cards["nb_years"] = g.pop("nb_years")
        cards["guests"] = g
    (ROOT / "assets" / "airbnb" / "cards.json").write_text(json.dumps(cards, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    print("cards:", {k: len(v) for k, v in cards["levels"].items()}, "listings", len(cards["listings"]), "segments", [x["name"] for x in cards["levels"]["seg"]])
    if cards.get("links"):
        L = cards["links"]
        print(f"links: of {L['of']:,} listings, {L['listed']:,} still listed on {L['snaps'][-1]}, {L['bookable']:,} of them bookable; {L['pics']:,} with a cover picture")
    print("as of", s["asof"], "homes", s["homes"], "revpar", s["revpar"], "best", s["nb"].index[0], "worst", s["nb"].index[-1])


if __name__ == "__main__":
    main()
