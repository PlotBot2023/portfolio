"""The case study's cards: one card per neighbourhood, ML segment, host and listing, from the same measured calendar data
as the rest of the page (entire homes, the latest snapshot with calendar prices).

Writes `assets/airbnb/cards.json`, read by `assets/airbnb/cards.js`. Privacy: hosts and listings carry codes, never a
name, an Airbnb id or a link, because most hosts are private people (the site is public and hardened against scraping).

Levels and pools (a card's z is its rank among the cards of its own level, turned into a normal score):
  - neighbourhood: every neighbourhood with at least MIN_N entire homes;
  - segment: a Gaussian mixture, K = 4, seed 42, on log ADR, occupancy and bedrooms (standardised), named in plain
    words from each group's medians against the county's;
  - host: every host with at least HOST_MIN entire homes, coded H001, H002 ... by number of homes;
  - listing: every entire home with measured RevPAR, coded by its RevPAR rank in the county.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HOST_MIN = 5
BINS = 16
METRICS = ["revpar", "adr", "occ", "rev", "rev_bed"]          # the histogram metrics (a home has one value of each)
# the earlier bnbscope models (its 22 September 2026 run), joined by listing id; a separate family on the cards
MODEL_METRICS = ["churn", "resid", "mood", "cap", "noi"]


def load_models(d) -> pd.DataFrame:
    """One row per listing id from bnbscope's processed outputs: churn probability, the XGBoost residual (actual minus
    predicted RevPAR), the anomaly flag, VADER review sentiment (latest snapshot), NOI and cap rate (latest snapshot)."""
    import pathlib
    d = pathlib.Path(d)
    churn = pd.read_parquet(d / "churn_predictor.parquet", columns=["listing_id", "churn_proba"])
    xgb = pd.read_parquet(d / "xgboost_revpar.parquet", columns=["listing_id", "residual"])
    an = pd.read_parquet(d / "anomaly_detection.parquet", columns=["listing_id", "is_anomaly"])
    se = pd.read_parquet(d / "features" / "review_sentiment.parquet", columns=["listing_id", "snapshot_date", "sentiment_mean"])
    se = se.sort_values("snapshot_date").drop_duplicates("listing_id", keep="last")
    inv = pd.read_parquet(d / "investment_metrics.parquet", columns=["listing_id", "snapshot_date", "noi", "home_value"])
    inv = inv.sort_values("snapshot_date").drop_duplicates("listing_id", keep="last")
    inv["cap"] = 100 * inv["noi"] / inv["home_value"].where(inv["home_value"] > 0)
    m = churn.drop_duplicates("listing_id").rename(columns={"churn_proba": "churn"})
    m["churn"] = 100 * m["churn"]
    an = an.drop_duplicates("listing_id")
    an["anom"] = 100.0 * an["is_anomaly"].astype(float)
    for t in (xgb.drop_duplicates("listing_id").rename(columns={"residual": "resid"}), an[["listing_id", "anom"]],
              se.rename(columns={"sentiment_mean": "mood"})[["listing_id", "mood"]], inv[["listing_id", "noi", "cap"]]):
        m = m.merge(t, on="listing_id", how="outer")
    return m


def num(v, d=2):
    """A JSON-safe number: None for a missing value (JSON has no NaN)."""
    v = float(v)
    return None if np.isnan(v) else round(v, d)


# a segment's title, by its rate and its calendar against the county's medians (a rule, so a refit renames itself)
MONIKER = {("premium", "busy"): "Gold Mines", ("premium", "quiet"): "Showpieces",
           ("mid-rate", "busy"): "Workhorses", ("mid-rate", "steady"): "Steady Earners", ("mid-rate", "quiet"): "Sleepers",
           ("budget", "busy"): "Value Packers", ("budget", "steady"): "Budget Regulars", ("budget", "quiet"): "Idle Rooms"}


def _segments(h: pd.DataFrame, seed: int = 42) -> tuple[pd.Series, list[str], dict]:
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler
    x = np.column_stack([np.log1p(h["adr"]), h["occ"], h["bedrooms"].fillna(h["bedrooms"].median()).clip(upper=8)])
    xs = StandardScaler().fit_transform(x)
    gm = GaussianMixture(n_components=4, covariance_type="full", random_state=seed, n_init=3).fit(xs)
    lab = pd.Series(gm.predict(xs), index=h.index)
    med_adr, med_occ = h["adr"].median(), h["occ"].median()
    names, descs = {}, {}
    for k, g in h.groupby(lab):
        b = g["bedrooms"].median()
        size = "Small" if b <= 1 else "Mid-size" if b <= 3 else "Large"
        a, o = g["adr"].median() / med_adr, g["occ"].median() / max(med_occ, 1e-9)
        rate = "premium" if a >= 1.25 else "budget" if a <= .8 else "mid-rate"
        cal = "busy" if o >= 1.3 else "quiet" if o <= .7 else "steady"
        names[k] = MONIKER[(rate, cal)] if (rate, cal) != ("premium", "steady") else ("Trophy Homes" if size == "Large" else "Boutique Stays")
        descs[k] = f"{size} homes, {rate.replace('mid-rate', 'mid-range')} rates, {cal} calendars"
    seen: dict[str, int] = {}
    names = {k: f"The {v}" for k, v in names.items()}
    for k in sorted(names, key=lambda k: -h.loc[lab == k, "revpar"].median()):      # strongest first
        n = names[k]; seen[n] = seen.get(n, 0) + 1
        if seen[n] > 1:
            names[k] = f"{n} ({seen[n]})"
    order = sorted(names, key=lambda k: -h.loc[lab == k, "revpar"].median())
    remap = {k: i for i, k in enumerate(order)}
    meta = {"method": "Gaussian mixture, 4 groups, seed 42, on log ADR, occupancy and bedrooms (standardised)",
            "bic": round(float(gm.bic(xs)), 1)}
    return lab.map(remap), [names[k] for k in order], meta | {"desc": [descs[k] for k in order]}


def build_cards(homes: pd.DataFrame, asof: str, min_n: int, models_dir=None) -> dict:
    """homes: entire homes of the latest snapshot with listing_id, neighbourhood_cleansed, host_id, adr, occupancy
    (0 to 1), revpar, expected_revenue, bedrooms, host_is_superhost."""
    # the page's own rules: a neighbourhood is ranked on all its entire homes (n), each median skips a missing value
    nb_all = homes.groupby("neighbourhood_cleansed")["listing_id"].count()
    h = homes.dropna(subset=["revpar"]).copy()
    h["occ"] = 100 * h["occupancy"]
    h["rev"] = h["expected_revenue"]
    h["rev_bed"] = h["rev"] / h["bedrooms"].clip(lower=1)
    h["clear50"] = (100.0 * (h["rev"] >= 50_000)).where(h["rev"].notna())
    h["super"] = 100.0 * h["host_is_superhost"].astype(str).str.lower().isin(["t", "true", "1"])
    ok = h[["adr", "occ"]].notna().all(axis=1)   # a home whose price was dropped is not segmented
    seg, seg_names, seg_meta = _segments(h[ok])
    h["seg"] = seg.reindex(h.index).fillna(-1).astype(int)
    have_models = models_dir is not None
    if have_models:
        h = h.merge(load_models(models_dir), on="listing_id", how="left")
        h["matched"] = h[["churn", "resid", "mood", "cap"]].notna().any(axis=1)
    HM = METRICS + (MODEL_METRICS if have_models else [])

    edges = {m: np.quantile(h[m].dropna(), np.linspace(.02, .98, BINS + 1)).round(2).tolist() for m in HM}

    def hist(v: pd.Series, m: str) -> list[int]:
        e = np.array(edges[m]); v = v.dropna().clip(e[0], e[-1])
        return np.histogram(v, bins=e)[0].astype(int).tolist()

    def group(g: pd.DataFrame, name: str, sub: str) -> dict:
        m = {k: num(g[k].median()) for k in HM} | {"clear50": num(g["clear50"].mean(), 1), "super": num(g["super"].mean(), 1)}
        if have_models:
            m["anom"] = num(g["anom"].mean(), 1)
        out = {"name": name, "sub": sub, "n": int(len(g)), "m": m,
               "q": {k: [num(g[k].quantile(.25)), num(g[k].quantile(.75))] for k in HM},
               "h": {k: hist(g[k], k) for k in HM}}
        if have_models:
            out["matched"] = int(g["matched"].sum())
        return out

    nb_ok = nb_all[nb_all >= min_n].index
    nbs = [group(g, n, f"{int(nb_all[n]):,} entire homes") for n, g in h[h["neighbourhood_cleansed"].isin(nb_ok)].groupby("neighbourhood_cleansed")]
    segs = [group(h[h["seg"] == i], seg_names[i], f"{seg_meta['desc'][i]}, {int((h['seg'] == i).sum()):,} entire homes") for i in range(len(seg_names))]

    hc = h.groupby("host_id").size().sort_values(ascending=False)
    hc = hc[hc >= HOST_MIN]
    host_code = {hid: f"H{i + 1:03d}" for i, hid in enumerate(hc.index)}
    host_idx = {hid: i for i, hid in enumerate(hc.index)}
    hosts = []
    for hid in hc.index:
        g = h[h["host_id"] == hid]
        top = g["neighbourhood_cleansed"].mode().iat[0] if g["neighbourhood_cleansed"].notna().any() else "Broward"
        hosts.append(group(g, f"Host {host_code[hid]}", f"{len(g):,} entire homes, most in {top}"))

    nb_index = {n["name"]: i for i, n in enumerate(nbs)}
    h = h.sort_values("revpar", ascending=False).reset_index(drop=True)
    rows = []
    for i, r in h.iterrows():
        bed = r["bedrooms"]
        rows.append([nb_index.get(r["neighbourhood_cleansed"], -1), int(r["seg"]),
                     host_idx.get(r["host_id"], -1),
                     None if pd.isna(bed) else int(bed), int(r["super"] > 0),
                          *[None if pd.isna(r[c]) else round(float(r[c]), d) for c, d in (("revpar", 2), ("adr", 2), ("occ", 1), ("rev", 0), ("rev_bed", 0))
                       + ((("churn", 1), ("resid", 2), ("mood", 3), ("cap", 2), ("noi", 0), ("anom", 0)) if have_models else ())]])
    county = {m: num(h[m].median()) for m in HM} | {"clear50": num(h["clear50"].mean(), 1), "super": num(h["super"].mean(), 1)}
    if have_models:
        county["anom"] = num(h["anom"].mean(), 1)
    return {"asof": asof, "homes": int(len(h)), "edges": edges, "county": county,
            "county_h": {m: hist(h[m], m) for m in HM}, "nb_names": [n["name"] for n in nbs],
            "models": ({"asof": "22 September 2026", "matched": int(h["matched"].sum()), "of": int(len(h)),
                        "src": "bnbscope models of the 22 September 2026 snapshot: an XGBoost churn classifier (held-out AUC 0.818), "
                               "an XGBoost occupancy model (its residual is actual minus predicted RevPAR), IsolationForest anomalies, "
                               "VADER review sentiment, and NOI against a ZIP home value"}
                       if have_models else None),
            "levels": {"nb": nbs, "seg": segs, "host": hosts}, "seg_meta": seg_meta, "host_min": HOST_MIN,
            "listing_cols": ["nb", "seg", "host", "bedrooms", "superhost", "revpar", "adr", "occ", "rev", "rev_bed"]
                            + (["churn", "resid", "mood", "cap", "noi", "anom"] if have_models else []),
            "listings": rows}
