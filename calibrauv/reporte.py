"""Tablas de resultados y reporte HTML autocontenido."""

from __future__ import annotations

import datetime as dt
import html

import pandas as pd

from . import __version__
from .graficos import ecuacion
from .interpretacion import evaluar

AVISO_IA = ("CalibraUV fue diseñada en su mayoría con apoyo de Claude (Anthropic), un asistente "
            "de IA, y revisada por personas. Los resultados deben ser verificados por un analista "
            "calificado antes de usarse en decisiones técnicas, regulatorias o clínicas.")


def _g(v, d=6):
    if v is None:
        return "n/d"
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return str(v)
    try:
        return f"{v:.{d}g}"
    except (TypeError, ValueError):
        return str(v)


def tabla_coeficientes(res) -> pd.DataFrame:
    filas = []
    conf = int(res["conf_level"] * 100)
    for nombre, clave in (("Pendiente (b)", "slope"), ("Intercepto (a)", "intercept")):
        c = res["coefficients"][clave]
        if c is None:
            continue
        filas.append({"Parámetro": nombre, "Estimado": c["estimate"], "Error estándar": c["se"],
                      "t": c["t"], "p": c["p"], f"IC {conf}% inf.": c["ci_low"],
                      f"IC {conf}% sup.": c["ci_high"]})
    return pd.DataFrame(filas)


def tabla_resumen(res, unidad, eps_molar=None) -> pd.DataFrame:
    filas = [
        ("Ecuación", ecuacion(res, 6)),
        ("n (estándares)", res["n"]),
        ("Grados de libertad residuales", res["df_resid"]),
        ("r de Pearson", _g(res["r"], 7)),
        ("R²", _g(res["r_squared"], 7)),
        ("R² ajustado", _g(res["adj_r_squared"], 7)),
        ("Error estándar de la regresión s(y/x)", _g(res["s_yx"])),
        ("F de regresión", _g(res["f_stat"])),
        ("p (F)", _g(res["f_p"], 4)),
        ("DER de la pendiente (%)", _g(res["slope_rsd_pct"], 4)),
        (f"LOD = 3.3·s/b ({unidad})", _g(res["lod"], 5)),
        (f"LOQ = 10·s/b ({unidad})", _g(res["loq"], 5)),
        (f"Rango calibrado ({unidad})", f"{_g(res['x_min'], 5)} – {_g(res['x_max'], 5)}"),
        (f"Absortividad a = b/l ({unidad})⁻¹·cm⁻¹", _g(res["absorptivity"], 6)),
    ]
    if eps_molar is not None:
        filas.append(("Absortividad molar ε (L·mol⁻¹·cm⁻¹)", _g(eps_molar, 6)))
    filas.append(("Motor de cálculo", res["engine"]))
    return pd.DataFrame([(k, str(v)) for k, v in filas], columns=["Estadístico", "Valor"])


def tabla_anova(res) -> pd.DataFrame:
    a = res["anova"]
    tot_ss = a["ss_reg"] + a["ss_res"]
    nan = float("nan")
    return pd.DataFrame({
        "Fuente": ["Regresión", "Residual", "Total"],
        "gl": [a["df_reg"], a["df_res"], a["df_reg"] + a["df_res"]],
        "SC": [a["ss_reg"], a["ss_res"], tot_ss],
        "CM": [a["ms_reg"], a["ms_res"], nan],
        "F": [a["f"], nan, nan],
        "p": [a["p"], nan, nan]})


def tabla_puntos(res) -> pd.DataFrame:
    p = res["points"]
    return pd.DataFrame({"Concentración": p["x"], "Absorbancia": p["y"], "A ajustada": p["fitted"],
                         "Residual": p["residuals"], "Residual estandarizado": p["std_residuals"],
                         "Apalancamiento": p["leverage"], "Distancia de Cook": p["cooks"]})


def tabla_muestras(res, unidad) -> pd.DataFrame:
    if not res["unknowns"]:
        return pd.DataFrame()
    conf = int(res["conf_level"] * 100)
    filas = []
    for u in res["unknowns"]:
        estado = ("Extrapolada" if u["extrapolated"] else "< LOD" if u["below_lod"]
                  else "< LOQ" if u["below_loq"] else "OK")
        filas.append({"Muestra": u["sample"], "Réplicas (m)": u["m"], "A media": u["y_mean"],
                      "DE de A": u["y_sd"], f"C ({unidad})": u["x0"], "s(C)": u["s_x0"],
                      f"IC {conf}% inf.": u["ci_low"], f"IC {conf}% sup.": u["ci_high"],
                      "DER (%)": u["rsd_pct"], "Estado": estado})
    return pd.DataFrame(filas)


def reporte_html(res, meta: dict, fig_plotly=None, fig_diag=None, eps_molar=None) -> str:
    unidad = meta.get("unidad", "")
    css = """body{font-family:system-ui,Segoe UI,Roboto,sans-serif;max-width:980px;margin:2rem auto;
    padding:0 1rem;color:#1d2330}h1{color:#0072B2}table{border-collapse:collapse;margin:.6rem 0 1.4rem;
    font-size:.9rem}td,th{border:1px solid #ccd;padding:.3rem .6rem;text-align:right}th{background:#eef3f8}
    td:first-child,th:first-child{text-align:left}.ok{color:#007a55}.aviso{color:#b36b00}.mal{color:#c0392b}
    .ia{background:#f5f7fa;border-left:4px solid #0072B2;padding:.7rem 1rem;font-size:.85rem}"""

    def t(df):
        return df.to_html(index=False, float_format=lambda v: f"{v:.6g}", na_rep="", border=0)

    ev = "".join(f"<tr><td>{html.escape(e['prueba'])}</td><td>{html.escape(e['valor'])}</td>"
                 f"<td class='{e['estado']}' style='text-align:left'>{html.escape(e['mensaje'])}</td></tr>"
                 for e in evaluar(res))
    mt = "".join(f"<li><b>{html.escape(k)}:</b> {html.escape(str(v))}</li>" for k, v in meta.items() if v)
    figs = ""
    if fig_plotly is not None:
        figs += fig_plotly.to_html(full_html=False, include_plotlyjs="cdn")
    if fig_diag is not None:
        figs += fig_diag.to_html(full_html=False, include_plotlyjs=False)
    mu = tabla_muestras(res, unidad)
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Reporte CalibraUV</title><style>{css}</style></head><body>
<h1>Reporte de curva de calibración UV-Vis</h1>
<p>Generado el {dt.datetime.now():%Y-%m-%d %H:%M} con CalibraUV v{__version__}</p>
<ul>{mt}</ul>
<h2>Resumen</h2>{t(tabla_resumen(res, unidad, eps_molar))}
<h2>Coeficientes</h2>{t(tabla_coeficientes(res))}
<h2>ANOVA de la regresión</h2>{t(tabla_anova(res))}
<h2>Evaluación de supuestos</h2><table><tr><th>Prueba</th><th>Valor</th><th>Interpretación</th></tr>{ev}</table>
{"<h2>Muestras</h2>" + t(mu) if not mu.empty else ""}
<h2>Gráficos</h2>{figs}
<h2>Datos y residuales</h2>{t(tabla_puntos(res))}
<p class="ia">{AVISO_IA}</p></body></html>"""
