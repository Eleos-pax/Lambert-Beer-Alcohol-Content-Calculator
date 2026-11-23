"""Results tables and self-contained HTML report."""

from __future__ import annotations

import datetime as dt
import html

import pandas as pd

from . import __version__
from .i18n import get_lang, t
from .interpretation import evaluate
from .plots import equation

AI_NOTICE = ("CalibraUV was designed mostly with the help of Claude (Anthropic), an AI "
             "assistant, and reviewed by humans. Results must be verified by a qualified "
             "analyst before being used in technical, regulatory or clinical decisions.")

_CSS = """body{font-family:system-ui,Segoe UI,Roboto,sans-serif;max-width:980px;margin:2rem auto;
padding:0 1rem;color:#1d2330}h1{color:#0072B2}table{border-collapse:collapse;margin:.6rem 0 1.4rem;
font-size:.9rem}td,th{border:1px solid #ccd;padding:.3rem .6rem;text-align:right}th{background:#eef3f8}
td:first-child,th:first-child{text-align:left}.ok{color:#007a55}.warn{color:#b36b00}.bad{color:#c0392b}
.ai{background:#f5f7fa;border-left:4px solid #0072B2;padding:.7rem 1rem;font-size:.85rem}"""


def ai_notice() -> str:
    return t(AI_NOTICE)


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
    for name, key in ((t("Slope (b)"), "slope"), (t("Intercept (a)"), "intercept")):
        c = res["coefficients"][key]
        if c is None:
            continue
        rows.append({t("Parameter"): name, t("Estimate"): c["estimate"], t("Std. error"): c["se"],
                     "t": c["t"], "p": c["p"], t("{c}% CI lower", c=conf): c["ci_low"],
                     t("{c}% CI upper", c=conf): c["ci_high"]})
    return pd.DataFrame(rows)


def summary_table(res, unit, molar_eps=None) -> pd.DataFrame:
    rows = [
        (t("Equation"), equation(res, 6)),
        (t("n (standards)"), res["n"]),
        (t("Residual degrees of freedom"), res["df_resid"]),
        (t("Pearson r"), _g(res["r"], 7)),
        ("R²", _g(res["r_squared"], 7)),
        (t("Adjusted R²"), _g(res["adj_r_squared"], 7)),
        (t("Standard error of regression s(y/x)"), _g(res["s_yx"])),
        (t("Regression F"), _g(res["f_stat"])),
        ("p (F)", _g(res["f_p"], 4)),
        (t("Slope RSD (%)"), _g(res["slope_rsd_pct"], 4)),
        (f"LOD = 3.3·σ/b ({unit})", _g(res["lod"], 5)),
        (f"LOQ = 10·σ/b ({unit})", _g(res["loq"], 5)),
        (t("σ used for LOD/LOQ"), {"syx": "s(y/x)", "sa": t("s(a), SD of intercept"),
                                   "blanks": t("SD of blanks")}.get(res.get("lod_basis", "syx"))),
        (t("Calibrated range ({u})", u=unit), f"{_g(res['x_min'], 5)} – {_g(res['x_max'], 5)}"),
        (t("Absorptivity a = b/l ({u})⁻¹·cm⁻¹", u=unit), _g(res["absorptivity"], 6)),
    ]
    if molar_eps is not None:
        rows.append((t("Molar absorptivity ε (L·mol⁻¹·cm⁻¹)"), _g(molar_eps, 6)))
    rows.append((t("Computation engine"), res["engine"]))
    return pd.DataFrame([(k, str(v)) for k, v in rows], columns=[t("Statistic"), t("Value")])


def anova_table(res) -> pd.DataFrame:
    a = res["anova"]
    nan = float("nan")
    return pd.DataFrame({
        t("Source"): [t("Regression"), t("Residual"), "Total"],
        t("df"): [a["df_reg"], a["df_res"], a["df_reg"] + a["df_res"]],
        t("SS"): [a["ss_reg"], a["ss_res"], a["ss_reg"] + a["ss_res"]],
        t("MS"): [a["ms_reg"], a["ms_res"], nan],
        "F": [a["f"], nan, nan],
        "p": [a["p"], nan, nan]})


