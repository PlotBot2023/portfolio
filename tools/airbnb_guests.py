"""The case study's guest cards: one card for each repeat guest (a reviewer of several Broward homes), coded, never named
(PlotBot2023/SportsAnalytics issue 808).

    python tools/airbnb_guests.py --models <the study's processed folder for Broward>     # adds the guest level to cards.json

The study's files it reads (on the owner's PC only, kept out of git by the study's ignore rules):
  - processed/<region>/reviews_cleaned.parquet: review id, listing id, reviewer id and date only (never the comment);
  - interim/<region>/review_flags.parquet: the study's per-review flags (BrowardAirbnbV2 pull request 4, rules version 3);
  - processed/<region>/listings_cleaned.parquet: each listing's room type, price, place and host.

Privacy (issue 808, the site is public and Inside Airbnb's reviews file is public too, so a card must not match a row of it):
  1. codes only (G0001 ...); no name, reviewer id, Airbnb id, link or review text is ever written;
  2. bands only: no exact count and no date or year, so a card's numbers cannot be sorted back to one reviewer;
  3. a crowd of at least CROWD: a guest gets a card only when that many guests share its banded profile (BANDED);
  4. the code is not a rank: cards are ordered by a secret kept on this PC (SECRET_FILE), never in git;
  5. no list of the homes, no neighbourhood names and no link to a listing or host card.
build_guests() refuses to return a block that breaks 2 or 3.

Types, three families (each a rule on plain features, or k-means named by rules, and each with a split-half hold test:
a guest's early reviews and late reviews typed apart, kept against chance):
  - where they stay: the distance of their stays from the beach;
  - what they pay: the price third of the homes they pick, thirds of all stays (not of all listings);
  - how they travel: k-means (6 groups, seed 42) on return stays, price, whole homes, praise, complaints and review length.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import secrets

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
MIN_HOMES = 5          # a guest reviewed at least this many different homes (the host level's line, HOST_MIN)
CROWD = 10             # at least this many guests share a card's banded profile
MIN_TEXT = 5           # praise and complaints need at least this many English reviews
SECRET_FILE = pathlib.Path(os.environ.get("LOCALAPPDATA", pathlib.Path.home())) / "SportsAnalytics" / "portfolio" / "guest_order_secret.txt"
ASPECTS = ("cleanliness", "location", "communication", "value", "noise", "checkin", "beach", "pool", "hot_tub", "parking")
ASPECT_WORDS = {"cleanliness": "cleanliness", "location": "location", "communication": "the host's replies", "value": "value",
                "noise": "noise", "checkin": "check-in", "beach": "the beach", "pool": "the pool", "hot_tub": "the hot tub", "parking": "parking"}

# the bands a card shows: (key, label, cut points on the raw value; a value at or above a cut moves up one band)
BANDS = {
    "homes": ("Homes reviewed", ["5", "6 to 7", "8 to 9", "10 to 14", "15 or more"], [6, 8, 10, 15]),
    "years": ("Years active", ["1 to 2", "3 to 4", "5 or more"], [3, 5]),
    "nb": ("Neighbourhoods", ["1 to 2", "3 to 4", "5 or more"], [3, 5]),
    "beach": ("From the beach", ["under 1 km", "1 to 5 km", "5 km or more"], [1, 5]),
    "price": ("Price tier", ["budget", "middle", "premium"], None),          # cut on the stay-weighted thirds
    "ret": ("Return stays", ["none", "some", "often"], [1e-9, 0.2]),
    "praise": ("Praise", ["none", "some", "often"], [1e-9, 0.25]),
    "compl": ("Complaints", ["none", "some"], [1e-9]),
}
BANDED = ["homes", "years", "nb", "beach", "price", "ret"]      # the countable profile the crowd rule is checked on
BEHAVIOUR_RULES = [("The Tough Critic", "compl", 1, 1.5), ("The Returner", "rep", 1, 1.5), ("The Room Renter", "entire", -1, 1.2),
                   ("The Cheerleader", "praise", 1, 1.2), ("The Splurger", "price", 1, 0.7)]
BEHAVIOUR_FALLBACK = "The Easy Guest"
BEHAVIOUR_MEANING = {"The Tough Critic": "complaints in many reviews, and the longest reviews",
                     "The Returner": "comes back to a home they stayed in before",
                     "The Room Renter": "rooms more than whole homes, at budget prices",
                     "The Cheerleader": "praise in most reviews", "The Splurger": "premium homes, longer reviews",
                     "The Easy Guest": "no single trait stands out: short, quiet reviews"}
LOC_TYPES = [("The Beachgoer", "most stays under 1 km from the beach"), ("The Short Walk", "most stays 1 to 5 km from the beach"),
             ("The Inlander", "most stays 5 km or more from the beach"), ("The Roamer", "no distance holds most stays")]
PRICE_TYPES = [("The Budget Guest", "most stays in the cheapest third"), ("The Middle Guest", "most stays in the middle third"),
               ("The Premium Guest", "most stays in the dearest third"), ("The Mixer", "no third holds most stays")]
MOST = 0.6            # "most stays": a type rule's share


def band_of(v, cuts):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else int(sum(v >= c for c in cuts))


def read_reviews(proc: pathlib.Path) -> pd.DataFrame:
    """One row a review id (the newest scrape's copy, the study's rule), without the comment column."""
    import pyarrow.parquet as pq
    t = pq.read_table(proc / "reviews_cleaned.parquet", columns=["review_id", "listing_id", "reviewer_id", "date", "snapshot_date"]).to_pandas()
    return t.sort_values("snapshot_date").drop_duplicates("review_id", keep="last").drop(columns="snapshot_date").reset_index(drop=True)


def read_listings(proc: pathlib.Path) -> pd.DataFrame:
    """One row a listing: its newest room type, neighbourhood, place and host; its price rank is the median of its rank
    inside each snapshot (so the September 2026 change of price basis moves no one), and its distance from the beach."""
    l = pd.read_parquet(proc / "listings_cleaned.parquet", columns=["listing_id", "snapshot_date", "room_type", "neighbourhood", "host_id",
                                                                    "bedrooms", "price", "latitude", "longitude"])
    l["pr"] = l.groupby("snapshot_date")["price"].rank(pct=True, method="average")
    pr = l.groupby("listing_id")["pr"].median()
    last = l.sort_values("snapshot_date").drop_duplicates("listing_id", keep="last").set_index("listing_id")
    out = last[["room_type", "neighbourhood", "host_id", "bedrooms", "latitude", "longitude"]].join(pr)
    # the beach line: the east-most listings in each 0.01-degree band of latitude (the coast runs north to south)
    band = (out["latitude"] * 100).round()
    east = out.groupby(band)["longitude"].quantile(.995).rolling(5, center=True, min_periods=1).max()
    out["km"] = ((band.map(east) - out["longitude"]).clip(lower=0) * 111.32 * np.cos(np.radians(out["latitude"])))
    out["entire"] = (out["room_type"] == "Entire home/apt").astype(float)
    return out.drop(columns=["latitude", "longitude"])


def secret() -> bytes:
    if not SECRET_FILE.exists():
        SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        SECRET_FILE.write_text(secrets.token_hex(32), encoding="utf-8")
    return SECRET_FILE.read_text(encoding="utf-8").strip().encode()


def _hold(early: pd.Series, late: pd.Series) -> dict:
    both = pd.concat([early.rename("a"), late.rename("b")], axis=1).dropna()
    same = both["a"] == both["b"]
    chance = sum((both["a"] == k).mean() * (both["b"] == k).mean() for k in set(both["a"]) | set(both["b"]))
    out = {"n": int(len(both)), "kept": round(float(same.mean()), 3), "chance": round(float(chance), 3),
           "se": round(float(same.std() / np.sqrt(len(both))), 3), "by": {}}
    for k in sorted(set(both["a"])):
        m = both["a"] == k
        out["by"][k] = {"n": int(m.sum()), "kept": round(float((both["b"][m] == k).mean()), 3), "chance": round(float((both["b"] == k).mean()), 3),
                        "se": round(float((both["b"][m] == k).std() / np.sqrt(m.sum())), 3)}
    return out


def guest_table(r: pd.DataFrame, c1: float, c2: float) -> pd.DataFrame:
    """One row a reviewer from their review rows (each with its home's facts and the review's flags)."""
    r = r.assign(_b=(r["km"] < 1).astype(float), _i=(r["km"] >= 5).astype(float),
                 _lo=(r["pr"] < c1).astype(float).where(r["pr"].notna()), _hi=(r["pr"] >= c2).astype(float).where(r["pr"].notna()))
    en = r[r["english"].fillna(False).astype(bool)]
    g = r.groupby("reviewer_id")
    t = pd.DataFrame({"n_rev": g.size(), "n_homes": g["listing_id"].nunique(), "n_nb": g["neighbourhood"].nunique(),
                      "n_years": g["year"].nunique(), "rep": g["rep"].mean(), "pr": g["pr"].median(), "km": g["km"].median(),
                      "entire": g["entire"].mean(), "n_priced": g["pr"].count(),
                      "beach_s": g["_b"].mean(), "inland_s": g["_i"].mean(), "bud_s": g["_lo"].mean(), "prem_s": g["_hi"].mean()})
    ge = en.groupby("reviewer_id")
    t["n_en"] = ge.size().reindex(t.index).fillna(0).astype(int)
    for c in ("praise", "complaint"):
        t[c] = ge[c].mean().reindex(t.index)
    t["sent"] = ge["n_sentences"].mean().reindex(t.index)
    for a in ASPECTS:
        t[f"a_{a}"] = ge[f"m_{a}"].sum().reindex(t.index).fillna(0)
    t["mid_s"] = 1 - t["bud_s"] - t["prem_s"]
    t["near_s"] = 1 - t["beach_s"] - t["inland_s"]
    return t


def loc_type(t: pd.DataFrame) -> pd.Series:
    return pd.Series(np.select([t["beach_s"] >= MOST, t["near_s"] >= MOST, t["inland_s"] >= MOST], [0, 1, 2], 3), index=t.index)


def price_type(t: pd.DataFrame) -> pd.Series:
    s = pd.Series(np.select([t["bud_s"] >= MOST, t["mid_s"] >= MOST, t["prem_s"] >= MOST], [0, 1, 2], 3), index=t.index).astype(float)
    return s.where(t["n_priced"] >= 2)


def behaviour_features(t: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"rep": t["rep"], "price": t["pr"], "entire": t["entire"], "praise": t["praise"].fillna(0),
                         "compl": t["complaint"].fillna(0).clip(upper=.5), "detail": np.log1p(t["sent"].fillna(0))}, index=t.index)


def mix_block(r: pd.DataFrame, t: pd.DataFrame, lt: pd.DataFrame, loc_names, price_names, beh_names, seg_names, host_names) -> dict:
    """Every type across every other type (SportsAnalytics issue 812). Families: the guest's place, price and travel types
    (guests of 2 or more homes) and the home's ML segment and host size (the homes of the cards' calendar snapshot).
    A pair of guest families counts guests; a pair with a home family counts stays (reviews by typed guests of typed
    homes). Each cell: its count, its share of the row type, the share of all (the county's), and a z of its log lift over
    the pair's spread (0 at the county's own share), for the cyan-to-pink tendency scale. A cell under CROWD is not shown (null)."""
    fams = [("loc", "Where guests stay", list(loc_names), "guest"), ("price", "What guests pay", list(price_names), "guest"),
            ("beh", "How guests travel", list(beh_names), "guest"), ("seg", "Home segment", list(seg_names), "home"),
            ("host", "Host size", list(host_names), "home")]
    g = t[["t_loc", "t_price", "t_beh"]].rename(columns=lambda c: c[2:])
    stays = r[["reviewer_id", "listing_id"]].merge(g, left_on="reviewer_id", right_index=True).merge(lt, on="listing_id")
    out = {"fams": [{"key": k, "l": l, "names": n, "unit": u} for k, l, n, u in fams], "pairs": {}}
    for a, _, an, au in fams:
        for b, _, bn, bu in fams:
            if a == b:
                continue
            src = g if au == "guest" and bu == "guest" else stays
            d = src[[a, b]].dropna().astype(int)
            ct = pd.crosstab(d[a], d[b]).reindex(index=range(len(an)), columns=range(len(bn)), fill_value=0)
            n = ct.to_numpy()
            county = n.sum(0) / max(n.sum(), 1)
            share = n / np.maximum(n.sum(1, keepdims=True), 1)
            lift = np.log(np.where((n >= CROWD) & (county > 0), share / np.where(county > 0, county, 1), np.nan))
            rms = float(np.sqrt(np.nanmean(lift ** 2))) if np.isfinite(lift).any() else 0.0
            z = lift / rms if rms > 0 else lift * 0      # 0 at the county's own share; the pair's spread sets the steps
            keep = n >= CROWD
            out["pairs"][f"{a}|{b}"] = {
                "unit": "guests" if src is g else "stays", "rows": n.sum(1).astype(int).tolist(),
                "n": np.where(keep, n, -1).astype(int).tolist(),
                "share": np.where(keep, np.round(100 * share, 1), np.nan).tolist(),
                "county": np.round(100 * county, 1).tolist(),
                "z": np.where(keep, np.round(z, 2), np.nan).tolist()}
    # JSON has no NaN: a hidden cell is null
    for v in out["pairs"].values():
        for k in ("share", "z"):
            v[k] = [[None if (x != x) else x for x in row] for row in v[k]]
    return out


def build_guests(models_dir, listing_types: pd.DataFrame | None = None, seg_names=None, host_names=None) -> dict:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    proc = pathlib.Path(models_dir)
    interim = proc.parents[1] / "interim" / proc.name
    rv = read_reviews(proc)
    ls = read_listings(proc)
    fl = pd.read_parquet(interim / "review_flags.parquet", columns=["review_id", "english", "n_sentences", "praise", "complaint", *[f"m_{a}" for a in ASPECTS]])
    r = rv.merge(ls, left_on="listing_id", right_index=True, how="inner").merge(fl, on="review_id", how="left")
    r = r.sort_values(["reviewer_id", "listing_id", "date", "review_id"])
    r["rep"] = r.duplicated(["reviewer_id", "listing_id"]).astype(float)        # the study's repeat-guest rule
    r["year"] = pd.to_datetime(r["date"]).dt.year
    c1, c2 = (float(x) for x in r["pr"].quantile([1 / 3, 2 / 3]))                  # thirds of all stays
    asof = str(pd.to_datetime(r["date"]).max().date())
    first_year = int(r["year"].min())
    homes_all = r.groupby("reviewer_id")["listing_id"].nunique()
    overall = {"reviewers": int(len(homes_all)), "reviews": int(len(r)),
               "by_homes": [["1 home", int((homes_all == 1).sum())], ["2 homes", int((homes_all == 2).sum())],
                            ["3 to 4", int(homes_all.between(3, 4).sum())], [f"{MIN_HOMES} or more", int((homes_all >= MIN_HOMES).sum())]]}

    multi = homes_all[homes_all >= 2].index
    t = guest_table(r[r["reviewer_id"].isin(multi)], c1, c2)
    county_asp = {a: float(r.loc[r["english"].fillna(False).astype(bool), f"m_{a}"].mean()) for a in ASPECTS}
    county_text = {"praise": float(r.loc[r["english"].fillna(False).astype(bool), "praise"].mean()),
                   "complaint": float(r.loc[r["english"].fillna(False).astype(bool), "complaint"].mean())}

    # how they travel: fitted on every guest of 2 or more homes with 2 or more English reviews and a price
    fit_rows = t[(t["n_en"] >= 2) & t["pr"].notna()]
    X = behaviour_features(fit_rows)
    mu, sd = X.mean(), X.std()
    Z = ((X - mu) / sd).to_numpy()
    km = KMeans(6, n_init=50, random_state=42).fit(Z)
    sample = np.random.default_rng(42).choice(len(Z), min(20_000, len(Z)), replace=False)
    sil = float(silhouette_score(Z[sample], km.labels_[sample]))
    cent = pd.DataFrame(km.cluster_centers_, columns=X.columns)
    names, used = {}, set()
    for k in range(len(cent)):
        for nm, f, sign, thr in BEHAVIOUR_RULES:
            if nm not in used and sign * cent.loc[k, f] >= thr:
                names[k] = nm; used.add(nm); break
        else:
            names[k] = BEHAVIOUR_FALLBACK
    beh_names = list(dict.fromkeys(nm for nm, *_ in BEHAVIOUR_RULES if nm in used)) + ([BEHAVIOUR_FALLBACK] if BEHAVIOUR_FALLBACK in names.values() else [])
    beh_idx = {nm: i for i, nm in enumerate(beh_names)}

    def behaviour(tt: pd.DataFrame) -> pd.Series:
        ok = tt["pr"].notna()
        lab = km.predict(((behaviour_features(tt[ok]) - mu) / sd).fillna(0).to_numpy())
        return pd.Series([beh_idx[names[k]] for k in lab], index=tt.index[ok]).reindex(tt.index)

    cards = t[t["n_homes"] >= MIN_HOMES].copy()
    cards["t_loc"], cards["t_price"], cards["t_beh"] = loc_type(cards), price_type(cards), behaviour(cards)

    # split-half hold: each card guest's reviews split by date into an early and a late half, both typed by the same rules
    rc = r[r["reviewer_id"].isin(cards.index)].sort_values(["reviewer_id", "date", "review_id"])
    i = rc.groupby("reviewer_id").cumcount()
    late = i >= rc.groupby("reviewer_id")["review_id"].transform("size") / 2
    halves = [guest_table(rc[~late], c1, c2), guest_table(rc[late], c1, c2)]
    holds = {"loc": _hold(loc_type(halves[0]), loc_type(halves[1])), "price": _hold(price_type(halves[0]), price_type(halves[1])),
             "beh": _hold(behaviour(halves[0]), behaviour(halves[1]))}

    # the bands
    def bands(tt: pd.DataFrame) -> pd.DataFrame:
        b = pd.DataFrame(index=tt.index)
        b["homes"] = [band_of(v, BANDS["homes"][2]) for v in tt["n_homes"]]
        b["years"] = [band_of(v, BANDS["years"][2]) for v in tt["n_years"]]
        b["nb"] = [band_of(v, BANDS["nb"][2]) for v in tt["n_nb"]]
        b["beach"] = [band_of(v, BANDS["beach"][2]) for v in tt["km"]]
        b["price"] = [band_of(v, [c1, c2]) for v in tt["pr"]]
        b["ret"] = [band_of(v, BANDS["ret"][2]) for v in tt["rep"]]
        text = tt["n_en"] >= MIN_TEXT
        b["praise"] = [band_of(v, BANDS["praise"][2]) if ok else None for v, ok in zip(tt["praise"], text)]
        b["compl"] = [band_of(v, BANDS["compl"][2]) if ok else None for v, ok in zip(tt["complaint"], text)]
        return b

    b = bands(cards)
    prof = b[BANDED].astype("Int64").astype(str).agg("|".join, axis=1)
    crowd = prof.map(prof.value_counts())
    keep = crowd >= CROWD
    kept_n, drop_n = int(keep.sum()), int((~keep).sum())
    cards, b = cards[keep], b[keep]

    # what they talk about: up to three aspects they mention at least twice and at twice the county's rate or more
    def talk(row) -> int:
        if row["n_en"] < MIN_TEXT:
            return 0
        ratio = [(row[f"a_{a}"] / row["n_en"] / max(county_asp[a], 1e-9), j) for j, a in enumerate(ASPECTS) if row[f"a_{a}"] >= 2]
        return sum(1 << j for r_, j in sorted(ratio, reverse=True)[:3] if r_ >= 2)

    key = secret()
    order = sorted(cards.index, key=lambda rid: (-b.loc[rid, "homes"], hashlib.sha256(key + str(rid).encode()).hexdigest()))
    cols = ["homes", "years", "nb", "beach", "price", "ret", "praise", "compl", "t_loc", "t_price", "t_beh", "talk"]
    rows = []
    for rid in order:
        x, c = b.loc[rid], cards.loc[rid]
        rows.append([*(None if pd.isna(x[k]) else int(x[k]) for k in ("homes", "years", "nb", "beach", "price", "ret", "praise", "compl")),
                     int(c["t_loc"]), None if pd.isna(c["t_price"]) else int(c["t_price"]), None if pd.isna(c["t_beh"]) else int(c["t_beh"]), talk(c)])

    # the checks of the privacy rule, on what is about to be written
    out_rows = pd.DataFrame(rows, columns=cols)
    pc = out_rows[BANDED].astype("Int64").astype(str).agg("|".join, axis=1).value_counts()
    assert pc.min() >= CROWD, "a published guest profile is shared by fewer guests than the crowd rule allows"
    assert all(isinstance(v, (int, type(None))) and (v is None or 0 <= v < 1 << 10) for row in rows for v in row), "a guest row holds more than bands"

    def counts(cat, n):
        return [int((out_rows[cat] == i).sum()) for i in range(n)]
    pool = lambda tt, n: [int((tt == i).sum()) for i in range(n)]
    return {
        "asof": asof, "first_year": first_year, "min_homes": MIN_HOMES, "crowd": CROWD, "min_text": MIN_TEXT,
        "kept": kept_n, "left_off": drop_n, "overall": overall,
        "cols": cols, "rows": rows,
        "bands": {k: {"l": v[0], "names": v[1]} for k, v in BANDS.items()},
        "hist": {k: counts(k, len(BANDS[k][1])) for k in BANDS},
        "price_cut": [round(c1, 3), round(c2, 3)],
        "aspects": [ASPECT_WORDS[a] for a in ASPECTS],
        "county": {"praise": round(100 * county_text["praise"], 1), "complaint": round(100 * county_text["complaint"], 1),
                   "aspects": [round(100 * county_asp[a], 1) for a in ASPECTS]},
        "types": {
            "loc": {"l": "Where they stay", "names": [n for n, _ in LOC_TYPES], "why": [w for _, w in LOC_TYPES], "n": counts("t_loc", 4),
                    "all": pool(loc_type(t), 4), "hold": holds["loc"]},
            "price": {"l": "What they pay", "names": [n for n, _ in PRICE_TYPES], "why": [w for _, w in PRICE_TYPES], "n": counts("t_price", 4),
                      "all": pool(price_type(t), 4), "hold": holds["price"]},
            "beh": {"l": "How they travel", "names": beh_names, "why": [BEHAVIOUR_MEANING[n] for n in beh_names], "n": counts("t_beh", len(beh_names)),
                    "all": pool(behaviour(fit_rows), len(beh_names)), "hold": holds["beh"],
                    "method": f"k-means, 6 groups, seed 42, on return stays, price, whole homes, praise, complaints and review length, "
                              f"fitted on {len(fit_rows):,} guests of 2 or more homes; silhouette {sil:.2f}"},
        },
        "pool_all": int(len(t)),
        "mix": (mix_block(r, t.assign(t_loc=loc_type(t), t_price=price_type(t), t_beh=behaviour(t)), listing_types,
                          [n for n, _ in LOC_TYPES], [n for n, _ in PRICE_TYPES], beh_names, seg_names, host_names)
                if listing_types is not None else None),
        # each market's own review span, for the neighbourhood cards' Years line (years only, never a date)
        "nb_years": {str(k): [int(v.min()), int(v.max())] for k, v in r.groupby("neighbourhood")["year"]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True, type=pathlib.Path, help="the study's processed folder for the region")
    a = ap.parse_args()
    g = build_guests(a.models)
    path = ROOT / "assets" / "airbnb" / "cards.json"
    cards = json.loads(path.read_text(encoding="utf-8"))
    cards["nb_years"] = g.pop("nb_years")
    cards["guests"] = g
    path.write_text(json.dumps(cards, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    print("guest cards", g["kept"], "left off by the crowd rule", g["left_off"], "of", g["kept"] + g["left_off"],
          {k: v["n"] for k, v in g["types"].items()}, {k: (v["hold"]["kept"], v["hold"]["chance"], v["hold"]["se"]) for k, v in g["types"].items()})


if __name__ == "__main__":
    main()
