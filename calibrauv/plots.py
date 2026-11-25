"""Plots with four libraries: Matplotlib, Seaborn, Plotly and Altair.

One `Design` object controls the look of every library (palette, markers, lines,
grid, legend, labels, what to show), so the figure on screen is the one exported.

Publication output (Matplotlib/Seaborn):
  * exact final size in millimetres (journal column widths) with constrained layout;
  * fonts in points at final size, Arial/Helvetica or Times (metric-compatible
    fallbacks on Linux), embedded as TrueType (Type 42) in PDF/EPS, editable text in SVG;
  * no transparency (bands are pre-blended solid colours), so PDF, EPS and TIFF print alike;
  * vector PDF/SVG/EPS, or TIFF (LZW, lossless) / PNG up to 1200 dpi.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field, replace

import altair as alt
import matplotlib
import matplotlib.font_manager  # noqa: F401

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import seaborn as sns  # noqa: E402
from matplotlib.ticker import AutoMinorLocator  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402
from scipy import stats  # noqa: E402

from .i18n import t  # noqa: E402

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)   # silence font fallbacks

BLUE, ORANGE, GREEN, RED, GREY = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#7f7f7f"

# Colour roles: (curve & standards, samples, LOD, LOQ). All colour-blind friendly except
# "classic"; "grayscale" is for black-and-white print.
PALETTES = {
    "okabe_ito": ("#0072B2", "#E69F00", "#D55E00", "#009E73"),
    "seaborn_colorblind": ("#0173B2", "#DE8F05", "#D55E00", "#029E73"),
    "viridis": ("#31688E", "#B5DE2B", "#440154", "#35B779"),
    "cividis": ("#00336F", "#C6A84F", "#575C6D", "#8C8A7A"),
    "tableau": ("#4E79A7", "#F28E2B", "#E15759", "#59A14F"),
    "deep": ("#4C72B0", "#DD8452", "#C44E52", "#55A868"),
    "grayscale": ("#000000", "#555555", "#000000", "#000000"),
}
THEMES = ["journal", "seaborn_ticks", "seaborn_whitegrid", "seaborn_darkgrid", "classic", "dark"]
MARKERS = {"o": "circle", "s": "square", "^": "triangle-up", "D": "diamond", "v": "triangle-down"}
LEGEND_POS = ["upper left", "lower right", "outside", "none"]
JOURNAL_WIDTHS_MM = {"single": 85.0, "onehalf": 114.0, "double": 174.0}
FONT_FAMILIES = {
    "sans": ["Arial", "Helvetica", "Liberation Sans", "FreeSans", "DejaVu Sans"],
    "serif": ["Times New Roman", "Times", "Liberation Serif", "FreeSerif", "DejaVu Serif"],
}
EXPORT_FORMATS = {"pdf": "application/pdf", "svg": "image/svg+xml", "eps": "application/postscript",
                  "tiff": "image/tiff", "png": "image/png"}
VECTOR_FORMATS = {"pdf", "svg", "eps"}


@dataclass
class Design:
    theme: str = "journal"
    palette: str = "okabe_ito"
    curve_color: str | None = None        # None → palette
    sample_color: str | None = None
    marker: str = "o"
    marker_scale: float = 1.0
    line_scale: float = 1.0
    grid: str = "y"                      # none | y | both
    minor_ticks: bool = True
    legend: str = "upper left"
    show_title: bool = False
    show_bands: bool = True
    show_lod: bool = True
    show_samples: bool = True
    show_labels: bool = True
    show_equation: bool = True
    replicate_means: bool = False        # mean ± SD per level instead of every replicate
    residual_lines: bool = False         # vertical segments from each point to the line
    x_from_zero: bool = True
    xlabel: str = ""                     # "" → automatic
    ylabel: str = ""
    font: str = "sans"
    font_size: float = 8.0
    width_mm: float = 85.0
    height_mm: float = 65.0
    panel_letters: bool = True
    extra: dict = field(default_factory=dict)

    @property
    def colors(self):
        main, unk, lod, loq = PALETTES.get(self.palette, PALETTES["okabe_ito"])
        return (self.curve_color or main, self.sample_color or unk, lod, loq)

    @property
    def gray(self) -> bool:
        return self.palette == "grayscale"


def equation(res: dict, dec: int = 5) -> str:
    b = res["coefficients"]["slope"]["estimate"]
    inter = res["coefficients"]["intercept"]
    if inter is None:
        return f"A = {b:.{dec}f}·C"
    a = inter["estimate"]
    return f"A = {b:.{dec}f}·C {'+' if a >= 0 else '−'} {abs(a):.{dec}f}"


def _qq(e):
    e = np.sort(np.asarray(e, float))
    n = len(e)
    theo = stats.norm.ppf((np.arange(1, n + 1) - 0.375) / (n + 0.25))
    return theo, e


def _df_band(res):
    return pd.DataFrame(res["band"])


def _df_pts(res):
    return pd.DataFrame(res["points"])


def _df_unk(res):
    return pd.DataFrame(res["unknowns"]) if res["unknowns"] else pd.DataFrame()


def _level_means(pt: pd.DataFrame) -> pd.DataFrame:
    g = pt.groupby("x")["y"]
    return pd.DataFrame({"x": g.mean().index, "y": g.mean().values, "sd": g.std(ddof=1).fillna(0).values,
                         "n": g.size().values})


def _blend(color: str, alpha: float, bg: str = "#ffffff") -> str:
    """Solid colour equivalent to `color` with `alpha` over `bg` (no transparency)."""
    c = np.array(matplotlib.colors.to_rgb(color))
    b = np.array(matplotlib.colors.to_rgb(bg))
    return matplotlib.colors.to_hex(alpha * c + (1 - alpha) * b)


def _rgba(color: str, alpha: float) -> str:
    r, g, b = (int(255 * v) for v in matplotlib.colors.to_rgb(color))
    return f"rgba({r},{g},{b},{alpha})"


def _labels(d: Design, xlab: str, ylab: str | None):
    return (d.xlabel or xlab), (d.ylabel or ylab or t("Absorbance"))


# ------------------------------------------------------ Matplotlib/Seaborn ----
def _first_font(font: str) -> str:
    """First installed family of the list (Arial on Windows, Liberation Sans on Linux…)."""
    installed = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    for name in FONT_FAMILIES["serif" if font == "serif" else "sans"]:
        if name in installed:
            return name
    return "DejaVu Serif" if font == "serif" else "DejaVu Sans"


def publication_rc(font: str = "sans", size: float = 8.0, dark: bool = False) -> dict:
    lw = max(0.5, size / 10)
    rc = {
        "font.family": FONT_FAMILIES["serif" if font == "serif" else "sans"],   # concrete names, first available
        "font.sans-serif": FONT_FAMILIES["sans"], "font.serif": FONT_FAMILIES["serif"],
        # math text (e.g. ×10⁻³ offsets) in the same typeface as the rest of the figure
        "mathtext.fontset": "custom", "mathtext.rm": _first_font(font), "mathtext.sf": _first_font(font),
        "mathtext.it": f"{_first_font(font)}:italic", "mathtext.bf": f"{_first_font(font)}:bold",
        "font.size": size, "axes.labelsize": size, "axes.titlesize": size,
        "xtick.labelsize": size - 1, "ytick.labelsize": size - 1, "legend.fontsize": size - 1,
        "axes.linewidth": lw, "xtick.major.width": lw, "ytick.major.width": lw,
        "xtick.minor.width": lw * 0.7, "ytick.minor.width": lw * 0.7,
        "xtick.major.size": 3.2, "ytick.major.size": 3.2, "xtick.minor.size": 1.8, "ytick.minor.size": 1.8,
        "xtick.direction": "out", "ytick.direction": "out",
        "lines.linewidth": lw * 1.6, "patch.linewidth": lw, "grid.linewidth": lw * 0.6,
        "legend.frameon": False, "legend.handlelength": 1.6, "legend.borderaxespad": 0.3,
        "axes.titleweight": "bold", "axes.labelpad": 3,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    }
    if not dark:
        rc.update({"savefig.facecolor": "white", "figure.facecolor": "white"})
    return rc


def _theme_ctx(d: Design):
    if d.theme.startswith("seaborn_"):
        return sns.axes_style(d.theme.replace("seaborn_", ""))
    if d.theme == "dark":
        return plt.style.context("dark_background")
    return plt.style.context("default")


def _finish_axes(ax, d: Design, dark: bool):
    grid_c = "#444444" if dark else "#d9d9d9"
    ax.grid(False)
    if d.grid in ("y", "both"):
        ax.grid(True, axis="y" if d.grid == "y" else "both", color=grid_c, lw=0.4 * d.line_scale, zorder=0)
        ax.set_axisbelow(True)
    if d.minor_ticks:
        ax.xaxis.set_minor_locator(AutoMinorLocator())
        ax.yaxis.set_minor_locator(AutoMinorLocator())
    if d.theme in ("journal", "seaborn_ticks"):
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)


def mpl_calibration(res, xlab, ylab=None, title=None, design: Design | None = None, dpi: int = 110):
    """Calibration curve built at the final size of `design` (mm) — what you see is what you export."""
    d = design or Design()
    bd, pt, uk = _df_band(res), _df_pts(res), _df_unk(res)
    conf = int(res["conf_level"] * 100)
    c_main, c_unk, c_lod, c_loq = d.colors
    dark = d.theme == "dark"
    bg = "#000000" if dark else "#ffffff"
    k = d.font_size / 8
    lw, ms = d.line_scale * k, d.marker_scale * k
    xl, yl = _labels(d, xlab, ylab)
    with _theme_ctx(d), plt.rc_context(publication_rc(d.font, d.font_size, dark)):
        fig, ax = plt.subplots(figsize=(d.width_mm / 25.4, d.height_mm / 25.4), layout="constrained", dpi=dpi)
        fig._calibrauv_rc = publication_rc(d.font, d.font_size, dark)
        if d.show_bands:
            ax.fill_between(bd.x, bd.pred_low, bd.pred_high, color=_blend(c_main, 0.12, bg), lw=0, zorder=1,
                            label=t("{c}% prediction", c=conf))
            ax.fill_between(bd.x, bd.conf_low, bd.conf_high, color=_blend(c_main, 0.30, bg), lw=0, zorder=1,
                            label=t("{c}% confidence", c=conf))
        ax.plot(bd.x, bd.fit, color=c_main, lw=1.1 * lw, zorder=2, solid_capstyle="round",
                label=t("Linear fit") if d.show_equation else equation(res))
        if d.residual_lines:
            ax.vlines(pt.x, pt.fitted, pt.y, color=_blend(c_main, 0.6, bg), lw=0.6 * lw, zorder=2)
        face = bg if d.gray else c_main
        edge = c_main if d.gray else bg
        if d.replicate_means:
            lm = _level_means(pt)
            ax.errorbar(lm.x, lm.y, yerr=lm.sd, fmt=d.marker, ms=4.2 * ms, mfc=face, mec=edge if not d.gray else c_main,
                        mew=0.6 * lw, ecolor=c_main, elinewidth=0.8 * lw, capsize=2.2 * k, zorder=3,
                        label=t("Standards (mean ± SD)"))
        else:
            ax.scatter(pt.x, pt.y, s=16 * ms ** 2, marker=d.marker, facecolor=face, edgecolor=edge,
                       linewidth=0.6 * lw, zorder=3, label=t("Standards"))
        if d.show_samples and not uk.empty:
            ax.errorbar(uk.x0, uk.y_mean, xerr=[uk.x0 - uk.ci_low, uk.ci_high - uk.x0], fmt="D",
                        color=c_unk, mec=edge, mew=0.5 * lw, ms=4 * ms, capsize=2 * k, elinewidth=0.8 * lw,
                        label=t("Samples"), zorder=4)
            if d.show_labels:
                for _, r in uk.iterrows():
                    ax.annotate(r["sample"], (r.x0, r.y_mean), textcoords="offset points", xytext=(4, -9),
                                fontsize=d.font_size - 1.5, color=c_unk)
        if d.show_lod:
            ax.axvline(res["lod"], color=c_lod, ls=":", lw=0.8 * lw, zorder=1, label=f"LOD = {res['lod']:.3g}")
            ax.axvline(res["loq"], color=c_loq, ls="--", lw=0.8 * lw, zorder=1, label=f"LOQ = {res['loq']:.3g}")
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        if d.x_from_zero:
            ax.set_xlim(left=min(0, float(np.min(pt.x))))
            ax.set_ylim(bottom=min(0, float(np.min(bd.pred_low))))
        ax.margins(x=0.02)
        if d.show_title:
            ax.set_title(title or t("Calibration curve (R² = {r})", r=f"{res['r_squared']:.5f}"))
        if d.show_equation:
            ax.text(0.97, 0.04, f"{equation(res)}\nR² = {res['r_squared']:.4f}", transform=ax.transAxes,
                    ha="right", va="bottom", fontsize=d.font_size - 0.5,
                    bbox=dict(boxstyle="round,pad=0.3", fc=bg, ec="#bbbbbb" if not dark else "#666666",
                              lw=0.5 * lw))
        leg = dict(handlelength=1.4, handletextpad=0.5, labelspacing=0.3, borderaxespad=0.4)
        if d.legend == "outside":
            ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), **{**leg, "borderaxespad": 0})
        elif d.legend != "none":
            ax.legend(loc=d.legend, **leg)
        _finish_axes(ax, d, dark)
    return fig


def mpl_diagnostics(res, xlab, design: Design | None = None, dpi: int = 110):
    """2×2 residual diagnostics, panel letters (a)–(d), at the final size of `design`."""
    d = design or Design()
    pt = _df_pts(res)
    theo, emp = _qq(pt.residuals)
    c_main, _, c_ref, _ = d.colors
    dark = d.theme == "dark"
    bg = "#000000" if dark else "#ffffff"
    k = d.font_size / 8
    lw, s_pt = d.line_scale * k, 12 * (d.marker_scale * k) ** 2
    ref = dict(color=c_ref, ls=":", lw=0.8 * lw)
    zero = dict(color=GREY, lw=0.6 * lw)
    face, edge = (bg, c_main) if d.gray else (c_main, bg)
    with _theme_ctx(d), plt.rc_context(publication_rc(d.font, d.font_size, dark)):
        fig, axs = plt.subplots(2, 2, figsize=(d.width_mm / 25.4, d.height_mm / 25.4), layout="constrained",
                                dpi=dpi)
        fig._calibrauv_rc = publication_rc(d.font, d.font_size, dark)
        pts = dict(s=s_pt, marker=d.marker, facecolor=face, edgecolor=edge, linewidth=0.5 * lw, zorder=3)
        a = axs[0, 0]
        a.scatter(pt.x, pt.residuals, **pts)
        a.axhline(0, **zero)
        a.set(xlabel=xlab, ylabel=t("Residual"))
        a = axs[0, 1]
        a.scatter(pt.fitted, pt.std_residuals, **pts)
        for v in (-2, 2):
            a.axhline(v, **ref)
        a.axhline(0, **zero)
        a.set(xlabel=t("Fitted absorbance"), ylabel=t("Standardized r"))
        a = axs[1, 0]
        a.scatter(theo, emp, **pts)
        sl, ic = np.polyfit(theo, emp, 1)
        a.plot(theo, ic + sl * theo, color=c_ref, lw=0.9 * lw)
        a.set(xlabel=t("Theoretical quantiles"), ylabel=t("Ordered residuals"))
        a = axs[1, 1]
        sns.histplot(pt.residuals, kde=len(pt) > 3, ax=a, color=_blend(c_main, 0.55, bg), edgecolor=bg,
                     alpha=1.0, linewidth=0.5 * lw, line_kws={"lw": 1.1 * lw})
        for ln in a.lines:
            ln.set_color(c_main)
        a.set(xlabel=t("Residual"), ylabel=t("Count"))
        titles = [t("Residuals vs concentration"), t("Standardized residuals"), t("Normal Q-Q plot"),
                  t("Residual distribution")]
        for i, ax in enumerate(axs.flat):
            if d.show_title:
                ax.set_title(titles[i])
            if d.panel_letters:
                ax.text(-0.02, 1.03, f"({'abcd'[i]})", transform=ax.transAxes, ha="right", va="bottom",
                        fontweight="bold")
            _finish_axes(ax, replace(d, minor_ticks=d.minor_ticks and i != 3), dark)
        # small residuals: scientific notation (×10⁻ⁿ) instead of long decimals
        for ax in (axs[0, 0], axs[1, 0]):
            ax.ticklabel_format(axis="y", style="sci", scilimits=(-2, 3), useMathText=True)
        axs[1, 1].ticklabel_format(axis="x", style="sci", scilimits=(-2, 3), useMathText=True)
    return fig


def export_figure(fig, fmt: str = "pdf", dpi: int = 600, close: bool = True, color_mode: str = "RGB") -> bytes:
    """Save a figure for publication, keeping its exact size (no cropping).

    Vector formats (PDF, SVG, EPS) are resolution-independent; dpi matters for TIFF/PNG.
    Raster images are flattened on white (no alpha channel, which many journals reject):
    RGB by default, or CMYK for TIFF (simple conversion, without an ICC profile).
    TIFF uses lossless LZW compression.
    """
    buf = io.BytesIO()
    # The figure's own style is re-applied at save time (tick labels are drawn now) and the
    # font embedding is decided here: TrueType (Type 42) in PDF/EPS, real text in SVG.
    rc = dict(getattr(fig, "_calibrauv_rc", {}))
    rc.update({"pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none"})
    with plt.rc_context(rc):
        if fmt in ("tiff", "png"):
            raw = io.BytesIO()
            fig.savefig(raw, format="png", dpi=dpi)
            from PIL import Image
            im = Image.open(raw)
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.getchannel("A") if im.mode == "RGBA" else None)
            out = bg.convert("CMYK") if (fmt == "tiff" and color_mode == "CMYK") else bg
            if fmt == "tiff":
                out.save(buf, format="TIFF", compression="tiff_lzw", dpi=(dpi, dpi))
            else:
                out.save(buf, format="PNG", dpi=(dpi, dpi), optimize=True)
        else:
            fig.savefig(buf, format=fmt, dpi=dpi, metadata={"Creator": "CalibraUV"})
    if close:
        plt.close(fig)
    return buf.getvalue()


def fig_to_png(fig, dpi=300) -> bytes:
    return export_figure(fig, "png", dpi)


# ------------------------------------------------------------------ Plotly ----
def plotly_config(d: Design | None = None, filename: str = "calibrauv_figure") -> dict:
    """Modebar camera button downloads a vector SVG at the design size."""
    d = d or Design()
    return {"displaylogo": False,
            "toImageButtonOptions": {"format": "svg", "filename": filename,
                                     "width": round(d.width_mm / 25.4 * 96 * 2),
                                     "height": round(d.height_mm / 25.4 * 96 * 2)}}


def _plotly_layout(fig, d: Design, xl, yl, title, height):
    dark = d.theme == "dark"
    template = "plotly_dark" if dark else ("simple_white" if d.theme in ("journal", "seaborn_ticks", "classic")
                                           else "plotly_white")
    font = "Arial, Helvetica, sans-serif" if d.font == "sans" else "Times New Roman, Times, serif"
    legend = {"upper left": dict(x=0.02, y=0.93, xanchor="left", yanchor="top"),
              "lower right": dict(x=0.99, y=0.01, xanchor="right", yanchor="bottom"),
              "outside": dict(x=1.02, y=1, xanchor="left", yanchor="top")}.get(d.legend, {})
    fig.update_layout(template=template, title=title if d.show_title else None, height=height,
                      font=dict(family=font, size=13), hovermode="closest", showlegend=d.legend != "none",
                      legend=dict(bgcolor="rgba(0,0,0,0)", **legend), margin=dict(l=60, r=20, t=50 if d.show_title else 20, b=55))
    grid_c = "#3a3a3a" if dark else "#e5e5e5"
    axis = dict(showline=True, mirror=d.theme == "classic", ticks="outside", zeroline=False)
    if d.minor_ticks:
        axis["minor"] = dict(ticks="outside", showgrid=False)
    fig.update_xaxes(title_text=xl, showgrid=d.grid == "both", gridcolor=grid_c, **axis)
    fig.update_yaxes(title_text=yl, showgrid=d.grid in ("y", "both"), gridcolor=grid_c, **axis)
    if d.x_from_zero:
        fig.update_xaxes(rangemode="tozero")
        fig.update_yaxes(rangemode="tozero")


def plotly_calibration(res, xlab, ylab=None, title=None, design: Design | None = None):
    d = design or Design()
    bd, pt, uk = _df_band(res), _df_pts(res), _df_unk(res)
    conf = int(res["conf_level"] * 100)
    c_main, c_unk, c_lod, c_loq = d.colors
    xl, yl = _labels(d, xlab, ylab)
    sym = MARKERS.get(d.marker, "circle")
    fig = go.Figure()
    if d.show_bands:
        fig.add_trace(go.Scatter(x=np.r_[bd.x, bd.x[::-1]], y=np.r_[bd.pred_high, bd.pred_low[::-1]],
                                 fill="toself", fillcolor=_rgba(c_main, 0.12), line=dict(width=0),
                                 name=t("{c}% prediction band", c=conf), hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=np.r_[bd.x, bd.x[::-1]], y=np.r_[bd.conf_high, bd.conf_low[::-1]],
                                 fill="toself", fillcolor=_rgba(c_main, 0.30), line=dict(width=0),
                                 name=t("{c}% confidence band", c=conf), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=bd.x, y=bd.fit, mode="lines", line=dict(color=c_main, width=2.2 * d.line_scale),
                             name=t("Linear fit") if d.show_equation else equation(res)))
    if d.residual_lines:
        xs, ys = [], []
        for x, y0, y1 in zip(pt.x, pt.fitted, pt.y):
            xs += [x, x, None]
            ys += [y0, y1, None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=_rgba(c_main, 0.5), width=1),
                                 name=t("Residual"), hoverinfo="skip", showlegend=False))
    mk = dict(color="white" if d.gray else c_main, size=9 * d.marker_scale, symbol=sym,
              line=dict(color=c_main if d.gray else "white", width=1))
    if d.replicate_means:
        lm = _level_means(pt)
        fig.add_trace(go.Scatter(x=lm.x, y=lm.y, mode="markers", name=t("Standards (mean ± SD)"), marker=mk,
                                 error_y=dict(type="data", array=lm.sd, color=c_main, thickness=1.2),
                                 hovertemplate="C = %{x}<br>A = %{y:.4f}<extra></extra>"))
    else:
        fig.add_trace(go.Scatter(x=pt.x, y=pt.y, mode="markers", name=t("Standards"), marker=mk,
                                 hovertemplate="C = %{x}<br>A = %{y:.4f}<extra></extra>"))
    if d.show_samples and not uk.empty:
        fig.add_trace(go.Scatter(
            x=uk.x0, y=uk.y_mean, mode="markers+text" if d.show_labels else "markers", name=t("Samples"),
            marker=dict(color=c_unk, size=11 * d.marker_scale, symbol="diamond", line=dict(color="white", width=1)),
            text=uk["sample"], textposition="bottom right", textfont=dict(color=c_unk, size=11),
            error_x=dict(type="data", symmetric=False, array=uk.ci_high - uk.x0,
                         arrayminus=uk.x0 - uk.ci_low, color=c_unk),
            hovertemplate="%{text}<br>C = %{x:.4f}<br>A = %{y:.4f}<extra></extra>"))
    if d.show_lod:
        fig.add_vline(x=res["lod"], line=dict(color=c_lod, dash="dot", width=1.2), annotation_text="LOD",
                      annotation_position="top left")
        fig.add_vline(x=res["loq"], line=dict(color=c_loq, dash="dash", width=1.2), annotation_text="LOQ",
                      annotation_position="top right")
    if d.show_equation:
        fig.add_annotation(x=0.98, y=0.03, xref="paper", yref="paper", xanchor="right", yanchor="bottom",
                           text=f"{equation(res)}<br>R² = {res['r_squared']:.4f}", showarrow=False, align="right",
                           bordercolor="#bbbbbb", borderwidth=1, borderpad=4,
                           bgcolor="rgba(255,255,255,0.85)" if d.theme != "dark" else "rgba(0,0,0,0.6)")
    _plotly_layout(fig, d, xl, yl, title or t("Calibration curve (R² = {r})", r=f"{res['r_squared']:.5f}"), 540)
    return fig


def plotly_diagnostics(res, xlab, design: Design | None = None):
    d = design or Design()
    pt = _df_pts(res)
    theo, emp = _qq(pt.residuals)
    c_main, _, c_ref, _ = d.colors
    letters = [f"({c}) " if d.panel_letters else "" for c in "abcd"]
    fig = make_subplots(rows=2, cols=2, horizontal_spacing=0.1, vertical_spacing=0.16, subplot_titles=[
        letters[0] + t("Residuals vs concentration"), letters[1] + t("Standardized residuals vs fitted"),
        letters[2] + t("Normal Q-Q plot"), letters[3] + t("Cook's distance")])
    mk = dict(color="white" if d.gray else c_main, size=8 * d.marker_scale, symbol=MARKERS.get(d.marker, "circle"),
              line=dict(color=c_main if d.gray else "white", width=1))
    fig.add_trace(go.Scatter(x=pt.x, y=pt.residuals, mode="markers", marker=mk), 1, 1)
    fig.add_hline(y=0, line_color=GREY, row=1, col=1)
    fig.add_trace(go.Scatter(x=pt.fitted, y=pt.std_residuals, mode="markers", marker=mk), 1, 2)
    for v in (-2, 0, 2):
        fig.add_hline(y=v, line_color=c_ref if v else GREY, line_dash="dot" if v else "solid", row=1, col=2)
    fig.add_trace(go.Scatter(x=theo, y=emp, mode="markers", marker=mk), 2, 1)
    sl, ic = np.polyfit(theo, emp, 1)
    fig.add_trace(go.Scatter(x=theo, y=ic + sl * theo, mode="lines", line=dict(color=c_ref, width=1.5)), 2, 1)
    fig.add_trace(go.Bar(x=np.arange(1, len(pt) + 1), y=pt.cooks, marker_color=_rgba(c_main, 0.8)), 2, 2)
    fig.add_hline(y=4 / res["n"], line_color=c_ref, line_dash="dot", row=2, col=2)
    _plotly_layout(fig, replace(d, show_title=False, x_from_zero=False, legend="none"), None, None, None, 680)
    fig.update_xaxes(title_text=xlab, row=1, col=1)
    fig.update_xaxes(title_text=t("Fitted absorbance"), row=1, col=2)
    fig.update_xaxes(title_text=t("Theoretical quantiles"), row=2, col=1)
    fig.update_xaxes(title_text=t("Observation"), row=2, col=2)
    fig.update_layout(showlegend=False, margin=dict(t=40))
    return fig


def plotly_standard_addition(res_add, sa, xlab, design: Design | None = None):
    """Standard addition line extrapolated to the x-intercept (−C_sample)."""
    d = design or Design()
    c_main, c_unk, _, _ = d.colors
    pt = _df_pts(res_add)
    a, b = sa["intercept"], sa["slope"]
    x0 = -sa["C"]
    gx = np.linspace(min(x0, 0) * 1.1, max(pt.x) * 1.05, 50)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=gx, y=a + b * gx, mode="lines", line=dict(color=c_main, dash="dash"),
                             name=f"A = {b:.5f}·C_added + {a:.5f}"))
    fig.add_trace(go.Scatter(x=pt.x, y=pt.y, mode="markers", name=t("Spiked aliquots"),
                             marker=dict(color=c_main, size=9 * d.marker_scale, symbol=MARKERS.get(d.marker, "circle"),
                                         line=dict(color="white", width=1))))
    fig.add_trace(go.Scatter(x=[x0], y=[0], mode="markers", marker=dict(color=c_unk, size=13, symbol="diamond"),
                             error_x=dict(type="data", array=[sa["ci_high"] - sa["C"]], color=c_unk),
                             name=t("x-intercept → C = {c}", c=f"{sa['C']:.4g}")))
    fig.add_hline(y=0, line_color=GREY)
    fig.add_vline(x=0, line_color=GREY)
    _plotly_layout(fig, replace(d, x_from_zero=False), xlab, t("Absorbance"), t("Standard addition"), 480)
    return fig


# ------------------------------------------------------------------ Altair ----
def _alt_config(chart, d: Design):
    font = "Arial" if d.font == "sans" else "Times New Roman"
    dark = d.theme == "dark"
    fg = "#dddddd" if dark else "#222222"
    return (chart.configure(font=font, background="#0e1117" if dark else "white")
            .configure_axis(grid=d.grid != "none", gridColor="#333333" if dark else "#e5e5e5", labelColor=fg,
                            titleColor=fg, domainColor=fg, tickColor=fg, labelFontSize=12, titleFontSize=13)
            .configure_legend(labelColor=fg, titleColor=fg)
            .configure_title(color=fg, fontSize=14)
            .configure_view(stroke=None if d.theme in ("journal", "seaborn_ticks") else "#888888"))


def altair_calibration(res, xlab, ylab=None, design: Design | None = None):
    d = design or Design()
    bd, pt, uk = _df_band(res), _df_pts(res), _df_unk(res)
    c_main, c_unk, c_lod, c_loq = d.colors
    xl, yl = _labels(d, xlab, ylab)
    shape = {"o": "circle", "s": "square", "^": "triangle-up", "D": "diamond", "v": "triangle-down"}[d.marker]
    X = alt.X("x:Q", title=xl, scale=alt.Scale(zero=d.x_from_zero))
    layers = []
    if d.show_bands:
        layers.append(alt.Chart(bd).mark_area(opacity=0.12, color=c_main).encode(
            X, alt.Y("pred_low:Q", title=yl, scale=alt.Scale(zero=d.x_from_zero)), alt.Y2("pred_high:Q")))
        layers.append(alt.Chart(bd).mark_area(opacity=0.30, color=c_main).encode(
            X, alt.Y("conf_low:Q", title=yl), alt.Y2("conf_high:Q")))
    layers.append(alt.Chart(bd).mark_line(color=c_main, strokeWidth=2 * d.line_scale).encode(X, alt.Y("fit:Q", title=yl)))
    if d.replicate_means:
        lm = _level_means(pt).assign(lo=lambda v: v.y - v.sd, hi=lambda v: v.y + v.sd)
        layers.append(alt.Chart(lm).mark_rule(color=c_main).encode(X, alt.Y("lo:Q"), alt.Y2("hi:Q")))
        src = lm
    else:
        src = pt
    layers.append(alt.Chart(src).mark_point(shape=shape, size=70 * d.marker_scale ** 2, filled=not d.gray,
                                            color=c_main, opacity=1, stroke="white" if not d.gray else c_main,
                                            strokeWidth=0.8).encode(
        X, alt.Y("y:Q", title=yl),
        tooltip=[alt.Tooltip("x:Q", title="C"), alt.Tooltip("y:Q", title="A", format=".4f")]))
    if d.show_samples and not uk.empty:
        uk2 = uk.rename(columns={"x0": "x"})
        layers.append(alt.Chart(uk2).mark_rule(color=c_unk).encode(alt.X("ci_low:Q"), alt.X2("ci_high:Q"), alt.Y("y_mean:Q")))
        layers.append(alt.Chart(uk2).mark_point(shape="diamond", size=120 * d.marker_scale ** 2, color=c_unk,
                                                filled=True, opacity=1).encode(
            alt.X("x:Q"), alt.Y("y_mean:Q"),
            tooltip=["sample", alt.Tooltip("x:Q", format=".4f"), alt.Tooltip("y_mean:Q", format=".4f")]))
        if d.show_labels:
            layers.append(alt.Chart(uk2).mark_text(align="left", dx=7, dy=10, color=c_unk).encode(
                alt.X("x:Q"), alt.Y("y_mean:Q"), text="sample"))
    if d.show_lod:
        lines = pd.DataFrame({"x": [res["lod"], res["loq"]], "lab": ["LOD", "LOQ"]})
        layers.append(alt.Chart(lines).mark_rule(strokeDash=[3, 3]).encode(
            alt.X("x:Q"), color=alt.Color("lab:N", scale=alt.Scale(domain=["LOD", "LOQ"], range=[c_lod, c_loq]),
                                          legend=alt.Legend(title=None))))
    title = f"{equation(res)}   R² = {res['r_squared']:.5f}" if (d.show_title or d.show_equation) else ""
    return _alt_config(alt.layer(*layers).properties(title=title, height=420).interactive(), d)


def altair_residuals(res, xlab, design: Design | None = None):
    d = design or Design()
    c_main, _, c_ref, _ = d.colors
    pt = _df_pts(res).assign(obs=lambda v: np.arange(1, len(v) + 1))
    base = alt.Chart(pt).mark_point(size=60 * d.marker_scale ** 2, filled=True, color=c_main, opacity=1).encode(
        alt.X("x:Q", title=xlab), alt.Y("std_residuals:Q", title=t("Standardized residual")),
        tooltip=["obs", "x", alt.Tooltip("std_residuals:Q", format=".3f")])
    rules = alt.Chart(pd.DataFrame({"y": [-2, 0, 2]})).mark_rule(strokeDash=[4, 4], color=c_ref).encode(
        y=alt.Y("y:Q"))
    return _alt_config((base + rules).properties(title=t("Standardized residuals"), height=300), d)
