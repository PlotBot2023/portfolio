// The case study's cards: a neighbourhood, an ML segment, a host or a listing as a player card (flip tiles: a number,
// its z against the cards of its level, a bead slider; turn a tile over for the homes behind the number), and a
// head-to-head board of two cards of one level. Data: cards.json, built by tools/airbnb_cards.py. No names or ids.
(function () {
  "use strict";
  var DLG = document.getElementById("ab-cards");
  if (!DLG) return;
  var D = null, state = { level: "nb", a: 0, b: 1, view: "card", nbf: 0, fam: "rev" };
  var LEVELS = [["nb", "Neighbourhood"], ["seg", "ML segment"], ["host", "Host"], ["listing", "Listing"]];
  var LWORD = { nb: "neighbourhoods", seg: "segments", host: "hosts", listing: "listings" };
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
    resid: { l: "Beats model", full: "Actual RevPAR minus the model's prediction (XGBoost occupancy model)", per: "a night", f: "smoney", hue: "#34D399", src: "MDL" },
    mood: { l: "Review mood", full: "Mean VADER sentiment of its reviews, minus 1 to plus 1", per: "", f: "mood", hue: "#FBBF24", src: "NLP" },
    cap: { l: "Cap rate", full: "Net operating income over the ZIP's home value", per: "", f: "pct1", hue: "#38BDF8", src: "MDL" },
    noi: { l: "NOI", full: "Net operating income a year, after operating costs", per: "a year", f: "moneyk", hue: "#A78BFA", src: "MDL" },
    anom: { l: "Anomalies", full: "Share of its homes the IsolationForest flags as anomalous", per: "of homes", f: "pct", hue: "#FB7185", src: "MDL", share: true, dir: -1 },
    bedrooms: { l: "Bedrooms", full: "Bedrooms", per: "", f: "int", hue: "#60A5FA", src: "LST", plain: true },
    superhost: { l: "Superhost", full: "Run by a Superhost", per: "", f: "yes", hue: "#CBD5E1", src: "LST", plain: true }
  };
  var TILES = { group: ["adr", "occ", "rev", "rev_bed", "clear50", "super"], listing: ["adr", "occ", "rev", "rev_bed", "bedrooms", "superhost"],
    models: ["churn", "resid", "mood", "cap", "noi", "anom"], models_listing: ["churn", "resid", "mood", "cap", "noi", "anom"] };
  var FAMS = [["rev", "Revenue"], ["models", "Models"]];
  var ROWS = ["revpar", "adr", "occ", "rev", "rev_bed", "clear50", "super"], MROWS = ["revpar", "churn", "resid", "mood", "cap", "noi", "anom"];

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function fmt(k, v) {
    if (v == null || isNaN(v)) return "none";
    var f = M[k].f;
    if (f === "money") return "$" + Math.round(v).toLocaleString("en-US");
    if (f === "moneyk") return Math.abs(v) >= 1e6 ? "$" + (v / 1e6).toFixed(1) + "M" : Math.abs(v) >= 1000 ? "$" + (v / 1000).toFixed(Math.abs(v) >= 10000 ? 0 : 1) + "k" : "$" + Math.round(v);
    if (f === "smoney") return (v > 0 ? "+" : v < 0 ? "-" : "") + "$" + Math.abs(Math.round(v)).toLocaleString("en-US");
    if (f === "mood") return (v > 0 ? "+" : "") + v.toFixed(2);
    if (f === "pct1") return v.toFixed(1) + "%";
    if (f === "pct") return Math.round(v) + "%";
    if (f === "yes") return v ? "Yes" : "No";
    return String(Math.round(v));
  }
  function gap(k, a, b) {
    var d = Math.abs(a - b), f = M[k].f;
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
  function pool(level, k) {
    var key = level + ":" + k;
    if (POOL[key]) return POOL[key];
    var vals = items(level).map(function (x) { return x.m[k]; }).filter(function (v) { return v != null && !isNaN(v); }).sort(function (x, y) { return x - y; });
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
          cap: ix.cap != null ? r[ix.cap] : null, noi: ix.noi != null ? r[ix.noi] : null, anom: ix.anom != null ? r[ix.anom] : null } };
    });
    return LISTING_CACHE;
  }
  function items(level) { return level === "listing" ? listingItems() : D.levels[level]; }
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
    var who = x.h ? "Its " + x.n.toLocaleString("en-US") + " homes" : "All " + D.homes.toLocaleString("en-US") + " entire homes in the county, this one marked";
    return '<div class="ab-cols"><div class="plot">' + cols + '</div><div class="axis"><i>' + fmt(k, e[0]) + "</i><i>" + fmt(k, e[e.length - 1]) + "</i></div><p>" + esc(who) + "</p></div>";
  }
  function shareBar(k, v) {
    if (v == null) return "";
    var c = D.county[k] == null ? 0 : D.county[k], w = Math.max(0, Math.min(100, v));
    return '<div class="ab-share"><span class="trk"><span class="fill" style="width:' + w.toFixed(1) + '%"></span><span class="cty" style="left:' + c.toFixed(1) + '%"></span></span>'
      + '<span class="lg"><i>' + esc(fmt(k, v) + " " + (M[k].per || "")) + "</i><i>county " + esc(fmt(k, c)) + "</i></span></div>";
  }
  function tile(x, k, hero) {
    var d = M[k], v = x.m[k], z = zOf(state.level, k, v), r = d.plain || v == null ? null : rankOf(state.level, k, v);
    var rk = r ? "rank " + r.rank.toLocaleString("en-US") + " of " + r.of.toLocaleString("en-US") : "";
    function hd(small) { return '<div class="ab-th"><i></i><span class="t">' + esc(d.l) + "</span>" + (small ? "<small>" + esc(small) + "</small>" : "") + '<span class="ab-fh" aria-hidden="true">↻</span></div>'; }
    var head = hd(rk);
    var q = x.q && x.q[k] ? "middle half " + fmt(k, x.q[k][0]) + " to " + fmt(k, x.q[k][1]) : "";
    var extra = hero ? '<div class="ab-hx"><div><span>Expected revenue a year</span><b>' + fmt("rev", x.m.rev) + "</b></div><div><span>County median RevPAR</span><b>" + fmt("revpar", D.county.revpar) + "</b></div></div>" : "";
    var front = '<div class="ab-face ab-f">' + head + '<div class="ab-tv"><b>' + fmt(k, v) + "</b>" + (d.per ? '<span class="per">' + esc(d.per) + "</span>" : "") + gem(z) + "</div>"
      + slider(z) + (hero ? strip(x, k, false) + extra : M[k].share ? shareBar(k, v) : strip(x, k, false)) + "</div>";
    var back = '<div class="ab-face ab-b" aria-hidden="true">' + hd(x.h ? (M[k].share ? "" : "median ") + fmt(k, v) : "this home " + fmt(k, v))
      + (D.edges[k] ? strip(x, k, true) : '<div class="ab-cols"><p>' + esc(M[k].full) + ": " + esc(fmt(k, v)) + (D.county[k] != null ? ", against " + esc(fmt(k, D.county[k])) + " across the county" : "") + ".</p>" + (M[k].share ? shareBar(k, v) : "") + "</div>")
      + (q ? '<p class="q">' + esc(q) + "</p>" : "") + "</div>";
    var label = d.full + ", " + fmt(k, v) + (z == null ? "" : ", " + (z >= .25 ? "above" : z <= -.25 ? "below" : "near") + " the " + LWORD[state.level] + " average, z " + z.toFixed(1)) + (r ? ", rank " + r.rank + " of " + r.of : "") + ". Turn over for the homes behind it.";
    return '<div class="ab-t' + (hero ? " hero" : "") + '" style="--sh:' + d.hue + '" data-flip role="button" tabindex="0" aria-pressed="false" aria-label="' + esc(label) + '"><div class="ab-in">' + front + back + "</div></div>";
  }

  function picker(id, idx, label) {
    var opts;
    if (state.level === "listing") opts = listingChoices().map(function (p) { return '<option value="' + p[1] + '"' + (p[1] === idx ? " selected" : "") + ">" + esc(p[0].code + ", " + p[0].name + ", " + fmt("revpar", p[0].m.revpar)) + "</option>"; });
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
  function band(x) {
    var r = rankOf(state.level, "revpar", x.m.revpar), z = zOf(state.level, "revpar", x.m.revpar);
    var lvl = LEVELS.filter(function (l) { return l[0] === state.level; })[0][1];
    return '<div class="ab-disc" aria-hidden="true">' + (state.level === "listing" ? "L" : state.level === "host" ? "H" : state.level === "seg" ? "ML" : "N") + "</div>"
      + '<div class="ab-id"><span class="eyebrow">' + esc(lvl + ", Broward County, " + D.asof) + '</span><p id="ab-title" class="ab-name' + (x.name.length > 18 ? " long" : "") + '" role="heading" aria-level="2">' + esc(x.name) + '</p>' + subLine(x) + '<p class="ab-deck">' + deck(x) + "</p></div>"
      + '<div class="ab-chips"><span class="ab-chip rk ' + heat(z) + '"><i>Rank</i><b>' + r.rank.toLocaleString("en-US") + "</b><small>of " + r.of.toLocaleString("en-US") + "</small></span>"
      + '<span class="ab-chip"><i>Priced</i><b>' + x.n.toLocaleString("en-US") + '</b></span><span class="ab-chip gold"><i>Data</i><b>Measured</b></span></div>';
  }

  function cardView() {
    var list = items(state.level), x = list[state.a] || list[0], fam = D.models ? state.fam : "rev";
    var keys = fam === "models" ? TILES.models : state.level === "listing" ? TILES.listing : TILES.group;
    var notes = state.level === "seg" ? '<p class="ab-note">' + esc(D.seg_meta.method) + ". Titles follow a rule on each group's rate and calendar against the county's medians, so a refit renames itself. Homes whose nightly price was a placeholder are not segmented.</p>"
      : state.level === "host" ? '<p class="ab-note">Hosts with ' + D.host_min + " or more entire homes, coded by size. No names or Airbnb ids: most hosts are private people.</p>"
      : state.level === "listing" ? '<p class="ab-note">Each listing is coded by its RevPAR rank. No names, ids or links. Its tiles turn over to the county with this home marked.</p>' : "";
    if (fam === "models") notes = '<p class="ab-note">' + esc(D.models.src) + ". Matched by listing id to " + D.models.matched.toLocaleString("en-US") + " of these " + D.models.of.toLocaleString("en-US")
      + " homes" + (x.matched != null ? "; this card, " + x.matched.toLocaleString("en-US") + " of its " + x.n.toLocaleString("en-US") : "") + ". Model revenue there is the asking price times occupancy, an estimate; RevPAR on the hero tile is measured.</p>";
    return '<div class="ab-tiles">' + tile(x, "revpar", true) + keys.map(function (k) { return tile(x, k, false); }).join("") + "</div>" + notes;
  }

  function h2hView() {
    var list = items(state.level), A = list[state.a] || list[0], B = list[state.b] || list[1] || list[0];
    var keys = D.models && state.fam === "models" ? MROWS : state.level === "listing" ? ROWS.slice(0, 5) : ROWS;
    function side(x, k, right) {
      var v = x.m[k], z = zOf(state.level, k, v), r = v == null ? null : rankOf(state.level, k, v);
      var bar = z == null ? '<span class="vl"><span class="mid"></span></span>' : (function () {
        var w = Math.min(50, 50 * Math.abs(z) / 3), left = z >= 0 ? 50 : 50 - w;
        return '<span class="vl"><span class="mid"></span><span class="fill ' + heat(z) + '" style="left:' + left.toFixed(1) + "%;width:" + w.toFixed(1) + '%"></span></span>';
      })();
      var parts = [strip(x, k, false) || '<span class="ab-mini" aria-hidden="true"></span>', '<span class="pill">' + fmt(k, v) + "</span>", bar, '<span class="rk">' + (r ? r.rank.toLocaleString("en-US") : "") + "</span>"];
      if (right) parts.reverse();
      return '<div class="side' + (right ? " r" : "") + '">' + parts.join("") + "</div>";
    }
    var rows = keys.map(function (k) {
      var a = A.m[k], b = B.m[k], apart = a == null || b == null ? "" : gap(k, a, b);
      var lead = a == null || b == null || a === b ? "" : ((M[k].dir === -1 ? a < b : a > b) ? A : B).name;
      return '<div class="ab-row" role="row" aria-label="' + esc(M[k].full + ": " + A.name + " " + fmt(k, a) + ", " + B.name + " " + fmt(k, b) + (lead ? ", " + lead + " higher" : "")) + '">' + side(A, k, false)
        + '<div class="mid"><span class="src">' + M[k].src + '</span><span class="lbl">' + esc(M[k].l) + "</span>" + (apart ? '<span class="apart">' + esc(apart) + "</span>" : "") + "</div>" + side(B, k, true) + "</div>";
    }).join("");
    function head(x, right) {
      var z = zOf(state.level, "revpar", x.m.revpar), r = rankOf(state.level, "revpar", x.m.revpar);
      return '<div class="hd' + (right ? " r" : "") + '"><div><b>' + esc(x.name) + '</b><small>' + esc(x.sub) + '</small></div><span class="ab-chip rk ' + heat(z) + '"><b>' + r.rank + '</b><small>of ' + r.of + '</small></span><span class="ab-gem ' + heat(z) + '"><span aria-hidden="true">' + glyph(z) + "</span> " + fmt("revpar", x.m.revpar) + " RevPAR</span></div>";
    }
    return '<div class="ab-h2h"><div class="ab-hh">' + head(A, false) + '<span class="vs">VS</span>' + head(B, true) + '</div><div class="ab-hcols" aria-hidden="true"><i>Its homes</i><i>Value</i><i>Against the ' + esc(LWORD[state.level]) + '</i><i>Rank</i><i>Stat, edge</i><i>Rank</i><i>Against the ' + esc(LWORD[state.level]) + '</i><i>Value</i><i>Its homes</i></div><div class="ab-rows" role="table" aria-label="Head to head">' + rows + "</div></div>";
  }

  function render() {
    var list = items(state.level), x = list[state.a] || list[0];
    if (state.level === "listing") {
      var ch = listingChoices();
      if (!ch.some(function (p) { return p[1] === state.a; })) state.a = ch.length ? ch[0][1] : 0;
      if (!ch.some(function (p) { return p[1] === state.b; })) state.b = ch.length > 1 ? ch[ch.length - 1][1] : state.a;
      x = list[state.a];
    }
    DLG.querySelector(".ab-band").innerHTML = band(x);
    var lv = LEVELS.map(function (l) { return '<button type="button" class="ab-seg" data-level="' + l[0] + '" aria-pressed="' + (l[0] === state.level) + '">' + l[1] + "</button>"; }).join("");
    var fams = D.models ? '<div class="ab-segs ab-fam" role="group" aria-label="Stat family">' + FAMS.map(function (f) { return '<button type="button" class="ab-seg" data-fam="' + f[0] + '" aria-pressed="' + (f[0] === state.fam) + '">' + f[1] + "</button>"; }).join("") + "</div>" : "";
    var pick = fams + (state.level === "listing" ? nbFilter() : "") + picker("ab-a", state.a, state.view === "h2h" ? "Left" : "Card") + (state.view === "h2h" ? picker("ab-b", state.b, "Right") : "");
    DLG.querySelector(".ab-fs").innerHTML = '<div class="ab-segs" role="group" aria-label="Level">' + lv + "</div>" + pick
      + '<span class="ab-count"><b>' + items(state.level).length.toLocaleString("en-US") + "</b> " + LWORD[state.level] + "</span>";
    DLG.querySelectorAll(".ab-view").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.view === state.view)); });
    DLG.querySelector(".ab-body").innerHTML = state.view === "h2h" ? h2hView() : cardView();
  }

  function load(then) {
    if (D) return then();
    DLG.querySelector(".ab-body").innerHTML = '<p class="ab-note">Loading the cards.</p>';
    fetch(DLG.dataset.src).then(function (r) { return r.json(); }).then(function (j) { D = j; then(); })
      .catch(function (err) { if (window.console) console.error("cards:", err); DLG.querySelector(".ab-body").innerHTML = '<p class="ab-note">The cards did not load. Reload the page to try again.</p>'; });
  }
  function open(level, name) {
    load(function () {
      state.level = level || "nb"; state.view = "card";
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
    if (o) { e.preventDefault(); open(o.dataset.level, o.dataset.name); return; }
    if (!DLG.contains(e.target)) return;
    if (e.target.closest(".ab-close")) { DLG.close(); return; }
    var lv = e.target.closest("[data-level]");
    if (lv && DLG.contains(lv)) { state.level = lv.dataset.level; state.a = 0; state.b = 1; if (state.level === "listing") { state.a = -1; state.b = -1; } else { var l = items(state.level); var s = l.map(function (x, j) { return [x.m.revpar || 0, j]; }).sort(function (a, b) { return b[0] - a[0]; }); state.a = s[0][1]; state.b = s[s.length - 1][1]; } render(); return; }
    var fm = e.target.closest("[data-fam]");
    if (fm && DLG.contains(fm)) { state.fam = fm.dataset.fam; render(); return; }
    var vw = e.target.closest(".ab-view");
    if (vw) { state.view = vw.dataset.view; render(); return; }
    if (e.target.closest("select, button, a")) return;
    var t = e.target.closest("[data-flip]");
    if (t) flip(t);
  });
  DLG.addEventListener("keydown", function (e) {
    var t = e.target.closest && e.target.closest("[data-flip]");
    if (t && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); flip(t); }
  });
  DLG.addEventListener("change", function (e) {
    if (e.target.id === "ab-a") state.a = +e.target.value;
    if (e.target.id === "ab-b") state.b = +e.target.value;
    if (e.target.id === "ab-nbf") { state.nbf = +e.target.value; state.a = -1; state.b = -1; }
    render();
  });
  function flip(t) {
    var on = !t.classList.contains("flip");
    t.classList.toggle("flip", on); t.setAttribute("aria-pressed", on ? "true" : "false");
    t.querySelector(".ab-f").setAttribute("aria-hidden", on ? "true" : "false");
    t.querySelector(".ab-b").setAttribute("aria-hidden", on ? "false" : "true");
  }
})();
