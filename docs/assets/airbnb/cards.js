// The case study's cards: a neighbourhood, an ML segment, a host or a listing as a player card (flip tiles: a number,
// its z against the cards of its level, a bead slider; turn a tile over for the homes behind the number), and a
// head-to-head board of two cards of one level. Data: cards.json, built by tools/airbnb_cards.py. No names or ids.
(function () {
  "use strict";
  var DLG = document.getElementById("ab-cards");
  if (!DLG) return;
  var D = null, state = { level: "nb", a: 0, b: 1, view: "card", nbf: 0, fam: "succ", gpool: "all", gf: -1, cur: null, page: 0 };
  var LEVELS = [["nb", "Neighbourhood"], ["seg", "ML segment"], ["host", "Host"], ["listing", "Listing"], ["guest", "Guest"]];
  var LWORD = { nb: "neighbourhoods", seg: "segments", host: "hosts", listing: "listings", guest: "guests" };
  // a guest card's measures are bands (issue 808: no exact count, no date), each a tendency, so each wears the
  // cyan-to-pink scale; none is better or worse. Hues are identity only. The bands' words come from cards.json.
  // the flip hint: two arrows passing each other (the owner, 2026-11-21), in the kit's cyan and gold, never a value colour
  var FLIP = '<svg class="ab-flip" viewBox="0 0 48 40" aria-hidden="true" focusable="false"><path class="u" d="M8 21C8 12.7 13.2 8 21.5 8H31V2l13 11-13 11v-6h-9.5c-4.6 0-7.4 1.4-8.7 3z"/><path class="d" d="M40 19c0 8.3-5.2 13-13.5 13H17v6L4 27l13-11v6h9.5c4.6 0 7.4-1.4 8.7-3z"/></svg>';
  var GKEYS = ["g_homes", "g_years", "g_nb", "g_beach", "g_price", "g_ret"];
  var GEXTRA = ["g_praise", "g_compl"];
  var GDEF = { g_homes: ["homes", "#2DD4BF", "Different homes reviewed"], g_years: ["years", "#60A5FA", "Calendar years with a review"],
    g_nb: ["nb", "#C084FC", "Neighbourhoods of the homes reviewed"], g_beach: ["beach", "#38BDF8", "Typical distance of the stays from the beach", ["nearer", "farther"]],
    g_price: ["price", "#FFC72C", "Price third of the homes picked, thirds of all stays", ["cheaper", "dearer"]],
    g_ret: ["ret", "#F472B6", "Return stays: reviews of a home already reviewed"], g_praise: ["praise", "#34D399", "English reviews holding a praise sentence"],
    g_compl: ["compl", "#FB923C", "English reviews holding a complaint sentence"] };
  var GFAM = [["loc", "#2DD4BF"], ["price", "#FFC72C"], ["beh", "#60A5FA"]];
  var GPOOL = [["all", "All guests"], ["loc", "Same place type"], ["price", "Same price type"], ["beh", "Same travel type"]];
  // each tile's own hue: identity only (a rail and a header strip), never a value; values wear the heat scale
  var M = {
    revpar: { l: "RevPAR", full: "Revenue per available night", per: "a night", f: "money", hue: "#FFC72C", src: "CAL" },
    adr: { l: "Nightly rate", full: "Average daily rate (ADR)", per: "a night", f: "money", hue: "#2DD4BF", src: "CAL" },
    occ: { l: "Occupancy", full: "Share of the next 365 nights booked", per: "", f: "pct", hue: "#C084FC", src: "CAL" },
    rev: { l: "Revenue", full: "Expected revenue a year", per: "a year", f: "moneyk", hue: "#FB923C", src: "CAL" },
    rev_bed: { l: "Per bedroom", full: "Expected revenue a year per bedroom", per: "a year", f: "moneyk", hue: "#F472B6", src: "CAL" },
    clear50: { l: "Clear $50k", full: "Share of its homes expected to earn $50k or more a year", per: "of homes", f: "pct", hue: "#60A5FA", src: "CAL", share: true },
    super: { l: "Superhost", full: "Share of its homes run by a Superhost", per: "of homes", f: "pct", hue: "#CBD5E1", src: "LST", share: true },
    churn: { l: "Churn risk", full: "Model churn risk: chance of no review in 180 days (XGBoost, AUC 0.818)", per: "", f: "pct", hue: "#F87171", src: "MDL", dir: -1 },
    resid: { l: "Beats model", full: "Actual RevPAR minus the model's prediction (XGBoost occupancy model), on the old price basis", per: "a night", f: "smoney", hue: "#34D399", src: "MDL" },
    mood: { l: "Review mood", full: "Mean VADER sentiment of its reviews, minus 1 to plus 1", per: "", f: "mood", hue: "#FBBF24", src: "NLP" },
    cap: { l: "Cap rate", full: "Net operating income over the ZIP's home value", per: "", f: "pct1", hue: "#38BDF8", src: "MDL" },
    noi: { l: "NOI", full: "Net operating income a year, after operating costs", per: "a year", f: "moneyk", hue: "#A78BFA", src: "MDL" },
    pred: { l: "Model RevPAR", full: "RevPAR the XGBoost occupancy model expects for a home like this, on the old price basis", per: "a night", f: "money", hue: "#2DD4BF", src: "MDL" },
    dsr: { l: "Last review", full: "Days since the last review", per: "days ago", f: "int", hue: "#94A3B8", src: "LST", dir: -1 },
    hv: { l: "Home value", full: "Zillow home value index (ZHVI) of the home's ZIP: a typical value, not this home's price", per: "", f: "moneyk", hue: "#38BDF8", src: "ZHVI", tend: true },
    rating: { l: "Review score", full: "Guests' overall review score, out of 5", per: "of 5", f: "x2", hue: "#FBBF24", src: "LST" },
    rpm: { l: "Reviews a month", full: "Reviews a month: how often a stay ends in a review", per: "a month", f: "x2", hue: "#2DD4BF", src: "LST" },
    nrev: { l: "Reviews", full: "Reviews in all, since the listing began", per: "in all", f: "int", hue: "#A78BFA", src: "LST" },
    years: { l: "Years hosting", full: "Years since the host joined Airbnb", per: "years", f: "y1", hue: "#60A5FA", src: "LST" },
    snaps: { l: "Staying power", full: "Inside Airbnb snapshots it appears in, of 10 since April 2024", per: "of 10", f: "int", hue: "#34D399", src: "LST" },
    gy: { l: "Gross yield", full: "Revenue a year over the ZIP's home value", per: "", f: "pct1", hue: "#34D399", src: "INV" },
    coc: { l: "Cash on cash", full: "Cash flow after the mortgage over the cash put in (25% down, 2% closing, 7% 30-year)", per: "", f: "pct1", hue: "#FFC72C", src: "INV" },
    dscr: { l: "DSCR", full: "Debt service coverage: NOI over the year's mortgage payments; 1.25 is a lender's usual floor", per: "x", f: "x2", hue: "#C084FC", src: "INV" },
    anom: { l: "Anomalies", full: "Share of its homes the IsolationForest flags as anomalous", per: "of homes", f: "pct", hue: "#FB7185", src: "MDL", share: true, dir: -1 },
    bedrooms: { l: "Bedrooms", full: "Bedrooms", per: "", f: "int", hue: "#60A5FA", src: "LST", plain: true },
    superhost: { l: "Superhost", full: "Run by a Superhost", per: "", f: "yes", hue: "#CBD5E1", src: "LST", plain: true }
  };
  // the four groups the owner measures by (2026-11-17: "opportunity, efficiency, success and longevity"); a tile may sit in two
  var GROUPS = { opp: ["gy", "cap", "coc", "dscr", "noi", "hv"], eff: ["occ", "adr", "rev_bed", "pred", "rpm", "anom"],
    succ: ["rev", "clear50", "super", "rating", "mood", "resid"], long: ["churn", "dsr", "years", "snaps", "nrev", "super"] };
  function groupKeys(fam) {
    var ks = GROUPS[fam] || GROUPS.succ;
    if (state.level !== "listing") return ks;
    return ks.map(function (k) { return k === "super" ? "superhost" : k === "clear50" ? "bedrooms" : k; });
  }
  var TILES = { group: ["adr", "occ", "rev", "rev_bed", "clear50", "super"], listing: ["adr", "occ", "rev", "rev_bed", "bedrooms", "superhost"],
    models: ["churn", "resid", "pred", "mood", "dsr", "anom"], invest: ["hv", "gy", "noi", "cap", "coc", "dscr"] };
  // Investment and Models rest on the 2026-09-22 asking price (a new price basis, fees included) and the old income
  // definition; they come back with the Investment Package on the measured income model (bnbscope experiments, E1)
  // the price-based figures are back (the owner, 2026-11-17: "the price modeling"): the investment figures are from
  // the 27 November 2025 snapshot, on the old basis; the RevPAR model's are divided by the measured price rise
  var FAMS = [["opp", "Opportunity"], ["eff", "Efficiency"], ["succ", "Success"], ["long", "Longevity"]];
  var MEDAL = [["gold", "1st"], ["silver", "2nd"], ["bronze", "3rd"]];
  var ROWS = ["revpar", "adr", "occ", "rev", "rev_bed", "clear50", "super"], MROWS = ["revpar", "churn", "resid", "pred", "mood", "dsr", "anom"],
    IROWS = ["revpar", "hv", "gy", "noi", "cap", "coc", "dscr"];

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function fmt(k, v) {
    if (v == null || isNaN(v)) return "none";
    var f = M[k].f;
    if (f === "money") return "$" + Math.round(v).toLocaleString("en-US");
    if (f === "moneyk") return Math.abs(v) >= 1e6 ? "$" + (v / 1e6).toFixed(1) + "M" : Math.abs(v) >= 1000 ? "$" + (v / 1000).toFixed(Math.abs(v) >= 10000 ? 0 : 1) + "k" : "$" + Math.round(v);
    if (f === "smoney") { var rv = Math.round(v); return (rv > 0 ? "+" : rv < 0 ? "-" : "") + "$" + Math.abs(rv).toLocaleString("en-US"); }
    if (f === "mood") return (v > 0 ? "+" : "") + v.toFixed(2);
    if (f === "pct1") return v.toFixed(1) + "%";
    if (f === "x2") return v.toFixed(2);
    if (f === "y1") return v.toFixed(1);
    if (f === "pct") return Math.round(v) + "%";
    if (f === "yes") return v ? "Yes" : "No";
    if (f === "band") { var bn = M[k].bands[Math.round(v)]; return bn == null ? "none" : bn; }
    return String(Math.round(v));
  }
  function gap(k, a, b) {
    var d = Math.abs(a - b), f = M[k].f;
    if (f === "band") return d === 0 ? "same band" : Math.round(d) + (Math.round(d) === 1 ? " band apart" : " bands apart");
    if (f === "pct") return Math.round(d) + " pts apart";
    return fmt(k, d) + " apart";
  }
  // the one GYOR heat scale, by z
  function heat(z) {
    if (z == null) return "hs-na";
    var s = [[-1.75, "n4"], [-1.25, "n3"], [-.75, "n2"], [-.25, "n1"], [.25, "0"], [.75, "p1"], [1.25, "p2"], [1.75, "p3"]];
    for (var i = 0; i < s.length; i++) if (z < s[i][0]) return "hs-" + s[i][1];
    return "hs-p4";
  }
  // a tendency (more or less, not better or worse) wears the cyan-to-pink scale, never red or green
  function hk(k, z) { var h = heat(z); return M[k] && M[k].tend ? h.replace("hs-", "ts-") : h; }
  function glyph(z) { return z == null ? "" : z >= .25 ? "▲" : z <= -.25 ? "▼" : "≈"; }
  function zText(z) { return (Math.abs(z) < .05 ? "0.0" : Math.abs(z).toFixed(1)) + " z"; }

  // inverse normal (Acklam), for a rank-based z: rank among the cards of the level, so skewed money is fair
  function probit(p) {
    var a = [-39.6968302866538, 220.946098424521, -275.928510446969, 138.357751867269, -30.6647980661472, 2.50662827745924],
      b = [-54.4760987982241, 161.585836858041, -155.698979859887, 66.8013118877197, -13.2806815528857],
      c = [-.00778489400243029, -.322396458041136, -2.40075827716184, -2.54973253934373, 4.37466414146497, 2.93816398269878],
      d = [.00778469570904146, .32246712907004, 2.445134137143, 3.75440866190742], q, r;
    if (p < .02425) { q = Math.sqrt(-2 * Math.log(p)); return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
    if (p > 1 - .02425) { q = Math.sqrt(-2 * Math.log(1 - p)); return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
    q = p - .5; r = q * q;
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  }
  var POOL = {};
  // a guest's z is against all guest cards, or against the guests of its own type in one family (the Against switch)
  function poolSel(level) {
    if (level !== "guest" || state.gpool === "all" || !state.cur || state.cur.t[state.gpool] == null) return null;
    return [state.gpool, state.cur.t[state.gpool]];
  }
  function pool(level, k) {
    var sel = poolSel(level), key = level + ":" + k + (sel ? ":" + sel.join("=") : "");
    if (POOL[key]) return POOL[key];
    var vals = items(level).filter(function (x) { return !sel || x.t[sel[0]] === sel[1]; }).map(function (x) { return x.m[k]; })
      .filter(function (v) { return v != null && !isNaN(v); }).sort(function (x, y) { return x - y; });
    return (POOL[key] = vals);
  }
  function rankOf(level, k, v) {       // 1 = highest
    var p = pool(level, k), lo = 0, hi = p.length;
    while (lo < hi) { var mid = (lo + hi) >> 1; if (p[mid] <= v) lo = mid + 1; else hi = mid; }
    var above = p.length - lo, below = 0; while (below < p.length && p[below] < v) below++;
    if (M[k].dir === -1) return { rank: below + 1, of: p.length, pctl: 1 - lo / p.length };
    return { rank: above + 1, of: p.length, pctl: lo / p.length };
  }
  function zOf(level, k, v) {
    if (v == null || isNaN(v) || M[k].plain) return null;
    var p = pool(level, k), n = p.length;
    if (n < 3) return null;
    var lo = 0, hi = n; while (lo < hi) { var mid = (lo + hi) >> 1; if (p[mid] < v) lo = mid + 1; else hi = mid; }
    var lo2 = lo; while (lo2 < n && p[lo2] === v) lo2++;
    var z = probit(Math.min(.999, Math.max(.001, (lo + (lo2 - lo) / 2) / n)));
    return M[k].dir === -1 ? -z : z;
  }

  // a listing row as a card-shaped item
  var LISTING_CACHE = null;
  function listingItems() {
    if (LISTING_CACHE) return LISTING_CACHE;
    var cols = D.listing_cols, ix = {}; cols.forEach(function (c, i) { ix[c] = i; });
    LISTING_CACHE = D.listings.map(function (r, i) {
      var nb = r[ix.nb] >= 0 ? D.nb_names[r[ix.nb]] : "Broward", bed = r[ix.bedrooms];
      return { name: (bed == null ? "Home" : bed === 0 ? "Studio" : bed + "-bed home") + " in " + nb, code: "L" + String(i + 1).padStart(5, "0"),
        sub: "Listing L" + String(i + 1).padStart(5, "0") + ", RevPAR rank " + (i + 1).toLocaleString("en-US") + " in the county", nb: r[ix.nb], seg: r[ix.seg], host: r[ix.host],
        n: 1, m: { revpar: r[ix.revpar], adr: r[ix.adr], occ: r[ix.occ], rev: r[ix.rev], rev_bed: r[ix.rev_bed], bedrooms: bed, superhost: r[ix.superhost],
          churn: ix.churn != null ? r[ix.churn] : null, resid: ix.resid != null ? r[ix.resid] : null, mood: ix.mood != null ? r[ix.mood] : null,
          cap: ix.cap != null ? r[ix.cap] : null, noi: ix.noi != null ? r[ix.noi] : null, anom: ix.anom != null ? r[ix.anom] : null,
          pred: ix.pred != null ? r[ix.pred] : null, dsr: ix.dsr != null ? r[ix.dsr] : null, hv: ix.hv != null ? r[ix.hv] : null,
          gy: ix.gy != null ? r[ix.gy] : null, coc: ix.coc != null ? r[ix.coc] : null, dscr: ix.dscr != null ? r[ix.dscr] : null } };
    });
    return LISTING_CACHE;
  }
  // a guest row as a card-shaped item: bands only, and the code is its place in a secret order, never a rank
  var GUEST_CACHE = null;
  function guestItems() {
    if (GUEST_CACHE) return GUEST_CACHE;
    var G = D.guests, ix = {}; G.cols.forEach(function (c, i) { ix[c] = i; });
    GUEST_CACHE = G.rows.map(function (r, i) {
      var code = "G" + String(i + 1).padStart(4, "0"), m = {};
      Object.keys(GDEF).forEach(function (k) { m[k] = r[ix[GDEF[k][0]]]; });
      var talk = [], bits = r[ix.talk];
      G.aspects.forEach(function (a, j) { if (bits & (1 << j)) talk.push(a); });
      return { name: "Guest " + code, code: code, n: 1, m: m, talk: talk, t: { loc: r[ix.t_loc], price: r[ix.t_price], beh: r[ix.t_beh] },
        sub: fmt("g_homes", m.g_homes) + " homes reviewed, " + fmt("g_years", m.g_years) + " years active" };
    });
    return GUEST_CACHE;
  }
  function guestSetup() {
    var G = D.guests; if (!G || M.g_homes) return;
    Object.keys(GDEF).forEach(function (k) {
      var d = GDEF[k], b = G.bands[d[0]];
      M[k] = { l: b.l, full: d[2], per: "", f: "band", hue: d[1], src: "REV", tend: true, bands: b.names, ends: d[3] || ["less", "more"] };
      D.edges[k] = b.names.map(function (_, i) { return i - .5; }).concat([b.names.length - .5]);
      D.county_h[k] = G.hist[d[0]];
    });
  }
  function typeName(fam, i) { return i == null ? "not typed" : D.guests.types[fam].names[i]; }
  function items(level) { return level === "listing" ? listingItems() : level === "guest" ? guestItems() : D.levels[level]; }
  function listingChoices() {
    var all = listingItems(), nbf = state.nbf;
    return all.map(function (x, i) { return [x, i]; }).filter(function (p) { return p[0].nb === nbf; });
  }

  // ── the parts ──
  function slider(z) {
    if (z == null) return '<div class="ab-zm na"><span class="trk"></span><span class="ends"><i>no score: a description, not a ranking</i></span></div>';
    var x = 50 + 50 * Math.max(-3, Math.min(3, z)) / 3, lo = Math.min(50, x), w = Math.abs(x - 50), h = heat(z);
    return '<div class="ab-zm"><span class="trk"><span class="fill ' + h + '" style="left:' + lo.toFixed(1) + "%;width:" + w.toFixed(1) + '%"></span><span class="mid"></span>'
      + '<span class="dot ' + h + '" style="left:' + x.toFixed(1) + '%"></span></span><span class="ends"><i>weaker</i><i>' + esc(LWORD[state.level]) + " average</i><i>stronger</i></span></div>";
  }
  function gem(z) {
    if (z == null) return "";
    return '<span class="ab-gem ' + heat(z) + '"><span aria-hidden="true">' + glyph(z) + "</span> " + zText(z) + "</span>";
  }
  function strip(x, k, big) {
    var e = D.edges[k]; if (!e) return "";
    var hist = x.h ? x.h[k] : D.county_h[k], mark = -1;
    if (!x.h) { var v = x.m[k]; if (v == null) return ""; for (var i = 0; i < e.length - 1; i++) if (v >= e[i]) mark = i; }
    var mx = Math.max.apply(null, hist) || 1;
    var cols = hist.map(function (c, i) {
      var cls = x.h ? "on" : i === mark ? "on mk" : "";
      return '<i class="' + cls + '" style="--hf:' + Math.max(.04, c / mx).toFixed(3) + '"' + (big ? ' data-n="' + c + '"' : "") + "></i>";
    }).join("");
    if (!big) return '<div class="ab-mini" aria-hidden="true">' + cols + "</div>";
    var who = x.h ? "Its " + x.n.toLocaleString("en-US") + " homes" : state.level === "guest" ? "All " + D.guests.kept.toLocaleString("en-US") + " guest cards in each band, this guest marked"
      : "All " + D.homes.toLocaleString("en-US") + " entire homes in the county, this one marked";
    var lo = M[k].f === "band" ? M[k].bands[0] : fmt(k, e[0]), hi = M[k].f === "band" ? M[k].bands[M[k].bands.length - 1] : fmt(k, e[e.length - 1]);
    return '<div class="ab-cols"><div class="plot">' + cols + '</div><div class="axis"><i>' + esc(lo) + "</i><i>" + esc(hi) + "</i></div><p>" + esc(who) + "</p></div>";
  }
  function shareBar(k, v) {
    if (v == null) return "";
    var c = D.county[k] == null ? 0 : D.county[k], w = Math.max(0, Math.min(100, v));
    return '<div class="ab-share"><span class="trk"><span class="fill" style="width:' + w.toFixed(1) + '%"></span><span class="cty" style="left:' + c.toFixed(1) + '%"></span></span>'
      + '<span class="lg"><i>' + esc(fmt(k, v) + " " + (M[k].per || "")) + "</i><i>county " + esc(fmt(k, c)) + "</i></span></div>";
  }
  // the mix of a card's homes by segment and host type moved to the archetype-mix cards (SportsAnalytics issue 812)
  function tile(x, k, hero) {
    var guest = state.level === "guest";
    // a guest card carries no rank and no medal (issue 808, rule 5): its z alone, from its band
    var d = M[k], v = x.m[k], z = zOf(state.level, k, v), r = d.plain || v == null || guest ? null : rankOf(state.level, k, v);
    var rk = r ? "rank " + r.rank.toLocaleString("en-US") + " of " + r.of.toLocaleString("en-US") : "";
    // a medal for the first three of the level on this tile's own measure (ties share a place)
    var place = r && r.rank <= 3 && r.of >= 4 ? r.rank : 0;
    var medal = place ? '<span class="ab-medal m' + place + '">' + MEDAL[place - 1][1] + "</span>" : "";
    function hd(small) { return '<div class="ab-th"><i></i><span class="t">' + esc(d.l) + "</span>" + (small ? "<small>" + esc(small) + "</small>" : "") + '<span class="ab-fh" aria-hidden="true">' + FLIP + '</span></div>'; }
    var head = hd(guest ? (v == null ? "too few reviews" : "") : rk);
    var q = x.q && x.q[k] ? "middle half " + fmt(k, x.q[k][0]) + " to " + fmt(k, x.q[k][1]) : "";
    var extra = hero && !x.mix ? ('<div class="ab-hx"><div><span>Expected revenue a year</span><b>' + fmt("rev", x.m.rev) + "</b></div><div><span>County median RevPAR</span><b>" + fmt("revpar", D.county.revpar) + "</b></div></div>") : "";
    var front = '<div class="ab-face ab-f">' + head + '<div class="ab-tv"><b>' + fmt(k, v) + "</b>" + (d.per ? '<span class="per">' + esc(d.per) + "</span>" : "") + medal + gem(z) + "</div>"
      + slider(z) + (hero ? strip(x, k, false) + extra : M[k].share ? shareBar(k, v) : strip(x, k, false)) + "</div>";
    var back = '<div class="ab-face ab-b" aria-hidden="true">' + hd(x.h ? (M[k].share ? "" : "median ") + fmt(k, v) : (guest ? "this guest " : "this home ") + fmt(k, v))
      + (D.edges[k] ? strip(x, k, true) : '<div class="ab-cols"><p>' + esc(M[k].full) + ": " + esc(fmt(k, v)) + (D.county[k] != null ? ", against " + esc(fmt(k, D.county[k])) + " across the county" : "") + ".</p>" + (M[k].share ? shareBar(k, v) : "") + "</div>")
      + (q ? '<p class="q">' + esc(q) + "</p>" : "") + "</div>";
    var ends = d.ends || ["less", "more"];
    if (d.tend) front = front.replace(/hs-/g, "ts-").replace(/<i>weaker<\/i>/, "<i>" + ends[0] + "</i>").replace(/<i>stronger<\/i>/, "<i>" + ends[1] + "</i>");
    var label = d.full + ", " + fmt(k, v) + (z == null ? "" : ", " + (z >= .25 ? (d.tend ? "more than" : "above") : z <= -.25 ? (d.tend ? "less than" : "below") : "near") + " the " + LWORD[state.level] + " average, z " + z.toFixed(1)) + (r ? ", rank " + r.rank + " of " + r.of : "") + (place ? ", a " + MEDAL[place - 1][0] + " medal" : "") + (guest ? ". Turn over for every guest card in each band." : ". Turn over for the homes behind it.");
    return '<div class="ab-t' + (hero ? " hero" : "") + (place ? " medal m" + place : "") + '" style="--sh:' + d.hue + '" data-flip role="button" tabindex="0" aria-pressed="false" aria-label="' + esc(label) + '"><div class="ab-in">' + front + back + "</div></div>";
  }

  function picker(id, idx, label) {
    var opts;
    if (state.level === "guest") opts = guestChoices().map(function (p) { return '<option value="' + p[1] + '"' + (p[1] === idx ? " selected" : "") + ">" + esc(p[0].code + ", " + typeName("price", p[0].t.price) + ", " + typeName("beh", p[0].t.beh)) + "</option>"; });
    else if (state.level === "listing") opts = listingChoices().map(function (p) { return '<option value="' + p[1] + '"' + (p[1] === idx ? " selected" : "") + ">" + esc(p[0].code + ", " + p[0].name + ", " + fmt("revpar", p[0].m.revpar)) + "</option>"; });
    else opts = items(state.level).map(function (x, i) { return [x, i]; }).sort(function (a, b) { return (b[0].m.revpar || 0) - (a[0].m.revpar || 0); })
      .map(function (p) { return '<option value="' + p[1] + '"' + (p[1] === idx ? " selected" : "") + ">" + esc(p[0].name + ", " + fmt("revpar", p[0].m.revpar)) + "</option>"; });
    return '<label class="ab-pick"><span>' + esc(label) + '</span><select id="' + id + '">' + opts.join("") + "</select></label>";
  }
  function nbFilter() {
    return '<label class="ab-pick"><span>In</span><select id="ab-nbf">' + D.nb_names.map(function (n, i) { return '<option value="' + i + '"' + (i === state.nbf ? " selected" : "") + ">" + esc(n) + "</option>"; }).join("") + "</select></label>";
  }

  // the deck: one plain sentence a magazine would run under the name, from the card's own numbers
  function deck(x) {
    var v = x.m.revpar, c = D.county.revpar;
    if (v == null || !c) return "";
    var ratio = v / c, how = ratio >= 1.8 ? "nearly twice" : ratio >= 1.15 ? Math.round((ratio - 1) * 100) + "% above" : ratio <= .55 ? "about half" : ratio <= .87 ? Math.round((1 - ratio) * 100) + "% below" : "close to";
    var za = zOf(state.level, "adr", x.m.adr), zo = zOf(state.level, "occ", x.m.occ), why = "";
    if (za != null && zo != null) {
      if (ratio >= 1) why = za > zo + .5 ? ", on rate more than bookings" : zo > za + .5 ? ", on bookings more than rate" : ", on rate and bookings together";
      else why = za < zo - .5 ? ", held back by its rate" : zo < za - .5 ? ", held back by empty nights" : ", on both rate and bookings";
    }
    var fig = function (t) { return '<b class="fig">' + esc(t) + "</b>"; };
    return fig(fmt("revpar", v)) + " a night, " + '<em class="how">' + esc(how) + "</em> the county's " + fig(fmt("revpar", c)) + (why ? '<span class="why">' + esc(why) + "</span>" : "") + ".";
  }
  function subLine(x) {
    var parts = String(x.sub).split(", ");
    if (state.level === "seg" && parts.length >= 4) {
      var hues = ["#2DD4BF", "#FFC72C", "#C084FC"];
      return '<div class="ab-tags">' + parts.slice(0, 3).map(function (t, i) { return '<span class="ab-tag" style="--th:' + hues[i] + '">' + esc(t.charAt(0).toUpperCase() + t.slice(1)) + "</span>"; }).join("")
        + '<span class="ab-cnt">' + esc(parts.slice(3).join(", ")) + "</span></div>";
    }
    return '<span class="ab-sub">' + esc(x.sub) + "</span>";
  }
  function share(n) { var v = 100 * n / D.homes; return v < 1 ? v.toFixed(2) : v.toFixed(1); }
  // the badge slot: the metal medal for the first three on RevPAR today; later badges (an archetype, a trend) join here
  // a badge is an emblem: a hexagonal medallion (a big mark inside) over a notched ribbon (its word)
  function emblem(cls, mark, word, spoken) {
    return '<span class="ab-badge ' + cls + '" role="img" aria-label="' + esc(spoken) + '"><span class="em"><b>' + esc(mark) + '</b></span><span class="rib">' + esc(word) + "</span></span>";
  }
  function badges(x, r) {
    var out = [];
    if (r && r.rank <= 3 && r.of >= 4) out.push(emblem(MEDAL[r.rank - 1][0], String(r.rank), "RevPAR", MEDAL[r.rank - 1][1] + " on RevPAR, " + MEDAL[r.rank - 1][0] + " badge"));
    out.push(emblem("data", "CAL", "Data", "Measured from calendar data"));
    return out.join("");
  }
  function band(x) {
    var r = rankOf(state.level, "revpar", x.m.revpar), z = zOf(state.level, "revpar", x.m.revpar);
    var lvl = LEVELS.filter(function (l) { return l[0] === state.level; })[0][1];
    // a market's own review span (the owner, 2026-11-21: "each market's years"); its homes count is on the Homes chip
    var yrs = state.level === "nb" && D.nb_years ? D.nb_years[x.name] : null;
    return '<div class="ab-disc" aria-hidden="true">' + (state.level === "listing" ? "L" : state.level === "host" ? "H" : state.level === "seg" ? "ML" : "N") + "</div>"
      + '<div class="ab-id"><span class="eyebrow">' + esc(yrs ? lvl + ": Broward County" : lvl + ", Broward County, " + D.asof) + '</span><p id="ab-title" class="ab-name' + (x.name.length > 18 ? " long" : "") + '" role="heading" aria-level="2">' + esc(x.name) + '</p>'
      + (yrs ? '<span class="ab-sub ab-yrs">Years: ' + yrs[0] + " to " + yrs[1] + "</span>" : subLine(x)) + '<p class="ab-deck">' + deck(x) + "</p></div>"
      + '<div class="ab-tray"><div class="ab-badges" aria-label="Badges">' + badges(x, r) + "</div>"
      + '<div class="ab-chips"><span class="ab-chip rk ' + heat(z) + '"><i>Rank</i><b>' + r.rank.toLocaleString("en-US") + "<small>/" + r.of.toLocaleString("en-US") + "</small></b></span>"
      + '<span class="ab-chip"><i>Homes</i><b>' + x.n.toLocaleString("en-US") + "</b></span>"
      + '<span class="ab-chip"><i>Of county</i><b>' + share(x.n) + "<small>%</small></b></span></div></div>";
  }

  // ── the guest card: a banner of three types, a hero of the types and the words, six band tiles ──
  function gChip(k, x) {
    var v = x.m[k], z = zOf("guest", k, v);
    return '<span class="ab-chip rk ' + (v == null ? "ts-na" : heat(z).replace("hs-", "ts-")) + '"><i>' + esc(M[k].l) + "</i><b>" + esc(fmt(k, v)) + "</b></span>";
  }
  function guestBand(x) {
    var G = D.guests, chips = GFAM.map(function (f) {
      return '<span class="ab-chip ab-tchip" style="--th:' + f[1] + '"><i>' + esc(G.types[f[0]].l) + "</i><b>" + esc(typeName(f[0], x.t[f[0]]).replace(/^The /, "")) + "</b></span>";
    }).join("");
    return '<div class="ab-disc" aria-hidden="true">G</div>'
      + '<div class="ab-id"><span class="eyebrow">Guest: Broward County</span><p id="ab-title" class="ab-name" role="heading" aria-level="2">' + esc(x.name) + "</p>"
      + '<span class="ab-sub ab-yrs">Years: ' + G.first_year + " to " + G.asof.slice(0, 4) + "</span></div>"
      + '<div class="ab-tray"><div class="ab-badges" aria-label="Badges">' + emblem("data", "REV", "Data", "Measured from review data") + "</div>"
      + '<div class="ab-chips">' + chips + "</div></div>";
  }
  function guestHero(x) {
    var G = D.guests;
    var rows = GFAM.map(function (f) {
      var T = G.types[f[0]], i = x.t[f[0]], tot = T.n.reduce(function (a, b) { return a + b; }, 0) || 1;
      var bar = T.n.map(function (c, j) { return '<span class="' + (j === i ? "on" : "") + '" style="--w:' + (100 * c / tot).toFixed(2) + '%"></span>'; }).join("");
      return '<div class="ab-gtype" style="--th:' + f[1] + '" title="' + esc(i == null ? "too few priced stays" : T.why[i]) + '"><span class="fam">' + esc(T.l) + '</span>'
        + '<span class="cnt" aria-label="' + (i == null ? "" : Math.round(100 * T.n[i] / tot) + " percent of guests") + '">' + (i == null ? "" : Math.round(100 * T.n[i] / tot) + "%") + "</span><b>" + esc(typeName(f[0], i)) + "</b>"
        + '<span class="bar" role="img" aria-label="' + esc(T.l + ": " + T.names.map(function (n, j) { return n + " " + Math.round(100 * T.n[j] / tot) + "%"; }).join(", ")) + '">' + bar + "</span></div>";
    }).join("");
    var talk = x.talk.length ? x.talk.map(function (a) { return '<span class="ab-tag" style="--th:#CBD5E1">' + esc(a.charAt(0).toUpperCase() + a.slice(1)) + "</span>"; }).join("")
      : '<span class="ab-cnt">' + (x.m.g_praise == null ? "too few English reviews" : "nothing stands out") + "</span>";
    var front = '<div class="ab-face ab-f"><div class="ab-th"><i></i><span class="t">Guest types</span><small>three ways to sort a guest</small><span class="ab-fh" aria-hidden="true">' + FLIP + '</span></div>'
      + '<div class="ab-gtypes">' + rows + "</div>"
      + '<div class="ab-gtalk"><span class="fam">Writes about</span><div class="ab-tags">' + talk + "</div>"
      + '<div class="ab-gchips">' + gChip("g_praise", x) + gChip("g_compl", x) + "</div></div></div>";
    var trows = GFAM.map(function (f) {
      var T = G.types[f[0]];
      return T.names.map(function (n, j) { var h = T.hold.by[j] || T.hold.by[String(j)];
        return "<tr><td>" + esc(T.l) + "</td><td>" + esc(n) + "</td><td>" + T.n[j].toLocaleString("en-US") + "</td><td>" + (h ? Math.round(100 * h.kept) + "% (chance " + Math.round(100 * h.chance) + "%)" : "not measured") + "</td></tr>"; }).join("");
    }).join("");
    var back = '<div class="ab-face ab-b" aria-hidden="true"><div class="ab-th"><i></i><span class="t">The types as a table</span><span class="ab-fh" aria-hidden="true">' + FLIP + '</span></div>'
      + '<div class="ab-gtab"><table class="twin"><thead><tr><th scope="col">Family</th><th scope="col">Type</th><th scope="col">Guest cards</th><th scope="col">Keeps its type</th></tr></thead><tbody>' + trows + "</tbody></table>"
      + '<p class="q">Keeps its type: each guest\'s early reviews and late reviews typed apart, the same type both times, against chance.</p></div></div>';
    var label = "Guest types. " + GFAM.map(function (f) { return G.types[f[0]].l + ": " + typeName(f[0], x.t[f[0]]); }).join(". ") + ". Turn over for every type as a table.";
    return '<div class="ab-t hero ab-ghero" style="--sh:#2DD4BF" data-flip role="button" tabindex="0" aria-pressed="false" aria-label="' + esc(label) + '"><div class="ab-in">' + front + back + "</div></div>";
  }
  function guestView(x) {
    var G = D.guests, pl = GPOOL.filter(function (p) { return p[0] === state.gpool; })[0][1];
    return '<div class="ab-tiles">' + guestHero(x) + GKEYS.map(function (k) { return tile(x, k, false); }).join("") + "</div>"
      + '<p class="ab-note">Against ' + esc(pl.toLowerCase()) + ". Reviews to " + esc(new Date(G.asof + "T12:00:00").toLocaleDateString("en-US", { month: "long", year: "numeric" })) + ". Guests who reviewed " + G.min_homes + " or more homes, coded in a secret order. Bands only: no counts, no dates, no homes, no names. A card is shown only where "
      + G.crowd + " or more guests share its bands: " + G.kept.toLocaleString("en-US") + " of " + (G.kept + G.left_off).toLocaleString("en-US") + ".</p>";
  }
  function guestFilter() {
    var T = D.guests.types.loc;
    return '<label class="ab-pick"><span>Place type</span><select id="ab-gf">' + T.names.map(function (n, i) { return '<option value="' + i + '"' + (i === state.gf ? " selected" : "") + ">" + esc(n) + "</option>"; }).join("") + "</select></label>";
  }
  function guestChoices() {
    return guestItems().map(function (x, i) { return [x, i]; }).filter(function (p) { return p[0].t.loc === state.gf; });
  }

  function cardView() {
    var list = items(state.level), x = list[state.a] || list[0], fam = D.models ? state.fam : "succ";
    if (state.level === "guest") return guestView(x);
    var keys = D.models ? groupKeys(fam) : state.level === "listing" ? TILES.listing : TILES.group;
    var notes = state.level === "seg" ? '<p class="ab-note">' + esc(D.seg_meta.method) + ". Titles follow a rule on each group's rate and calendar against the county's medians, so a refit renames itself. Homes whose nightly price was a placeholder are not segmented.</p>"
      : state.level === "host" ? '<p class="ab-note">Hosts with ' + D.host_min + " or more entire homes, coded by size. No names or Airbnb ids: most hosts are private people.</p>"
      : state.level === "listing" ? '<p class="ab-note">Each listing is coded by its RevPAR rank. No names, ids or links. Its tiles turn over to the county with this home marked.</p>' : "";
    var B = D.models && D.models.basis, basisNote = B ? " The model's RevPAR is put on the old price basis: the same " + B.pairs.toLocaleString("en-US")
      + " homes list at " + B.median.toFixed(2) + " times their " + "September 2025 price, so each prediction is divided by its price decile's ratio ("
      + B.ratio[0].toFixed(2) + " to " + Math.max.apply(null, B.ratio).toFixed(2) + "); on held-out homes the corrected price sits " + (100 * B.spread).toFixed(0) + "% from last year's, against " + (100 * B.raw_spread).toFixed(0) + "% uncorrected." : "";
    if (fam === "opp") notes = '<p class="ab-note">Investment, from the ' + esc(D.models.invest_asof) + " snapshot (the old price basis): bnbscope\'s calculator, " + D.finance.down + "% down, " + D.finance.closing + "% closing, a "
      + D.finance.rate + "% " + D.finance.term + "-year loan. Home value is the ZIP's Zillow index, a typical value, not this home's price; it is a cost of entry, so it wears the more-or-less scale.</p>";
    else if (fam === "eff") notes = '<p class="ab-note">Occupancy, rate and per bedroom read the 19 March 2025 calendar. ' + esc(D.models.src.split(":")[0]) + "." + esc(basisNote) + "</p>";
    else if (fam === "succ") notes = '<p class="ab-note">Review score is the guests\' overall score out of 5; review mood is the mean VADER sentiment of the review text. Beats model is actual minus predicted RevPAR on the old price basis.</p>';
    else if (fam === "long") notes = '<p class="ab-note">Churn risk is bnbscope\'s XGBoost classifier (held-out AUC 0.818) for no review in 180 days. Staying power counts the 10 Inside Airbnb snapshots since April 2024 a home appears in.</p>';
    else if (fam === "invest") notes = '<p class="ab-note">Investment: bnbscope\'s calculator, same formulas and defaults: ' + D.finance.down + "% down, " + D.finance.closing + "% closing, a "
      + D.finance.rate + "% " + D.finance.term + "-year loan. Home value is the ZIP's Zillow index, a typical value, not this home's price. Revenue and NOI come from the 22 September 2026 run, an estimate.</p>";
    else if (fam === "models") notes = '<p class="ab-note">' + esc(D.models.src) + ". Matched by listing id to " + D.models.matched.toLocaleString("en-US") + " of these " + D.models.of.toLocaleString("en-US")
      + " homes" + (x.matched != null ? "; this card, " + x.matched.toLocaleString("en-US") + " of its " + x.n.toLocaleString("en-US") : "") + ". Model revenue there is the asking price times occupancy, an estimate; RevPAR on the hero tile is measured.</p>";
    if (state.level === "nb" && D.nb_years) {      // the calendar date left the banner for the Years line, so it is said here
      var cal = "Revenue from the calendar of " + D.asof + ". ";
      notes = notes ? notes.replace('<p class="ab-note">', '<p class="ab-note">' + esc(cal)) : '<p class="ab-note">' + esc(cal) + "</p>";
    }
    return '<div class="ab-tiles">' + tile(x, "revpar", true) + keys.map(function (k) { return tile(x, k, false); }).join("") + "</div>" + notes;
  }

  function h2hView() {
    var list = items(state.level), A = list[state.a] || list[0], B = list[state.b] || list[1] || list[0];
    var guest = state.level === "guest";
    var keys = guest ? GKEYS.concat(GEXTRA) : D.models ? ["revpar"].concat(groupKeys(state.fam)) : state.level === "listing" ? ROWS.slice(0, 5) : ROWS;
    // a stat row in the matchup look the owner favours (the NFL matchup cards, 2026-11-21: "these are my favorite"): each
    // side a pill with its rank disc, the stat's source disc, the stat over a rail in its hue (the rail's length is where it
    // sits among its peers), the number in a dark capsule and a plain verdict pill in the heat or tendency scale by z
    function side(x, k) {
      var v = x.m[k], z = zOf(state.level, k, v), r = v == null || guest ? null : rankOf(state.level, k, v);
      var p = pool(state.level, k), med = p.length ? p[Math.floor(p.length / 2)] : null;
      var near = v == null || med == null || v === med || Math.abs(z == null ? 0 : z) < .25;
      var word = v == null || med == null ? "not measured" : near ? "near the middle" : v > med ? "higher than most" : "lower than most";
      var g = near ? "\u2248" : v > med ? "\u25B2" : "\u25BC";
      var at = z == null ? 50 : 50 + 50 * Math.max(-1, Math.min(1, (M[k].dir === -1 ? -z : z) / 2.5));
      return '<div class="mside" style="--sh:' + M[k].hue + '">'
        + '<span class="mrk' + (r ? "" : " na") + '"' + (r ? "" : ' aria-hidden="true"') + ">" + (r ? r.rank.toLocaleString("en-US") : "") + "</span>"
        + '<span class="mdisc" aria-hidden="true"><b>' + esc(M[k].src) + "</b></span>"
        + '<span class="mname"><small>' + esc(x.name) + "</small><b>" + esc(M[k].l) + '</b><span class="mrail"><i style="width:' + at.toFixed(1) + '%"></i></span></span>'
        + '<span class="mval"><span class="mcap">' + esc(fmt(k, v)) + '</span><span class="mverd ' + (v == null ? "hs-na" : hk(k, z)) + '"><span aria-hidden="true">' + g + '</span> <span class="vlong">' + esc(word) + '</span><span class="vshort" aria-hidden="true">' + esc(word.split(" ")[0] === "near" ? "middle" : word.split(" ")[0]) + "</span></span></span></div>";
    }
    var rows = keys.map(function (k) {
      var a = A.m[k], b = B.m[k];
      return '<div class="ab-row mrow" role="row" aria-label="' + esc(M[k].full + ": " + A.name + " " + fmt(k, a) + ", " + B.name + " " + fmt(k, b)) + '">' + side(A, k)
        + '<span class="mvs" aria-hidden="true">vs</span>' + side(B, k) + "</div>";
    }).join("");
    function head(x, right) {
      if (guest) return '<div class="hd' + (right ? " r" : "") + '"><div><b>' + esc(x.name) + '</b><span class="ab-tags">'
        + GFAM.map(function (f) { return '<span class="ab-tag" style="--th:' + f[1] + '">' + esc(typeName(f[0], x.t[f[0]]).replace(/^The /, "")) + "</span>"; }).join("") + "</span></div></div>";
      // the names alone: rank and RevPAR open the first row below, in the matchup look (the owner: the header's pills were "unaceptable")
      return '<div class="hd' + (right ? " r" : "") + '"><div><b>' + esc(x.name) + "</b></div></div>";
    }
    return '<div class="ab-h2h"><div class="ab-hh">' + head(A, false) + '<span class="mvs" aria-hidden="true">vs</span>' + head(B, true) + '</div><div class="ab-rows" role="table" aria-label="Head to head">' + rows + "</div></div>";
  }

  function render() {
    var list = items(state.level), x = list[state.a] || list[0];
    if (state.level === "listing") {
      var ch = listingChoices();
      if (!ch.some(function (p) { return p[1] === state.a; })) state.a = ch.length ? ch[0][1] : 0;
      if (!ch.some(function (p) { return p[1] === state.b; })) state.b = ch.length > 1 ? ch[ch.length - 1][1] : state.a;
      x = list[state.a];
    }
    var guest = state.level === "guest";
    if (guest) {
      if (state.gf < 0) state.gf = x.t.loc;
      var gc = guestChoices();
      if (!gc.some(function (p) { return p[1] === state.a; })) state.a = gc.length ? gc[0][1] : 0;
      if (!gc.some(function (p) { return p[1] === state.b; })) state.b = gc.length > 1 ? gc[gc.length - 1][1] : state.a;
      x = list[state.a];
    }
    state.cur = x;
    DLG.dataset.lvl = state.level;
    DLG.classList.toggle("is-h2h", state.view === "h2h");      // not data-level: clicks find level buttons by that attribute
    DLG.querySelector(".ab-band").innerHTML = guest ? guestBand(x) : band(x);
    // the gold parallel: the card ranked first in its level on RevPAR wears a gold foil banner
    // the banner's metal: gold, silver or bronze for the first three of the level on RevPAR
    var rr = state.view === "card" && x.m.revpar != null ? rankOf(state.level, "revpar", x.m.revpar) : null;
    var tier = rr && rr.rank <= 3 && rr.of >= 4 ? MEDAL[rr.rank - 1][0] : "";
    ["gold", "silver", "bronze"].forEach(function (t) { DLG.querySelector(".ab-top").classList.toggle(t, t === tier); });
    var lv = LEVELS.map(function (l) { return '<button type="button" class="ab-seg" data-level="' + l[0] + '" aria-pressed="' + (l[0] === state.level) + '">' + l[1] + "</button>"; }).join("");
    var fams = guest ? '<label class="ab-pick"><span>Against</span><select id="ab-gp">' + GPOOL.map(function (p) { return '<option value="' + p[0] + '"' + (p[0] === state.gpool ? " selected" : "") + ">" + esc(p[1]) + "</option>"; }).join("") + "</select></label>"
      : D.models && FAMS.length > 1 && window.innerWidth < 1600 ? '<label class="ab-pick"><span>Stats</span><select id="ab-fam">' + FAMS.map(function (f) { return '<option value="' + f[0] + '"' + (f[0] === state.fam ? " selected" : "") + ">" + f[1] + "</option>"; }).join("") + "</select></label>"
      : D.models && FAMS.length > 1 ? '<div class="ab-segs ab-fam" role="group" aria-label="Stat family">' + FAMS.map(function (f) { return '<button type="button" class="ab-seg" data-fam="' + f[0] + '" aria-pressed="' + (f[0] === state.fam) + '">' + f[1] + "</button>"; }).join("") + "</div>" : "";
    var pick = fams + (state.level === "listing" ? nbFilter() : guest ? guestFilter() : "") + picker("ab-a", state.a, state.view === "h2h" ? "Left" : "Card") + (state.view === "h2h" ? picker("ab-b", state.b, "Right") : "");
    var lvBlock = window.innerWidth < 1600 ? '<label class="ab-pick"><span>Level</span><select id="ab-lv">' + LEVELS.map(function (l) { return '<option value="' + l[0] + '"' + (l[0] === state.level ? " selected" : "") + ">" + l[1] + "</option>"; }).join("") + "</select></label>"
      : '<div class="ab-segs" role="group" aria-label="Level">' + lv + "</div>";
    var vw0 = DLG.querySelector(".ab-views");
    if (vw0 && vw0.parentNode !== DLG.querySelector(".ab-top")) DLG.querySelector(".ab-top").appendChild(vw0);    // keep it out of the redraw
    DLG.querySelector(".ab-fs").innerHTML = lvBlock + pick
      + '<span class="ab-count"><b>' + items(state.level).length.toLocaleString("en-US") + "</b> " + LWORD[state.level] + "</span>";
    // shorter screens: the view buttons sit at the end of the filter strip, so the banner keeps one row
    var vws = DLG.querySelector(".ab-views"), home = window.innerHeight <= 960 ? DLG.querySelector(".ab-fs") : DLG.querySelector(".ab-top");
    if (vws && vws.parentNode !== home) home.appendChild(vws);
    DLG.querySelectorAll(".ab-view").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.view === state.view)); });
    DLG.querySelector(".ab-body").innerHTML = state.view === "h2h" ? h2hView() : cardView();
    // shorter screens: the small tiles (and head to head's rows) page in two halves, at full size
    var paged = window.innerWidth >= 900 && window.innerHeight <= 960;
    var tl = DLG.querySelector(".ab-tiles"), hh = DLG.querySelector(".ab-h2h");
    if (tl) { tl.querySelectorAll(".ab-t:not(.hero)").forEach(function (t, i, all) { t.dataset.pg = i < Math.ceil(all.length / 2) ? 0 : 1; }); }
    state.pages = tl && paged ? 2 : 1;
    if (tl) { state.page = state.page % 2; tl.classList.toggle("paged", paged); tl.classList.add("pg" + state.page); }
    if (hh) {
      // head to head: as many rows as fit, page by page (its header leaves a different height at each size)
      var box = hh.querySelector(".ab-rows"), rs = [].slice.call(hh.querySelectorAll(".ab-row"));
      rs.forEach(function (r) { r.style.display = ""; });
      var gp = parseFloat(getComputedStyle(box).rowGap) || 0, rh = rs.length ? rs[0].getBoundingClientRect().height + gp : 1, per = Math.max(1, Math.floor((box.clientHeight + gp) / rh));
      state.pages = Math.ceil(rs.length / per); state.page = state.page % state.pages;
      rs.forEach(function (r, i) { r.style.display = Math.floor(i / per) === state.page ? "" : "none"; });
    }
    DLG.classList.toggle("is-paged", state.pages > 1);
    // the note, also one click away (Method), for screens too short to show it under the tiles
    var nt = DLG.querySelector(".ab-body > .ab-note"), pop = DLG.querySelector("#ab-method");
    if (!pop) { pop = document.createElement("div"); pop.id = "ab-method"; pop.setAttribute("popover", ""); pop.className = "note"; DLG.appendChild(pop); }
    pop.innerHTML = '<h3>Method</h3>' + (nt ? nt.outerHTML : '<p class="ab-note">No method note for this view.</p>') + '<button type="button" class="btn" popovertarget="ab-method" popovertargetaction="hide">Close</button>';
    var vg = DLG.querySelector(".ab-views");
    if (vg && !vg.querySelector(".ab-pgbtn")) { var pb = document.createElement("button"); pb.type = "button"; pb.className = "ab-mbtn ab-pgbtn"; vg.insertBefore(pb, vg.firstChild); }
    var pbn = vg && vg.querySelector(".ab-pgbtn");
    if (pbn) { var last = state.page >= state.pages - 1; pbn.textContent = last ? "First stats" : "More stats";
      pbn.setAttribute("aria-label", (last ? "Back to the first stats" : "More stats") + ", page " + (state.page + 1) + " of " + state.pages); }
    if (vg && !vg.querySelector(".ab-mbtn:not(.ab-pgbtn)")) { var mb = document.createElement("button"); mb.type = "button"; mb.className = "ab-mbtn"; mb.setAttribute("popovertarget", "ab-method"); mb.textContent = "Method"; vg.insertBefore(mb, vg.querySelector(".ab-close")); }
  }

  function load(then) {
    if (D) return then();
    DLG.querySelector(".ab-body").innerHTML = '<p class="ab-note">Loading the cards.</p>';
    fetch(DLG.dataset.src).then(function (r) { return r.json(); }).then(function (j) {
      D = j;
      if (!D.guests) LEVELS = LEVELS.filter(function (l) { return l[0] !== "guest"; }); else guestSetup();
      then();
    })
      .catch(function (err) { if (window.console) console.error("cards:", err); DLG.querySelector(".ab-body").innerHTML = '<p class="ab-note">The cards did not load. Reload the page to try again.</p>'; });
  }
  function open(level, name, view) {
    load(function () {
      state.level = level || "nb"; state.view = view === "h2h" ? "h2h" : "card";
      var list = items(state.level), i = name ? list.map(function (x) { return x.name; }).indexOf(name) : -1;
      if (i < 0) i = list.map(function (x, j) { return [x.m.revpar || 0, j]; }).sort(function (a, b) { return b[0] - a[0]; })[0][1];
      state.a = i;
      var sorted = list.map(function (x, j) { return [x.m.revpar || 0, j]; }).sort(function (a, b) { return a[0] - b[0]; });
      state.b = sorted[0][1] === i ? sorted[sorted.length - 1][1] : sorted[0][1];
      render();
    });
    if (!DLG.open) DLG.showModal();
  }

  document.addEventListener("click", function (e) {
    var o = e.target.closest("[data-card-open]");
    if (o) { e.preventDefault(); open(o.dataset.level, o.dataset.name, o.dataset.view); return; }
    if (!DLG.contains(e.target)) {
      // the page's own tiles (the case study drawn as a card) turn over the same way
      var pt = e.target.closest(".ab-sheet [data-flip]");
      if (pt && !e.target.closest("select, button, a")) flip(pt);
      return;
    }
    if (e.target.closest(".ab-close")) { DLG.close(); return; }
    var lv = e.target.closest("[data-level]");
    if (lv && DLG.contains(lv)) { state.level = lv.dataset.level; state.page = 0; state.a = 0; state.b = 1; if (state.level === "guest") { state.gf = -1; } else if (state.level === "listing") { state.a = -1; state.b = -1; } else { var l = items(state.level); var s = l.map(function (x, j) { return [x.m.revpar || 0, j]; }).sort(function (a, b) { return b[0] - a[0]; }); state.a = s[0][1]; state.b = s[s.length - 1][1]; } render(); return; }
    var fm = e.target.closest("[data-fam]");
    if (fm && DLG.contains(fm)) { state.fam = fm.dataset.fam; render(); return; }
    if (e.target.closest(".ab-pgbtn")) { state.page = (state.page + 1) % (state.pages || 2); render(); return; }
    var gp = e.target.closest("[data-gpool]");
    if (gp && DLG.contains(gp)) { state.gpool = gp.dataset.gpool; render(); return; }
    var vw = e.target.closest(".ab-view");
    if (vw) { state.view = vw.dataset.view; render(); return; }
    if (e.target.closest("select, button, a")) return;
    var t = e.target.closest("[data-flip]");
    if (t) flip(t);
  });
  document.addEventListener("keydown", function (e) {
    var t = e.target.closest && e.target.closest("[data-flip]");
    if (t && !DLG.contains(t) && !t.closest(".ab-sheet")) return;
    if (t && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); flip(t); }
  });
  DLG.addEventListener("change", function (e) {
    if (e.target.id === "ab-a") state.a = +e.target.value;
    if (e.target.id === "ab-b") state.b = +e.target.value;
    if (e.target.id === "ab-nbf") { state.nbf = +e.target.value; state.a = -1; state.b = -1; }
    if (e.target.id === "ab-gp") { state.gpool = e.target.value; }
    if (e.target.id === "ab-fam") { state.fam = e.target.value; }
    if (e.target.id === "ab-lv") { var b = document.createElement("button"); b.dataset.level = e.target.value; DLG.querySelector(".ab-fs").appendChild(b); b.click(); return; }
    if (e.target.id === "ab-gf") { state.gf = +e.target.value; state.a = -1; state.b = -1; }
    render();
  });
  // the filter strip changes shape at 1600 px wide (buttons above, one picker below), so a resize redraws it
  var wide = window.innerWidth >= 1600;
  var tall = window.innerHeight > 960;
  window.addEventListener("resize", function () {
    if (DLG.open && D && ((window.innerWidth >= 1600) !== wide || (window.innerHeight > 960) !== tall)) { wide = window.innerWidth >= 1600; tall = window.innerHeight > 960; render(); }
  });
  function flip(t) {
    var on = !t.classList.contains("flip");
    t.classList.toggle("flip", on); t.setAttribute("aria-pressed", on ? "true" : "false");
    t.querySelector(".ab-f").setAttribute("aria-hidden", on ? "true" : "false");
    t.querySelector(".ab-b").setAttribute("aria-hidden", on ? "false" : "true");
  }
})();