def points_table(res) -> pd.DataFrame:
    p = res["points"]
    return pd.DataFrame({t("Concentration"): p["x"], t("Absorbance"): p["y"], t("Fitted A"): p["fitted"],
                         t("Residual"): p["residuals"], t("Standardized residual"): p["std_residuals"],
                         t("Leverage"): p["leverage"], t("Cook's distance"): p["cooks"]})


def samples_table(res, unit) -> pd.DataFrame:
    if not res["unknowns"]:
        return pd.DataFrame()
    conf = int(res["conf_level"] * 100)
    rows = []
    for u in res["unknowns"]:
        status = (t("Extrapolated") if u["extrapolated"] else "< LOD" if u["below_lod"]
                  else "< LOQ" if u["below_loq"] else "OK")
        rows.append({t("Sample"): u["sample"], t("Replicates (m)"): u["m"], t("Mean A"): u["y_mean"],
                     t("SD of A"): u["y_sd"], f"C ({unit})": u["x0"], "s(C)": u["s_x0"],
                     t("{c}% CI lower", c=conf): u["ci_low"], t("{c}% CI upper", c=conf): u["ci_high"],
                     t("RSD (%)"): u["rsd_pct"], t("Status"): status})
    return pd.DataFrame(rows)


def df_html(df: pd.DataFrame) -> str:
    return df.to_html(index=False, float_format=lambda v: f"{v:.6g}", na_rep="", border=0)


def _head(title: str) -> str:
    return (f'<!doctype html><html lang="{get_lang()}"><head><meta charset="utf-8">'
            f"<title>{html.escape(t('CalibraUV report'))}</title><style>{_CSS}</style></head><body>"
            f"<h1>{html.escape(title)}</h1>"
            f"<p>{html.escape(t('Generated on {d} with CalibraUV v{v}', d=f'{dt.datetime.now():%Y-%m-%d %H:%M}', v=__version__))}</p>")


def html_report(res, meta: dict, fig_plotly=None, fig_diag=None, molar_eps=None,
                extra_sections=None, r2_min: float = 0.99, r2_rec: float = 0.995) -> str:
    """extra_sections: list of (title, html) inserted after the samples table."""
    unit = meta.pop("unit", "") if "unit" in meta else ""
    ev = "".join(f"<tr><td>{html.escape(e['test'])}</td><td>{html.escape(e['value'])}</td>"
                 f"<td class='{e['status']}' style='text-align:left'>{html.escape(e['message'])}</td></tr>"
                 for e in evaluate(res, r2_min, r2_rec))
    mt = "".join(f"<li><b>{html.escape(k)}:</b> {html.escape(str(v))}</li>" for k, v in meta.items() if v)
    figs = ""
    if fig_plotly is not None:
        figs += fig_plotly.to_html(full_html=False, include_plotlyjs="cdn")
    if fig_diag is not None:
        figs += fig_diag.to_html(full_html=False, include_plotlyjs=False)
    st = samples_table(res, unit)
    h2 = lambda s: f"<h2>{html.escape(s)}</h2>"  # noqa: E731
    return (_head(t("UV-Vis calibration curve report")) + f"<ul>{mt}</ul>"
            + h2(t("Summary")) + df_html(summary_table(res, unit, molar_eps))
            + h2(t("Coefficients")) + df_html(coefficients_table(res))
            + h2(t("Regression ANOVA")) + df_html(anova_table(res))
            + h2(t("Assumption checks"))
            + f"<table><tr><th>{t('Test')}</th><th>{t('Value')}</th><th>{t('Interpretation')}</th></tr>{ev}</table>"
            + (h2(t("Samples")) + df_html(st) if not st.empty else "")
            + "".join(h2(ti) + body for ti, body in (extra_sections or []))
            + h2(t("Plots")) + figs
            + h2(t("Data and residuals")) + df_html(points_table(res))
            + f'<p class="ai">{html.escape(ai_notice())}</p></body></html>')


def simple_html_report(title: str, meta: dict, sections: list[tuple[str, str]]) -> str:
    """Generic report (used by methods without a calibration curve, e.g. pH differential)."""
    mt = "".join(f"<li><b>{html.escape(k)}:</b> {html.escape(str(v))}</li>" for k, v in meta.items() if v)
    body = "".join(f"<h2>{html.escape(ti)}</h2>{b}" for ti, b in sections)
    return _head(title) + f"<ul>{mt}</ul>{body}" + f'<p class="ai">{html.escape(ai_notice())}</p></body></html>'
