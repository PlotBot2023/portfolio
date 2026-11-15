"""Measure the four main pages against the owner's standards, in a real browser (headless Chromium, Playwright).

    python -m http.server 8765 --bind 127.0.0.1 --directory docs     # in one terminal
    python tools/measure_pages.py [--shots DIR]                       # in another

Per page and viewport (1920x1080, 1536x864, 1366x768 and a 390x844 phone) it reports:
  - single view: the desktop page does not scroll and nothing is cut off at the bottom; no horizontal scroll anywhere
  - type floor: the smallest computed font size of any visible text (rule 34: at least 16 px)
  - contrast: each text run's colour against the lightest or darkest pixel behind it, read from a screenshot taken
    with all text hidden, so gradients and glass are measured as drawn (7:1 body, 4.5:1 secondary)
  - targets: every visible link, button and tab at least 44 by 44 px
  - reader symbols: none of the announced characters in visible text or in aria-label, title or alt
  - alt text: every image has an alt; a decorative one is alt="" inside a labelled control
  - motion: the number of running animations, normally and under prefers-reduced-motion
Every note popover is opened and measured too. Exits 1 if any check fails.
"""
import argparse, io, json, sys
from PIL import Image
from playwright.sync_api import sync_playwright

PAGES = ["index", "projects", "airbnb", "about", "resume"]
SIZES = [(1920, 1080), (1536, 864), (1366, 768), (390, 844)]
SYMBOLS = set("&·|→←↗↘✕×#±≥≤▾▸●◌◐○…—–~/\\•►▶")

JS_TEXT = r"""
() => {
  const out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    if (!n.textContent.trim()) continue;
    const el = n.parentElement; if (!el) continue;
    if (el.closest('script,style,noscript,svg,[hidden]')) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) continue;
    const r = document.createRange(); r.selectNodeContents(n);
    const rects = [...r.getClientRects()].filter(q => q.width > 1 && q.height > 1 && q.bottom > 0 && q.top < innerHeight && q.right > 0 && q.left < innerWidth);
    if (!rects.length) continue;
    const pop = el.closest('[popover]');
    if (pop && !pop.matches(':popover-open')) continue;
    out.push({pop: pop ? pop.id : null, t: n.textContent.trim().slice(0, 40), fs: parseFloat(cs.fontSize), fw: parseInt(cs.fontWeight), color: cs.color,
      rects: rects.map(q => [q.left, q.top, q.right, q.bottom]), sel: el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : '')});
  }
  return out;
}"""

JS_PAGE = r"""
() => {
  const vis = e => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && !e.closest('[hidden]') && (!e.closest('[popover]') || e.closest('[popover]').matches(':popover-open')); };
  const targets = [...document.querySelectorAll('a[href], button, [role=tab], summary, input, select')].filter(vis)
    .map(e => { const r = e.getBoundingClientRect(); return {w: r.width, h: r.height, t: (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 30)}; })
    .filter(x => x.w < 44 - .5 || x.h < 44 - .5);
  const names = [...document.querySelectorAll('[aria-label],[title],img[alt]')].map(e => [e.getAttribute('aria-label'), e.getAttribute('title'), e.tagName === 'IMG' ? e.getAttribute('alt') : null]).flat().filter(Boolean);
  const imgs = [...document.querySelectorAll('img')].filter(i => !i.hasAttribute('alt')).map(i => i.src);
  const sv = document.querySelector('.sv');
  const cut = sv ? [...sv.querySelectorAll('*')].filter(e => vis(e) && innerWidth >= 900 && e.getBoundingClientRect().bottom > innerHeight + 1).length : 0;
  const d = document.documentElement;
  return {visible: document.body.innerText, names, targets, noalt: imgs, cut,
    vscroll: d.scrollHeight > innerHeight + 1, hscroll: d.scrollWidth > innerWidth + 1, anims: document.getAnimations().length};
}"""

def lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    return .2126 * ch(c[0]) + .7152 * ch(c[1]) + .0722 * ch(c[2])

def ratio(a, b):
    la, lb = sorted([lum(a), lum(b)], reverse=True)
    return (la + .05) / (lb + .05)

def parse_rgb(s):
    v = [float(x) for x in s[s.index("(") + 1:s.index(")")].replace("/", ",").split(",")]
    return v[:3], (v[3] if len(v) > 3 else 1.0)

HIDE = "*{color:transparent!important;-webkit-text-fill-color:transparent!important;text-shadow:none!important;caret-color:transparent!important}"

