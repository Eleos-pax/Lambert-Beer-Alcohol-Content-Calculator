"""CalibraUV — graphical interface (Streamlit).

Run:  streamlit run app.py
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pandas as pd
import streamlit as st

from calibrauv import __version__
from calibrauv import plots as P
from calibrauv.engine import UNITS, available_engines, compute, molar_absorptivity
from calibrauv.interpretation import evaluate, sample_warnings
from calibrauv.report import (AI_NOTICE, anova_table, coefficients_table, html_report,
                              points_table, samples_table, summary_table)

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="CalibraUV", page_icon="🧪", layout="wide")


@st.cache_data
def example():
    return (pd.read_csv(ROOT / "data" / "example_iron_calibration.csv"),
            pd.read_csv(ROOT / "data" / "example_samples.csv"))


def read_file(f) -> pd.DataFrame:
    if f.name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(f)
    content = f.getvalue().decode("utf-8-sig", errors="replace")
    sep = ";" if content.count(";") > content.count(",") else ","
    df = pd.read_csv(StringIO(content), sep=sep)
    if sep == ";":  # regional format with decimal comma (e.g. European Excel)
        for col in df.columns:
            conv = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce")
            if conv.notna().all():
                df[col] = conv
    return df


def normalize_samples(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]
    df = df.rename(columns={"muestra": "sample", "absorbancia": "absorbance"})
    if "sample" not in df.columns:
        df.insert(0, "sample", [f"S{i + 1}" for i in range(len(df))])
    if "absorbance" not in df.columns:
        num = df.select_dtypes("number").columns
        df["absorbance"] = df[num[0]] if len(num) else pd.NA
    return df[["sample", "absorbance"]]


# ------------------------------------------------------------------ sidebar
engines = available_engines()
with st.sidebar:
    st.title("🧪 CalibraUV")
    st.caption(f"v{__version__} · UV-Vis calibration curve · Beer-Lambert law")

    st.subheader("Method")
    st.caption("Works for any analyte that follows the Beer-Lambert law.")
    use_demo = st.checkbox("Load demo data", True,
                           help="Demo only: Fe(II)–o-phenanthroline at 510 nm, in triplicate. "
                                "Untick it to start with an empty table and enter your own data.")
    analyte = st.text_input("Analyte", "Demo: Fe(II)–o-phenanthroline" if use_demo else "",
                            placeholder="e.g. KMnO₄, ethanol, Fe(II), caffeine…")
    wavelength = st.number_input("Wavelength λ (nm)", 190.0, 1100.0,
                                 510.0 if use_demo else None, 1.0, placeholder="optional")
    unit = st.selectbox("Concentration unit", list(UNITS), index=3 if use_demo else 0)
    molar_mass = None
    if UNITS[unit] is None:
        molar_mass = st.number_input("Molar mass (g/mol) for ε", 0.0, 1e6,
                                     55.845 if use_demo else 0.0, 0.001, format="%.3f",
                                     help="0 = do not compute molar ε")
    path_length = st.number_input("Path length l (cm)", 0.01, 10.0, 1.0, 0.1)

    st.subheader("Statistics")
    conf = st.select_slider("Confidence level", [0.90, 0.95, 0.99], 0.95,
                            format_func=lambda v: f"{v:.0%}")
    origin = st.checkbox("Force through the origin (A = b·C)", False,
                         help="Only if the intercept is not significant and the blank is corrected.")
    engine_options = ["auto", "R", "Python"] if engines["R"] else ["Python"]
    engine = st.selectbox("Computation engine", engine_options,
                          help="R (stats::lm) is the reference engine; Python is the fallback.")
    if not engines["R"]:
        st.warning("R not found: Python will be used. Install R to use stats::lm.")

    st.subheader("Plots")
    lib = st.radio("Library", ["Plotly (interactive)", "Matplotlib + Seaborn", "Matplotlib",
                               "Altair"], index=0)
    style = st.selectbox("Seaborn style", ["whitegrid", "darkgrid", "ticks", "white"],
                         disabled=lib != "Matplotlib + Seaborn")
    st.divider()
    st.caption("🤖 " + AI_NOTICE)

xlab = f"Concentration ({unit})"

# -------------------------------------------------------------------- data
st.header("UV-Vis calibration curve")
st.markdown(r"Beer-Lambert law: $A = \varepsilon \, l \, c$ → linear regression "
            r"$A = a + b\,C$, where $b = \varepsilon l$ is the sensitivity.")

tab_data, tab_stats, tab_plots, tab_samples, tab_report, tab_ai = st.tabs(
    ["📋 Data", "📊 Statistics", "📈 Plots", "🧫 Samples", "📄 Report", "🤖 AI & license"])

std_ex, unk_ex = example()
with tab_data:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Standards")
        f = st.file_uploader("CSV or Excel (column 1: concentration, column 2: absorbance)",
                             type=["csv", "xlsx", "xls"], key="f_std")
        if f:
            base = read_file(f)
        elif use_demo:
            base = std_ex
        else:
            base = pd.DataFrame({"c": pd.Series(dtype=float), "A": pd.Series(dtype=float)})
        base = base.iloc[:, :2].copy()
        base.columns = ["Concentration", "Absorbance"]
        standards = st.data_editor(base, num_rows="dynamic", width="stretch", key="ed_std")
    with c2:
        st.subheader("Unknown samples (optional)")
        f2 = st.file_uploader("CSV or Excel with columns: sample, absorbance (replicates as rows)",
                              type=["csv", "xlsx", "xls"], key="f_unk")
        if f2:
            base_u = normalize_samples(read_file(f2))
        elif use_demo:
            base_u = normalize_samples(unk_ex)
        else:
            base_u = pd.DataFrame({"sample": pd.Series(dtype=str),
                                   "absorbance": pd.Series(dtype=float)})
        samples = st.data_editor(base_u, num_rows="dynamic", width="stretch", key="ed_unk")
    st.info("Tip: measure each standard in triplicate so lack of fit can be evaluated, "
            "and keep absorbances between ~0.1 and 1.0.")

# ------------------------------------------------------------- computation
if len(standards.dropna()) < 3:
    st.info("Enter at least 3 standards (concentration, absorbance) in the Data tab, "
            "or upload a CSV/Excel file.")
    st.stop()
title = " · ".join(t for t in (analyte.strip(), f"λ = {wavelength:.0f} nm" if wavelength else "")
                   if t) or None
try:
    res = compute(standards.dropna(), samples.dropna(), engine=engine, conf=conf,
                  origin=origin, path_length=path_length)
except Exception as exc:  # noqa: BLE001
    st.error(f"The regression could not be computed: {exc}")
    st.stop()

if res.get("engine_note"):
    st.warning(res["engine_note"])
eps = molar_absorptivity(res, unit, molar_mass)

with tab_stats:
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("R²", f"{res['r_squared']:.5f}")
    m2.metric("Slope b", f"{res['coefficients']['slope']['estimate']:.5g}")
    m3.metric("s(y/x)", f"{res['s_yx']:.3g}")
    m4.metric(f"LOD ({unit})", f"{res['lod']:.3g}")
    m5.metric(f"LOQ ({unit})", f"{res['loq']:.3g}")
    st.markdown(f"**Equation:** `{P.equation(res, 6)}`  ·  **Engine:** {res['engine']}")
    if eps is not None:
        st.markdown(f"**Molar absorptivity ε** = {eps:,.0f} L·mol⁻¹·cm⁻¹ "
                    + (f"(at {wavelength:.0f} nm, " if wavelength else "(")
                    + f"l = {path_length} cm)")

    a, b = st.columns([1, 1])
    with a:
        st.subheader("Summary")
        st.dataframe(summary_table(res, unit, eps), hide_index=True, width="stretch")
    with b:
        st.subheader("Coefficients")
        st.dataframe(coefficients_table(res).style.format(precision=6), hide_index=True,
                     width="stretch")
        st.subheader("ANOVA")
        st.dataframe(anova_table(res).style.format(precision=6, na_rep=""), hide_index=True,
                     width="stretch")

    st.subheader("Assumption checks")
    icon = {"ok": "✅", "warn": "⚠️", "bad": "❌", "info": "ℹ️"}
    for e in evaluate(res):
        st.markdown(f"{icon[e['status']]} **{e['test']}** — {e['value']}  \n{e['message']}")

    with st.expander("Data, residuals and influence"):
        st.dataframe(points_table(res).style.format(precision=5), hide_index=True,
                     width="stretch")

fig_p = P.plotly_calibration(res, xlab, title=title)
fig_d = P.plotly_diagnostics(res, xlab)

with tab_plots:
    if lib.startswith("Plotly"):
        st.plotly_chart(fig_p, width="stretch")
        st.plotly_chart(fig_d, width="stretch")
    elif lib.startswith("Matplotlib"):
        use_sns = "Seaborn" in lib
        f1 = P.mpl_calibration(res, xlab, title=title,
                               seaborn_style=style, use_seaborn=use_sns)
        f2 = P.mpl_diagnostics(res, xlab, seaborn_style=style, use_seaborn=use_sns)
        st.pyplot(f1)
        st.download_button("⬇️ Curve PNG (300 dpi)", P.fig_to_png(f1), "calibration_curve.png",
                           "image/png")
        st.pyplot(f2)
        st.download_button("⬇️ Diagnostics PNG (300 dpi)", P.fig_to_png(f2), "diagnostics.png",
                           "image/png")
    else:
        st.altair_chart(P.altair_calibration(res, xlab), width="stretch")
        st.altair_chart(P.altair_residuals(res, xlab), width="stretch")

with tab_samples:
    tm = samples_table(res, unit)
    if tm.empty:
        st.info("Add sample absorbances in the Data tab.")
    else:
        st.markdown(r"Concentration by inverse regression: $\hat C_0 = (\bar A_0 - a)/b$, with "
                    r"$s_{C_0} = \frac{s_{y/x}}{b}\sqrt{\frac1m + \frac1n + "
                    r"\frac{(\bar A_0-\bar A)^2}{b^2 S_{xx}}}$")
        st.dataframe(tm.style.format(precision=5, na_rep=""), hide_index=True, width="stretch")
        for msg in sample_warnings(res):
            st.warning(msg)
        st.caption("If you diluted the sample, multiply the concentration and its interval by "
                   "the dilution factor.")

with tab_report:
    meta = {"Analyte": analyte, "Wavelength (nm)": wavelength, "Path length (cm)": path_length,
            "unit": unit, "Confidence level": f"{conf:.0%}",
            "Model": "A = b·C (through the origin)" if origin else "A = a + b·C"}
    report = html_report(res, meta, fig_p, fig_d, eps)
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇️ HTML report", report, "calibration_report.html", "text/html")
    c2.download_button("⬇️ Results JSON", json.dumps(res, indent=2, ensure_ascii=False),
                       "results.json", "application/json")
    c3.download_button("⬇️ Residuals CSV", points_table(res).to_csv(index=False),
                       "residuals.csv", "text/csv")
    st.caption("The HTML report includes tables, interpretation and interactive plots; "
               "it can be printed to PDF from the browser.")

with tab_ai:
    st.subheader("Free and open-source software")
    st.markdown("CalibraUV is distributed under the **MIT license**: you may use, study, "
                "modify and redistribute it freely.")
    st.subheader("Built with AI assistance")
    st.markdown(AI_NOTICE)
    st.markdown("This is an independent project, not affiliated with or endorsed by "
                "Anthropic. Claude is a trademark of Anthropic.")
    pol = ROOT / "RESPONSIBLE_AI_POLICY.md"
    if pol.exists():
        with st.expander("Responsible AI use policy", expanded=False):
            st.markdown(pol.read_text(encoding="utf-8"))
