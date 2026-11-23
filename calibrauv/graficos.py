"""Gráficos con cuatro bibliotecas: Matplotlib, Seaborn, Plotly y Altair.

Paleta: Okabe-Ito (apta para daltonismo).
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

AZUL, NARANJA, VERDE, ROJO, GRIS = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#7f7f7f"


def ecuacion(res: dict, dec: int = 5) -> str:
    b = res["coefficients"]["slope"]["estimate"]
    inter = res["coefficients"]["intercept"]
    if inter is None:
        return f"A = {b:.{dec}f}·C"
    a = inter["estimate"]
    return f"A = {b:.{dec}f}·C {'+' if a >= 0 else '−'} {abs(a):.{dec}f}"


def _qq(e):
    e = np.sort(np.asarray(e, float))
    n = len(e)
    teo = stats.norm.ppf((np.arange(1, n + 1) - 0.375) / (n + 0.25))
    return teo, e


def _df_band(res):
    return pd.DataFrame(res["band"])


def _df_pts(res):
    return pd.DataFrame(res["points"])


def _df_unk(res):
    return pd.DataFrame(res["unknowns"]) if res["unknowns"] else pd.DataFrame()


# ------------------------------------------------------------------ Plotly ----
def plotly_calibracion(res, xlab, ylab="Absorbancia", titulo=None, tema="plotly_white"):
    bd, pt, uk = _df_band(res), _df_pts(res), _df_unk(res)
    conf = int(res["conf_level"] * 100)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=np.r_[bd.x, bd.x[::-1]], y=np.r_[bd.pred_high, bd.pred_low[::-1]],
                             fill="toself", fillcolor="rgba(0,114,178,0.10)", line=dict(width=0),
                             name=f"Banda de predicción {conf}%", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=np.r_[bd.x, bd.x[::-1]], y=np.r_[bd.conf_high, bd.conf_low[::-1]],
                             fill="toself", fillcolor="rgba(0,114,178,0.25)", line=dict(width=0),
                             name=f"Banda de confianza {conf}%", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=bd.x, y=bd.fit, mode="lines", line=dict(color=AZUL, width=2),
                             name=ecuacion(res)))
    fig.add_trace(go.Scatter(x=pt.x, y=pt.y, mode="markers", name="Estándares",
                             marker=dict(color=AZUL, size=9, line=dict(color="white", width=1)),
                             hovertemplate="C = %{x}<br>A = %{y:.4f}<extra></extra>"))
    if not uk.empty:
        fig.add_trace(go.Scatter(
            x=uk.x0, y=uk.y_mean, mode="markers", name="Muestras",
            marker=dict(color=NARANJA, size=11, symbol="diamond"),
            error_x=dict(type="data", symmetric=False, array=uk.ci_high - uk.x0,
                         arrayminus=uk.x0 - uk.ci_low, color=NARANJA),
            text=uk["sample"], hovertemplate="%{text}<br>C = %{x:.4f}<br>A = %{y:.4f}<extra></extra>"))
    fig.add_vline(x=res["lod"], line=dict(color=ROJO, dash="dot"), annotation_text="LOD", annotation_position="top left")
    fig.add_vline(x=res["loq"], line=dict(color=VERDE, dash="dot"), annotation_text="LOQ", annotation_position="top right")
    fig.update_layout(template=tema, title=titulo or f"Curva de calibración (R² = {res['r_squared']:.5f})",
                      xaxis_title=xlab, yaxis_title=ylab, hovermode="closest",
                      legend=dict(orientation="h", y=-0.2), height=520)
    return fig


def plotly_diagnostico(res, xlab, tema="plotly_white"):
    pt = _df_pts(res)
    teo, emp = _qq(pt.residuals)
    fig = make_subplots(rows=2, cols=2, subplot_titles=(
        "Residuales vs concentración", "Residuales estandarizados vs ajustados",
        "Gráfico Q-Q normal", "Distancia de Cook"))
    fig.add_trace(go.Scatter(x=pt.x, y=pt.residuals, mode="markers", marker_color=AZUL), 1, 1)
    fig.add_hline(y=0, line_color=GRIS, row=1, col=1)
    fig.add_trace(go.Scatter(x=pt.fitted, y=pt.std_residuals, mode="markers", marker_color=AZUL), 1, 2)
    for v in (-2, 0, 2):
        fig.add_hline(y=v, line_color=ROJO if v else GRIS, line_dash="dot" if v else "solid", row=1, col=2)
    fig.add_trace(go.Scatter(x=teo, y=emp, mode="markers", marker_color=AZUL), 2, 1)
    sl, ic = np.polyfit(teo, emp, 1)
    fig.add_trace(go.Scatter(x=teo, y=ic + sl * teo, mode="lines", line_color=ROJO), 2, 1)
    fig.add_trace(go.Bar(x=np.arange(1, len(pt) + 1), y=pt.cooks, marker_color=AZUL), 2, 2)
    fig.add_hline(y=4 / res["n"], line_color=ROJO, line_dash="dot", row=2, col=2)
    fig.update_xaxes(title_text=xlab, row=1, col=1)
    fig.update_xaxes(title_text="Absorbancia ajustada", row=1, col=2)
    fig.update_xaxes(title_text="Cuantiles teóricos", row=2, col=1)
    fig.update_xaxes(title_text="Observación", row=2, col=2)
    fig.update_layout(template=tema, showlegend=False, height=650)
    return fig


# ------------------------------------------------------ Matplotlib/Seaborn ----
def mpl_calibracion(res, xlab, ylab="Absorbancia", titulo=None, estilo_seaborn="whitegrid",
                    usar_seaborn=True):
    bd, pt, uk = _df_band(res), _df_pts(res), _df_unk(res)
    conf = int(res["conf_level"] * 100)
    ctx = sns.axes_style(estilo_seaborn) if usar_seaborn else plt.style.context("default")
    with ctx:
        fig, ax = plt.subplots(figsize=(8, 5.5), dpi=110)
        ax.fill_between(bd.x, bd.pred_low, bd.pred_high, color=AZUL, alpha=0.10,
                        label=f"Predicción {conf}%")
        ax.fill_between(bd.x, bd.conf_low, bd.conf_high, color=AZUL, alpha=0.25,
                        label=f"Confianza {conf}%")
        ax.plot(bd.x, bd.fit, color=AZUL, lw=2, label=ecuacion(res))
        if usar_seaborn:
            sns.scatterplot(x=pt.x, y=pt.y, ax=ax, color=AZUL, s=60, edgecolor="white",
                            label="Estándares", zorder=3)
        else:
            ax.scatter(pt.x, pt.y, color=AZUL, s=50, edgecolor="white", label="Estándares", zorder=3)
        if not uk.empty:
            ax.errorbar(uk.x0, uk.y_mean, xerr=[uk.x0 - uk.ci_low, uk.ci_high - uk.x0],
                        fmt="D", color=NARANJA, ms=8, capsize=4, label="Muestras", zorder=4)
            for _, r in uk.iterrows():
                ax.annotate(r["sample"], (r.x0, r.y_mean), textcoords="offset points",
                            xytext=(6, -12), fontsize=8, color=NARANJA)
        ax.axvline(res["lod"], color=ROJO, ls=":", lw=1.2, label=f"LOD = {res['lod']:.3g}")
        ax.axvline(res["loq"], color=VERDE, ls=":", lw=1.2, label=f"LOQ = {res['loq']:.3g}")
        ax.set_xlabel(xlab)
        ax.set_ylabel(ylab)
        ax.set_title(titulo or f"Curva de calibración  (R² = {res['r_squared']:.5f})")
        ax.legend(fontsize=8, loc="upper left", frameon=True)
        fig.tight_layout()
    return fig


def mpl_diagnostico(res, xlab, estilo_seaborn="whitegrid", usar_seaborn=True):
    pt = _df_pts(res)
    teo, emp = _qq(pt.residuals)
    ctx = sns.axes_style(estilo_seaborn) if usar_seaborn else plt.style.context("default")
    with ctx:
        fig, axs = plt.subplots(2, 2, figsize=(10, 7.5), dpi=110)
        a = axs[0, 0]
        a.scatter(pt.x, pt.residuals, color=AZUL)
        a.axhline(0, color=GRIS)
        a.set(title="Residuales vs concentración", xlabel=xlab, ylabel="Residual")
        a = axs[0, 1]
        a.scatter(pt.fitted, pt.std_residuals, color=AZUL)
        for v in (-2, 2):
            a.axhline(v, color=ROJO, ls=":")
        a.axhline(0, color=GRIS)
        a.set(title="Residuales estandarizados", xlabel="Absorbancia ajustada", ylabel="r estandarizado")
        a = axs[1, 0]
        a.scatter(teo, emp, color=AZUL)
        sl, ic = np.polyfit(teo, emp, 1)
        a.plot(teo, ic + sl * teo, color=ROJO)
        a.set(title="Q-Q normal", xlabel="Cuantiles teóricos", ylabel="Residuales ordenados")
        a = axs[1, 1]
        if usar_seaborn:
            sns.histplot(pt.residuals, kde=True, ax=a, color=AZUL)
        else:
            a.hist(pt.residuals, color=AZUL, alpha=0.8)
        a.set(title="Distribución de residuales", xlabel="Residual")
        fig.tight_layout()
    return fig


def fig_a_png(fig, dpi=300) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


# ------------------------------------------------------------------ Altair ----
def altair_calibracion(res, xlab, ylab="Absorbancia"):
    bd, pt, uk = _df_band(res), _df_pts(res), _df_unk(res)
    X = alt.X("x:Q", title=xlab)
    pred = alt.Chart(bd).mark_area(opacity=0.12, color=AZUL).encode(X, alt.Y("pred_low:Q", title=ylab),
                                                                    alt.Y2("pred_high:Q"))
    conf = alt.Chart(bd).mark_area(opacity=0.28, color=AZUL).encode(X, alt.Y("conf_low:Q"), alt.Y2("conf_high:Q"))
    linea = alt.Chart(bd).mark_line(color=AZUL, strokeWidth=2).encode(X, alt.Y("fit:Q"))
    puntos = alt.Chart(pt).mark_circle(size=80, color=AZUL, opacity=1).encode(
        X, alt.Y("y:Q"), tooltip=[alt.Tooltip("x:Q", title="C"), alt.Tooltip("y:Q", title="A", format=".4f")])
    capas = [pred, conf, linea, puntos]
    if not uk.empty:
        uk2 = uk.rename(columns={"x0": "x"})
        capas.append(alt.Chart(uk2).mark_rule(color=NARANJA).encode(
            alt.X("ci_low:Q"), alt.X2("ci_high:Q"), alt.Y("y_mean:Q")))
        capas.append(alt.Chart(uk2).mark_point(shape="diamond", size=120, color=NARANJA, filled=True).encode(
            alt.X("x:Q"), alt.Y("y_mean:Q"),
            tooltip=["sample", alt.Tooltip("x:Q", format=".4f"), alt.Tooltip("y_mean:Q", format=".4f")]))
    return alt.layer(*capas).properties(
        title=f"{ecuacion(res)}   R² = {res['r_squared']:.5f}", height=420).interactive()


def altair_residuales(res, xlab):
    pt = _df_pts(res).assign(obs=lambda d: np.arange(1, len(d) + 1))
    base = alt.Chart(pt).mark_circle(size=70, color=AZUL).encode(
        alt.X("x:Q", title=xlab), alt.Y("std_residuals:Q", title="Residual estandarizado"),
        tooltip=["obs", "x", alt.Tooltip("std_residuals:Q", format=".3f")])
    reglas = alt.Chart(pd.DataFrame({"y": [-2, 0, 2]})).mark_rule(strokeDash=[4, 4], color=ROJO).encode(y="y:Q")
    return (base + reglas).properties(title="Residuales estandarizados", height=300)