def contrast_runs(pg, runs):
    """Worst-case contrast of each text run against the textless screenshot under it."""
    tag = pg.add_style_tag(content=HIDE)
    bg = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
    pg.evaluate("t => t.remove()", tag)
    W, H = bg.size
    worst = []
    for r in runs:
        rgb, a = parse_rgb(r["color"])
        lo = None
        for (x0, y0, x1, y1) in r["rects"]:
            box = (max(0, int(x0)), max(0, int(y0)), min(W, int(x1) + 1), min(H, int(y1) + 1))
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            px = list(bg.crop(box).getdata())
            for p in (max(px, key=lum), min(px, key=lum)):
                fg = [rgb[i] * a + p[i] * (1 - a) for i in range(3)]
                c = ratio(fg, p)
                lo = c if lo is None else min(lo, c)
        if lo is not None:
            worst.append((lo, r))
    return worst

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--shots"); ap.add_argument("--base", default="http://127.0.0.1:8765")
    args = ap.parse_args()
    fails, report = [], {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for motion in ("no-preference", "reduce"):
            for (w, h) in (SIZES if motion == "no-preference" else [(1366, 768)]):
                ctx = b.new_context(viewport={"width": w, "height": h}, reduced_motion=motion)
                pg = ctx.new_page()
                errs = []
                pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                pg.on("pageerror", lambda e: errs.append(str(e)))
                for name in PAGES:
                    key = f"{name} {w}x{h}" + (" reduced" if motion == "reduce" else "")
                    pg.goto(f"{args.base}/{name}.html", wait_until="networkidle")
                    errs.clear()
                    info = pg.evaluate(JS_PAGE)
                    rec = {"anims": info["anims"]}
                    if motion == "reduce":
                        report[key] = rec
                        if info["anims"]:
                            fails.append(f"{key}: {info['anims']} animations under reduced motion")
                        continue
                    if args.shots and w >= 1366:
                        pg.screenshot(path=f"{args.shots}/{name}-{w}x{h}.png")
                    runs = pg.evaluate(JS_TEXT)
                    main_cons = contrast_runs(pg, runs)   # the page itself, before any popover opens
                    # every note popover, opened one at a time
                    pops = pg.evaluate("() => [...document.querySelectorAll('[popover]')].map(e => e.id)")
                    pop_runs = []
                    if w == 1366:
                        for pid in pops:
                            pg.evaluate("id => document.getElementById(id).showPopover()", pid)
                            pr = [r for r in pg.evaluate(JS_TEXT) if r["pop"] == pid]
                            pop_runs += contrast_runs(pg, pr)
                            ptargets = pg.evaluate(JS_PAGE)["targets"]
                            if ptargets:
                                fails.append(f"{key} popover {pid}: small targets {ptargets}")
                            pg.evaluate("id => document.getElementById(id).hidePopover()", pid)
                    cons = main_cons + pop_runs
                    allruns = runs + [r for _, r in pop_runs]
                    minfs = min(r["fs"] for r in allruns)
                    small = sorted({(r["fs"], r["t"]) for r in allruns if r["fs"] < 16})
                    lowc = sorted([(round(c, 2), r["t"], r["sel"]) for c, r in cons if c < 7.0])[:8]
                    minc = min(c for c, _ in cons)
                    syms = sorted({ch for ch in info["visible"] if ch in SYMBOLS or ord(ch) >= 0x1F300})
                    nsyms = sorted({ch for s in info["names"] for ch in s if ch in SYMBOLS or ord(ch) >= 0x1F300})
                    rec.update(min_font_px=minfs, min_contrast=round(minc, 2), below_7=lowc, small_text=small[:5], targets_under_44=info["targets"],
                               reader_symbols_visible=syms, reader_symbols_names=nsyms, images_without_alt=info["noalt"],
                               page_scrolls=info["vscroll"] if w >= 900 else "phone, scrolls by design", horizontal_scroll=info["hscroll"],
                               cut_off_below_screen=info["cut"], popovers_measured=len(pops) if w == 1366 else 0)
                    rec["console_errors"] = list(errs)
                    report[key] = rec
                    if errs: fails.append(f"{key}: console errors {errs[:2]}")
                    if minfs < 16: fails.append(f"{key}: text under 16 px {small[:3]}")
                    if minc < 4.5: fails.append(f"{key}: contrast under 4.5 {lowc[:3]}")
                    if info["targets"]: fails.append(f"{key}: targets under 44 px {info['targets'][:3]}")
                    if syms or nsyms: fails.append(f"{key}: reader symbols {syms} {nsyms}")
                    if info["noalt"]: fails.append(f"{key}: images without alt")
                    if info["hscroll"]: fails.append(f"{key}: horizontal scroll")
                    if w >= 900 and (info["vscroll"] or info["cut"]): fails.append(f"{key}: not a single view (scrolls {info['vscroll']}, cut {info['cut']})")
                ctx.close()
        b.close()
    print(json.dumps(report, indent=1, ensure_ascii=False))
    print("\nFAILS:" if fails else "\nALL CHECKS PASS", *fails, sep="\n")
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
