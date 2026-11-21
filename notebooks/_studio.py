"""The site's look for the Broward notebooks' matplotlib figures (the owner, 2026-11-17: "all the notebooks needs the
same upgrades visually").

One call, `studio.apply()`, at the top of a notebook: the charcoal ground with a soft colour bleed, recessed chart wells
with HUD corner brackets (cyan at the top, pink at the foot), big type, identity hues that are never a value, glowing
lines, ringed dots, and every figure saved at 2x. Each figure is finished when it is shown, so a notebook's own plotting
code stays as it is. The values follow the SportsAnalytics brand kit (shared/brand/tokens.py: HEAT_*, TEND_*, the Studies
charcoal glass), copied as values because the site cannot import that repository; the reference build is BrowardAirbnbV2
experiments/income_model/e2e_amenity_spread/studio.py.
"""
from __future__ import annotations

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgb
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Rectangle

HEAT_POS = ["#D1F2D3", "#90E199", "#6DC97A", "#389E4C"]      # +1 .. +4 green: a result, better
HEAT_NEG = ["#F7EC94", "#E9CD6B", "#F39B44", "#E8574F"]      # -1 .. -4 yellow to red: a result, worse
HEAT_EVEN = "#FFFFFF"
TEND_LO = ["#CFFAFE", "#A5F3FC", "#67E8F9", "#22D3EE"]       # a tendency, less often: cyan
TEND_HI = ["#FCE7F3", "#FBCFE8", "#F9A8D4", "#F472B6"]       # a tendency, more often: pink
TEND_MID = "#E5E7EB"
Z_CUTS = [0.25, 0.75, 1.25, 2.0]

GROUND = "#1C1E27"
WELL = "#11131A"
EDGE = "#3A3F52"
CY, PK, AMBER, GOLD, TEAL, SKY, LIME = "#6EE7F5", "#F46BB4", "#F7A15A", "#FFC72C", "#2DD4BF", "#60A5FA", "#A3E635"
INK, INK2, MUTE = "#F5F6FA", "#CDD2DE", "#AEB4C4"
# identity hues for categories (never a value): cyan, amber, pink, teal, gold, sky, lime
PAL = [CY, AMBER, PK, TEAL, GOLD, SKY, LIME]


def step(z: float) -> int:
    return int(sum(abs(z) >= c for c in Z_CUTS))


def heat(z: float) -> str:
    """A result's colour by its z: green better, red worse, white about even."""
    s = step(z)
    return HEAT_EVEN if s == 0 else (HEAT_POS if z > 0 else HEAT_NEG)[s - 1]


def tend(z: float) -> str:
    """A tendency's colour by its z: pink more often, cyan less often."""
    s = step(z)
    return TEND_MID if s == 0 else (TEND_HI if z > 0 else TEND_LO)[s - 1]


def zs(v) -> np.ndarray:
    v = np.asarray(v, float)
    sd = np.nanstd(v)
    return (v - np.nanmean(v)) / sd if sd > 0 else np.zeros_like(v)


def heat_colors(values, higher_is_better: bool = True) -> list:
    z = zs(values) * (1 if higher_is_better else -1)
    return [heat(x) for x in z]


def _cmaps():
    from matplotlib.colors import LinearSegmentedColormap
    gyor = LinearSegmentedColormap.from_list("studio_gyor", HEAT_NEG[::-1] + [HEAT_EVEN] + HEAT_POS)     # low red .. high green
    tendc = LinearSegmentedColormap.from_list("studio_tend", TEND_LO[::-1] + [TEND_MID] + TEND_HI)      # less cyan .. more pink
    return gyor, tendc


GYOR, TEND = _cmaps()

_orig_show = plt.show


def apply() -> None:
    """Set the look for every figure the notebook draws from here on."""
    plt.rcParams.update({
        "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 15, "axes.titlesize": 19, "axes.titleweight": "bold",
        "axes.titlepad": 14, "axes.labelsize": 16, "axes.labelweight": "bold", "xtick.labelsize": 14, "ytick.labelsize": 14,
        "legend.fontsize": 14, "legend.title_fontsize": 14, "figure.titlesize": 24, "figure.titleweight": "black",
        "figure.facecolor": GROUND, "axes.facecolor": WELL, "savefig.facecolor": GROUND, "savefig.edgecolor": GROUND,
        "axes.edgecolor": EDGE, "axes.labelcolor": INK2, "axes.titlecolor": INK, "text.color": INK2,
        "xtick.color": MUTE, "ytick.color": MUTE, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": CY, "grid.alpha": 0.08, "grid.linewidth": 1.0,
        "axes.prop_cycle": plt.cycler(color=PAL), "lines.linewidth": 3.0, "lines.markersize": 8,
        "patch.edgecolor": "none", "legend.facecolor": "#232634", "legend.edgecolor": EDGE, "legend.framealpha": 0.95,
        "legend.labelcolor": INK2, "figure.dpi": 100, "savefig.dpi": 200, "figure.constrained_layout.use": False,
        "axes.unicode_minus": True, "image.cmap": "viridis",
    })
    try:  # a notebook's inline figures at 2x
        from IPython import get_ipython
        ip = get_ipython()
        if ip is not None:
            ip.run_line_magic("config", "InlineBackend.figure_formats = ['retina']")
            ip.run_line_magic("config", "InlineBackend.print_figure_kwargs = {'facecolor': '%s', 'bbox_inches': 'tight'}" % GROUND)
    except Exception:  # noqa: BLE001 - outside IPython the rcParams are enough
        pass
    plt.show = show


