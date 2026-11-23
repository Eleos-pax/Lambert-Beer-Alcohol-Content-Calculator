"""Plots with four libraries: Matplotlib, Seaborn, Plotly and Altair.

Palette: Okabe-Ito (colour-blind safe).
"""

from __future__ import annotations

import io

import altair as alt
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import seaborn as sns  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402
from scipy import stats  # noqa: E402

BLUE, ORANGE, GREEN, RED, GREY = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#7f7f7f"


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


# ------------------------------------------------------------------ Plotly ----
def plotly_calibration(res, xlab, ylab="Absorbance", title=None, template="plotly_white"):
    bd, pt, uk = _df_band(res), _df_pts(res), _df_unk(res)
    conf = int(res["conf_level"] * 100)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=np.r_[bd.x, bd.x[::-1]], y=np.r_[bd.pred_high, bd.pred_low[::-1]],
                             fill="toself", fillcolor="rgba(0,114,178,0.10)", line=dict(width=0),
                             name=f"{conf}% prediction band", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=np.r_[bd.x, bd.x[::-1]], y=np.r_[bd.conf_high, bd.conf_low[::-1]],
                             fill="toself", fillcolor="rgba(0,114,178,0.25)", line=dict(width=0),
                             name=f"{conf}% confidence band", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=bd.x, y=bd.fit, mode="lines", line=dict(color=BLUE, width=2),
                             name=equation(res)))
    fig.add_trace(go.Scatter(x=pt.x, y=pt.y, mode="markers", name="Standards",
                             marker=dict(color=BLUE, size=9, line=dict(color="white", width=1)),
                             hovertemplate="C = %{x}<br>A = %{y:.4f}<extra></extra>"))
    if not uk.empty:
        fig.add_trace(go.Scatter(
            x=uk.x0, y=uk.y_mean, mode="markers", name="Samples",
            marker=dict(color=ORANGE, size=11, symbol="diamond"),
            error_x=dict(type="data", symmetric=False, array=uk.ci_high - uk.x0,
                         arrayminus=uk.x0 - uk.ci_low, color=ORANGE),
            text=uk["sample"], hovertemplate="%{text}<br>C = %{x:.4f}<br>A = %{y:.4f}<extra></extra>"))
    fig.add_vline(x=res["lod"], line=dict(color=RED, dash="dot"), annotation_text="LOD",
                  annotation_position="top left")
    fig.add_vline(x=res["loq"], line=dict(color=GREEN, dash="dot"), annotation_text="LOQ",
                  annotation_position="top right")
    fig.update_layout(template=template, title=title or f"Calibration curve (R² = {res['r_squared']:.5f})",
                      xaxis_title=xlab, yaxis_title=ylab, hovermode="closest",
                      legend=dict(orientation="h", y=-0.2), height=520)
    return fig


def plotly_diagnostics(res, xlab, template="plotly_white"):
    pt = _df_pts(res)
    theo, emp = _qq(pt.residuals)
    fig = make_subplots(rows=2, cols=2, subplot_titles=(
        "Residuals vs concentration", "Standardized residuals vs fitted",
        "Normal Q-Q plot", "Cook's distance"))
    fig.add_trace(go.Scatter(x=pt.x, y=pt.residuals, mode="markers", marker_color=BLUE), 1, 1)
    fig.add_hline(y=0, line_color=GREY, row=1, col=1)
    fig.add_trace(go.Scatter(x=pt.fitted, y=pt.std_residuals, mode="markers", marker_color=BLUE), 1, 2)
    for v in (-2, 0, 2):
        fig.add_hline(y=v, line_color=RED if v else GREY, line_dash="dot" if v else "solid", row=1, col=2)
    fig.add_trace(go.Scatter(x=theo, y=emp, mode="markers", marker_color=BLUE), 2, 1)
    sl, ic = np.polyfit(theo, emp, 1)
    fig.add_trace(go.Scatter(x=theo, y=ic + sl * theo, mode="lines", line_color=RED), 2, 1)
    fig.add_trace(go.Bar(x=np.arange(1, len(pt) + 1), y=pt.cooks, marker_color=BLUE), 2, 2)
    fig.add_hline(y=4 / res["n"], line_color=RED, line_dash="dot", row=2, col=2)
    fig.update_xaxes(title_text=xlab, row=1, col=1)
    fig.update_xaxes(title_text="Fitted absorbance", row=1, col=2)
    fig.update_xaxes(title_text="Theoretical quantiles", row=2, col=1)
    fig.update_xaxes(title_text="Observation", row=2, col=2)
    fig.update_layout(template=template, showlegend=False, height=650)
    return fig


