"""Results tables and self-contained HTML report."""

from __future__ import annotations

import datetime as dt
import html

import pandas as pd

from . import __version__
from .interpretation import evaluate
from .plots import equation

AI_NOTICE = ("CalibraUV was designed mostly with the help of Claude (Anthropic), an AI "
             "assistant, and reviewed by humans. Results must be verified by a qualified "
             "analyst before being used in technical, regulatory or clinical decisions.")


def _g(v, d=6):
    if v is None:
        return "n/a"
    if isinstance(v, int) and not isinstance(v, bool):
        return str(v)
    try:
        return f"{v:.{d}g}"
    except (TypeError, ValueError):
        return str(v)


def coefficients_table(res) -> pd.DataFrame:
    rows = []
    conf = int(res["conf_level"] * 100)
    for name, key in (("Slope (b)", "slope"), ("Intercept (a)", "intercept")):
        c = res["coefficients"][key]
        if c is None:
            continue
        rows.append({"Parameter": name, "Estimate": c["estimate"], "Std. error": c["se"],
                     "t": c["t"], "p": c["p"], f"{conf}% CI lower": c["ci_low"],
                     f"{conf}% CI upper": c["ci_high"]})
    return pd.DataFrame(rows)


def summary_table(res, unit, molar_eps=None) -> pd.DataFrame:
    rows = [
        ("Equation", equation(res, 6)),
        ("n (standards)", res["n"]),
        ("Residual degrees of freedom", res["df_resid"]),
        ("Pearson r", _g(res["r"], 7)),
        ("R²", _g(res["r_squared"], 7)),
        ("Adjusted R²", _g(res["adj_r_squared"], 7)),
        ("Standard error of regression s(y/x)", _g(res["s_yx"])),
        ("Regression F", _g(res["f_stat"])),
        ("p (F)", _g(res["f_p"], 4)),
        ("Slope RSD (%)", _g(res["slope_rsd_pct"], 4)),
        (f"LOD = 3.3·s/b ({unit})", _g(res["lod"], 5)),
        (f"LOQ = 10·s/b ({unit})", _g(res["loq"], 5)),
        (f"Calibrated range ({unit})", f"{_g(res['x_min'], 5)} – {_g(res['x_max'], 5)}"),
        (f"Absorptivity a = b/l ({unit})⁻¹·cm⁻¹", _g(res["absorptivity"], 6)),
    ]
    if molar_eps is not None:
        rows.append(("Molar absorptivity ε (L·mol⁻¹·cm⁻¹)", _g(molar_eps, 6)))
    rows.append(("Computation engine", res["engine"]))
    return pd.DataFrame([(k, str(v)) for k, v in rows], columns=["Statistic", "Value"])


def anova_table(res) -> pd.DataFrame:
    a = res["anova"]
    nan = float("nan")
    return pd.DataFrame({
        "Source": ["Regression", "Residual", "Total"],
        "df": [a["df_reg"], a["df_res"], a["df_reg"] + a["df_res"]],
        "SS": [a["ss_reg"], a["ss_res"], a["ss_reg"] + a["ss_res"]],
        "MS": [a["ms_reg"], a["ms_res"], nan],
        "F": [a["f"], nan, nan],
        "p": [a["p"], nan, nan]})


def points_table(res) -> pd.DataFrame:
    p = res["points"]
    return pd.DataFrame({"Concentration": p["x"], "Absorbance": p["y"], "Fitted A": p["fitted"],
                         "Residual": p["residuals"], "Standardized residual": p["std_residuals"],
                         "Leverage": p["leverage"], "Cook's distance": p["cooks"]})


def samples_table(res, unit) -> pd.DataFrame:
    if not res["unknowns"]:
        return pd.DataFrame()
    conf = int(res["conf_level"] * 100)
    rows = []
    for u in res["unknowns"]:
        status = ("Extrapolated" if u["extrapolated"] else "< LOD" if u["below_lod"]
                  else "< LOQ" if u["below_loq"] else "OK")
        rows.append({"Sample": u["sample"], "Replicates (m)": u["m"], "Mean A": u["y_mean"],
                     "SD of A": u["y_sd"], f"C ({unit})": u["x0"], "s(C)": u["s_x0"],
                     f"{conf}% CI lower": u["ci_low"], f"{conf}% CI upper": u["ci_high"],
                     "RSD (%)": u["rsd_pct"], "Status": status})
    return pd.DataFrame(rows)


def html_report(res, meta: dict, fig_plotly=None, fig_diag=None, molar_eps=None) -> str:
    unit = meta.get("unit", "")
    css = """body{font-family:system-ui,Segoe UI,Roboto,sans-serif;max-width:980px;margin:2rem auto;
    padding:0 1rem;color:#1d2330}h1{color:#0072B2}table{border-collapse:collapse;margin:.6rem 0 1.4rem;
    font-size:.9rem}td,th{border:1px solid #ccd;padding:.3rem .6rem;text-align:right}th{background:#eef3f8}
    td:first-child,th:first-child{text-align:left}.ok{color:#007a55}.warn{color:#b36b00}.bad{color:#c0392b}
    .ai{background:#f5f7fa;border-left:4px solid #0072B2;padding:.7rem 1rem;font-size:.85rem}"""

    def t(df):
        return df.to_html(index=False, float_format=lambda v: f"{v:.6g}", na_rep="", border=0)

    ev = "".join(f"<tr><td>{html.escape(e['test'])}</td><td>{html.escape(e['value'])}</td>"
                 f"<td class='{e['status']}' style='text-align:left'>{html.escape(e['message'])}</td></tr>"
                 for e in evaluate(res))
    mt = "".join(f"<li><b>{html.escape(k)}:</b> {html.escape(str(v))}</li>" for k, v in meta.items() if v)
    figs = ""
    if fig_plotly is not None:
        figs += fig_plotly.to_html(full_html=False, include_plotlyjs="cdn")
    if fig_diag is not None:
        figs += fig_diag.to_html(full_html=False, include_plotlyjs=False)
    st = samples_table(res, unit)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>CalibraUV report</title><style>{css}</style></head><body>
<h1>UV-Vis calibration curve report</h1>
<p>Generated on {dt.datetime.now():%Y-%m-%d %H:%M} with CalibraUV v{__version__}</p>
<ul>{mt}</ul>
<h2>Summary</h2>{t(summary_table(res, unit, molar_eps))}
<h2>Coefficients</h2>{t(coefficients_table(res))}
<h2>Regression ANOVA</h2>{t(anova_table(res))}
<h2>Assumption checks</h2><table><tr><th>Test</th><th>Value</th><th>Interpretation</th></tr>{ev}</table>
{"<h2>Samples</h2>" + t(st) if not st.empty else ""}
<h2>Plots</h2>{figs}
<h2>Data and residuals</h2>{t(points_table(res))}
<p class="ai">{AI_NOTICE}</p></body></html>"""