def _brackets(ax, n=0.05):
    """HUD corner brackets on a chart well: cyan at the top corners, pink at the foot."""
    kw = dict(transform=ax.transAxes, clip_on=False, lw=2.6, solid_capstyle="round", zorder=30)
    for x, sx in ((0, 1), (1, -1)):
        ax.add_line(Line2D([x, x + sx * n], [1, 1], color=CY, **kw))
        ax.add_line(Line2D([x, x], [1, 1 - n * 1.6], color=CY, **kw))
        ax.add_line(Line2D([x, x + sx * n], [0, 0], color=PK, **kw))
        ax.add_line(Line2D([x, x], [0, n * 1.6], color=PK, **kw))


def _ground(fig):
    """The ground: charcoal with a soft cyan, amber and pink bleed."""
    if getattr(fig, "_studio_ground", False):
        return
    bg = fig.add_axes([0, 0, 1, 1], zorder=-20)
    bg.set_axis_off()
    H, W = 120, 200
    yy, xx = np.mgrid[0:H, 0:W]
    xx, yy = xx / W, yy / H
    img = np.ones((H, W, 3)) * np.array(to_rgb(GROUND))
    for (cx, cy, r, a), col in zip(((0.05, 0.02, 0.6, 0.16), (0.97, 0.98, 0.6, 0.10), (0.9, 0.05, 0.5, 0.08)), (CY, AMBER, PK)):
        m = np.exp(-(((xx - cx) * 1.6) ** 2 + (yy - cy) ** 2) / (2 * (r / 2.2) ** 2)) * a
        img = img * (1 - m[..., None]) + np.array(to_rgb(col)) * m[..., None]
    bg.imshow(img, extent=[0, 1, 0, 1], aspect="auto", origin="upper", zorder=-20)
    fig._studio_ground = True


def _finish_axes(ax):
    if not ax.get_visible() or ax.get_label() == "<colorbar>" or not ax.axison:
        return
    ax.set_facecolor(WELL)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(EDGE)
        ax.spines[s].set_linewidth(1.4)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTE, length=0, pad=8)
    ax.title.set_color(INK)
    ax.xaxis.label.set_color(INK2)
    ax.yaxis.label.set_color(INK2)
    glow = [pe.Stroke(linewidth=8, alpha=0.18), pe.Normal()]
    for ln in ax.get_lines():
        if ln.get_linewidth() >= 1.5 and ln.get_linestyle() in ("-", "solid"):
            ln.set_path_effects(glow)
    for coll in ax.collections:
        try:
            if coll.get_offsets().shape[0] > 0 and hasattr(coll, "get_sizes") and len(coll.get_sizes()):
                coll.set_edgecolor("#07080C")
                coll.set_linewidth(0.6)
        except Exception:  # noqa: BLE001 - a collection without offsets (a fill, a hexbin) stays as it is
            pass
    rects = [p for p in ax.patches if isinstance(p, Rectangle) and p.get_width() != 0 and p.get_height() != 0]
    for p in rects:   # a light top edge on a few bars; a histogram's many bars stay clean
        p.set_edgecolor((1, 1, 1, 0.22) if len(rects) <= 30 else (0, 0, 0, 0))
        p.set_linewidth(1.0)
    leg = ax.get_legend()
    if leg is not None:
        leg.get_frame().set_facecolor("#232634")
        leg.get_frame().set_edgecolor(EDGE)
        for t in leg.get_texts():
            t.set_color(INK2)
    for t in ax.texts:
        if t.get_color() in ("black", "#000000", "k", (0, 0, 0, 1)):
            t.set_color(INK)
    _brackets(ax)


def finish(fig=None):
    """The ground, the wells, a hue rail under the figure title; idempotent, so showing twice is harmless."""
    fig = fig or plt.gcf()
    _ground(fig)
    from matplotlib.text import Text
    for txt in fig.findobj(Text):          # the floor: no figure text under 13 pt (18 px at the 2x save, read at page width)
        if txt.get_text() and txt.get_fontsize() < 13:
            txt.set_fontsize(13)
    for ax in fig.axes:
        if ax.get_zorder() > -20:
            _finish_axes(ax)
    st = getattr(fig, "_suptitle", None)
    if st is not None and st.get_text() and st.get_fontsize() < 20:
        st.set_fontsize(20)
    if st is not None and st.get_text() and not getattr(fig, "_studio_rail", False):
        st.set_color(INK)
        st.set_fontweight("black")
        rail = fig.add_axes([0.02, 0.0, 0.96, 0.004], zorder=40)
        rail.set_axis_off()
        rail.imshow(np.linspace(0, 1, 256)[None, :], cmap=_rail_cmap(), aspect="auto", extent=[0, 1, 0, 1])
        x0, y0 = st.get_position()
        rail.set_position([0.02, min(0.985, y0 + 0.012), 0.96, 0.004])
        fig._studio_rail = True
    return fig


def _rail_cmap():
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list("studio_rail", [CY, SKY, PK, AMBER])


def show(*args, **kwargs):
    for num in plt.get_fignums():
        finish(plt.figure(num))
    return _orig_show(*args, **kwargs)


def pill_box(ax, x, y, text, color=INK, fc="#2E3142", size=13, **kw):
    """A raised pill label (a value next to a bar or a dot)."""
    return ax.text(x, y, text, color=color, fontsize=size, fontweight="bold", ha=kw.pop("ha", "center"), va=kw.pop("va", "center"),
                   bbox=dict(boxstyle="round,pad=0.35,rounding_size=0.8", fc=fc, ec="#07080C", lw=1.2), zorder=25, **kw)


__all__ = ["apply", "finish", "show", "GYOR", "TEND", "heat", "tend", "zs", "heat_colors", "pill_box", "PAL",
           "CY", "PK", "AMBER", "GOLD", "TEAL", "SKY", "LIME", "INK", "INK2", "MUTE", "GROUND", "WELL", "FancyBboxPatch"]