# ------------------------------------------------------ Matplotlib/Seaborn ----
def mpl_calibration(res, xlab, ylab="Absorbance", title=None, seaborn_style="whitegrid",
                    use_seaborn=True):
    bd, pt, uk = _df_band(res), _df_pts(res), _df_unk(res)
    conf = int(res["conf_level"] * 100)
    ctx = sns.axes_style(seaborn_style) if use_seaborn else plt.style.context("default")
    with ctx:
        fig, ax = plt.subplots(figsize=(8, 5.5), dpi=110)
        ax.fill_between(bd.x, bd.pred_low, bd.pred_high, color=BLUE, alpha=0.10,
                        label=f"{conf}% prediction")
        ax.fill_between(bd.x, bd.conf_low, bd.conf_high, color=BLUE, alpha=0.25,
                        label=f"{conf}% confidence")
        ax.plot(bd.x, bd.fit, color=BLUE, lw=2, label=equation(res))
        if use_seaborn:
            sns.scatterplot(x=pt.x, y=pt.y, ax=ax, color=BLUE, s=60, edgecolor="white",
                            label="Standards", zorder=3)
        else:
            ax.scatter(pt.x, pt.y, color=BLUE, s=50, edgecolor="white", label="Standards", zorder=3)
        if not uk.empty:
            ax.errorbar(uk.x0, uk.y_mean, xerr=[uk.x0 - uk.ci_low, uk.ci_high - uk.x0],
                        fmt="D", color=ORANGE, ms=8, capsize=4, label="Samples", zorder=4)
            for _, r in uk.iterrows():
                ax.annotate(r["sample"], (r.x0, r.y_mean), textcoords="offset points",
                            xytext=(6, -12), fontsize=8, color=ORANGE)
        ax.axvline(res["lod"], color=RED, ls=":", lw=1.2, label=f"LOD = {res['lod']:.3g}")
        ax.axvline(res["loq"], color=GREEN, ls=":", lw=1.2, label=f"LOQ = {res['loq']:.3g}")
        ax.set_xlabel(xlab)
        ax.set_ylabel(ylab)
        ax.set_title(title or f"Calibration curve  (R² = {res['r_squared']:.5f})")
        ax.legend(fontsize=8, loc="upper left", frameon=True)
        fig.tight_layout()
    return fig


def mpl_diagnostics(res, xlab, seaborn_style="whitegrid", use_seaborn=True):
    pt = _df_pts(res)
    theo, emp = _qq(pt.residuals)
    ctx = sns.axes_style(seaborn_style) if use_seaborn else plt.style.context("default")
    with ctx:
        fig, axs = plt.subplots(2, 2, figsize=(10, 7.5), dpi=110)
        a = axs[0, 0]
        a.scatter(pt.x, pt.residuals, color=BLUE)
        a.axhline(0, color=GREY)
        a.set(title="Residuals vs concentration", xlabel=xlab, ylabel="Residual")
        a = axs[0, 1]
        a.scatter(pt.fitted, pt.std_residuals, color=BLUE)
        for v in (-2, 2):
            a.axhline(v, color=RED, ls=":")
        a.axhline(0, color=GREY)
        a.set(title="Standardized residuals", xlabel="Fitted absorbance", ylabel="Standardized r")
        a = axs[1, 0]
        a.scatter(theo, emp, color=BLUE)
        sl, ic = np.polyfit(theo, emp, 1)
        a.plot(theo, ic + sl * theo, color=RED)
        a.set(title="Normal Q-Q", xlabel="Theoretical quantiles", ylabel="Ordered residuals")
        a = axs[1, 1]
        if use_seaborn:
            sns.histplot(pt.residuals, kde=True, ax=a, color=BLUE)
        else:
            a.hist(pt.residuals, color=BLUE, alpha=0.8)
        a.set(title="Residual distribution", xlabel="Residual")
        fig.tight_layout()
    return fig


def fig_to_png(fig, dpi=300) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


# ------------------------------------------------------------------ Altair ----
def altair_calibration(res, xlab, ylab="Absorbance"):
    bd, pt, uk = _df_band(res), _df_pts(res), _df_unk(res)
    X = alt.X("x:Q", title=xlab)
    pred = alt.Chart(bd).mark_area(opacity=0.12, color=BLUE).encode(
        X, alt.Y("pred_low:Q", title=ylab), alt.Y2("pred_high:Q"))
    conf = alt.Chart(bd).mark_area(opacity=0.28, color=BLUE).encode(
        X, alt.Y("conf_low:Q"), alt.Y2("conf_high:Q"))
    line = alt.Chart(bd).mark_line(color=BLUE, strokeWidth=2).encode(X, alt.Y("fit:Q"))
    points = alt.Chart(pt).mark_circle(size=80, color=BLUE, opacity=1).encode(
        X, alt.Y("y:Q"), tooltip=[alt.Tooltip("x:Q", title="C"), alt.Tooltip("y:Q", title="A", format=".4f")])
    layers = [pred, conf, line, points]
    if not uk.empty:
        uk2 = uk.rename(columns={"x0": "x"})
        layers.append(alt.Chart(uk2).mark_rule(color=ORANGE).encode(
            alt.X("ci_low:Q"), alt.X2("ci_high:Q"), alt.Y("y_mean:Q")))
        layers.append(alt.Chart(uk2).mark_point(shape="diamond", size=120, color=ORANGE, filled=True).encode(
            alt.X("x:Q"), alt.Y("y_mean:Q"),
            tooltip=["sample", alt.Tooltip("x:Q", format=".4f"), alt.Tooltip("y_mean:Q", format=".4f")]))
    return alt.layer(*layers).properties(
        title=f"{equation(res)}   R² = {res['r_squared']:.5f}", height=420).interactive()


def altair_residuals(res, xlab):
    pt = _df_pts(res).assign(obs=lambda d: np.arange(1, len(d) + 1))
    base = alt.Chart(pt).mark_circle(size=70, color=BLUE).encode(
        alt.X("x:Q", title=xlab), alt.Y("std_residuals:Q", title="Standardized residual"),
        tooltip=["obs", "x", alt.Tooltip("std_residuals:Q", format=".3f")])
    rules = alt.Chart(pd.DataFrame({"y": [-2, 0, 2]})).mark_rule(strokeDash=[4, 4], color=RED).encode(
        y=alt.Y("y:Q"))
    return (base + rules).properties(title="Standardized residuals", height=300)
