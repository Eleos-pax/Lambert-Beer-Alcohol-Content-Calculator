"""CalibraUV — graphical interface (Streamlit).

Run:  streamlit run app.py
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from calibrauv import __version__
from calibrauv import analysis as an
from calibrauv import methods as M
from calibrauv import ph_differential as phd
from calibrauv import plots as P
from calibrauv.engine import UNITS, available_engines, compute, molar_absorptivity
from calibrauv.interpretation import evaluate, sample_warnings
from calibrauv.report import (AI_NOTICE, anova_table, coefficients_table, df_html, html_report,
                              points_table, samples_table, simple_html_report, summary_table)

ROOT = Path(__file__).resolve().parent
ACC = M.acceptance()
SAMPLE_COLS = ["sample", "absorbance", "sample_blank", "extract_volume_mL", "dilution_factor", "mass_g"]
st.set_page_config(page_title="CalibraUV", page_icon="🧪", layout="wide")

# Synthetic demo data available for some methods
DEMOS = {
    "GENERIC": {"standards": "example_iron_calibration.csv", "samples": "example_samples.csv",
                "analyte": "Demo: Fe(II)–o-phenanthroline", "wavelength": 510.0,
                "unit": "mg/L (ppm)", "molar_mass": 55.845},
    "TPC_FOLIN": {"standards": "demo_tpc_gallic_acid.csv", "samples": "demo_tpc_samples.csv",
                  "addition": "demo_tpc_standard_addition.csv", "precision": "demo_tpc_precision.csv",
                  "recovery": "demo_tpc_recovery.csv"},
    "TMA_PH_DIFF": {"data": "demo_ph_differential.csv"},
}


@st.cache_data
def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / name)


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


def empty(columns: dict) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=t) for c, t in columns.items()})


def normalize_samples(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    canon = {c.lower(): c for c in SAMPLE_COLS}
    canon.update({"muestra": "sample", "absorbancia": "absorbance"})
    df.columns = [canon.get(str(c).strip().lower(), str(c).strip()) for c in df.columns]
    if "sample" not in df.columns:
        df.insert(0, "sample", [f"S{i + 1}" for i in range(len(df))])
    if "absorbance" not in df.columns:
        num = df.select_dtypes("number").columns
        df["absorbance"] = df[num[0]] if len(num) else np.nan
    for c in SAMPLE_COLS[2:]:
        if c not in df.columns:
            df[c] = np.nan
    df["sample"] = df["sample"].astype(str)
    return df[SAMPLE_COLS]


def editor(label: str, key: str, demo_df: pd.DataFrame | None, cols: dict, help_text: str = ""):
    f = st.file_uploader(f"{label} — CSV or Excel", type=["csv", "xlsx", "xls"], key=f"f_{key}",
                         help=help_text or None)
    if f:
        base = read_file(f)
    elif demo_df is not None:
        base = demo_df.copy()
    else:
        base = empty(cols)
    return base


def show_method_tab(m: dict, variant: dict | None, standard: dict | None):
    st.subheader(m["name"])
    if m.get("analyte"):
        st.markdown(f"**Analyte:** {m['analyte']}")
    st.markdown(f"**Principle:** {m['principle']}")
    if variant:
        flag = "📚 literature" if variant.get("source") == "literature" else \
            "⚠️ general analytical practice — verify against your laboratory protocol"
        st.markdown(f"**Selected variant:** {variant['name']} ({flag})")
        if variant.get("note"):
            st.caption(variant["note"])
        if variant.get("reaction_time_min"):
            st.markdown(f"**Reaction time:** {variant['reaction_time_min']} min")
    if m.get("reaction_time_range_min"):
        lo, hi = m["reaction_time_range_min"]
        st.markdown(f"**Reported reaction times:** {lo}–{hi} min")
    if m.get("conditions"):
        st.markdown("**Conditions:** " + "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in m["conditions"].items()))
    if m.get("buffers"):
        b = m["buffers"]
        st.markdown(f"**Buffers:** pH 1.0 → {b['pH_1.0']}; pH 4.5 → {b['pH_4.5']} "
                    f"(⚠️ {b['source']} — verify)")
    if m.get("standards"):
        st.markdown("**Standards:** " + ", ".join(f"{s['name']} ({s['abbr']})" for s in m["standards"])
                    + (f" — selected: **{standard['name']}**" if standard else ""))
        st.caption("Molar masses of standards are general reference values; verify them for your reagent.")
    if m.get("linear_range_examples_ug_mL"):
        st.markdown("**Reported linear ranges:** " + ", ".join(f"{a}–{b} µg/mL" for a, b in
                                                             m["linear_range_examples_ug_mL"]))
    if m.get("reported_performance"):
        st.markdown(f"**Reported performance:** {m['reported_performance']}")
    for w in m.get("warnings", []):
        st.warning(w)
    if m.get("references"):
        st.markdown("**References**")
        for r in m["references"]:
            st.markdown(f"- {M.reference_markdown(r)}")
    st.caption("Method parameters are stored in `calibrauv/methods.json`. "
               "Values marked as general practice are not taken from the cited references.")


def show_ai_tab():
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


# ===================================================================== sidebar
engines = available_engines()
all_methods = M.methods()
with st.sidebar:
    st.title("🧪 CalibraUV")
    st.caption(f"v{__version__} · UV-Vis calibration curve · Beer-Lambert law")

    st.subheader("Method")
    mid = st.selectbox("Assay / method", [m["id"] for m in all_methods],
                       format_func=lambda i: M.get(i)["name"],
                       help="Presets from the literature (calibrauv/methods.json). "
                            "'Generic' works for any analyte that follows the Beer-Lambert law.")
    method = M.get(mid)
    variant = None
    if method.get("variants"):
        vi = st.selectbox("Variant / conditions", range(len(method["variants"])),
                          format_func=lambda i: method["variants"][i]["name"], key=f"var_{mid}")
        variant = method["variants"][vi]
    standard = None
    if method.get("standards"):
        si = st.selectbox("Reference standard", range(len(method["standards"])),
                          format_func=lambda i: f"{method['standards'][i]['name']} "
                                                f"({method['standards'][i]['abbr']})", key=f"std_{mid}")
        standard = method["standards"][si]

    demo = DEMOS.get(mid)
    use_demo = st.checkbox("Load demo data", demo is not None, disabled=demo is None, key=f"demo_{mid}",
                           help="Synthetic values, only to show how the app works. "
                                "Untick it to start with empty tables.")
    if demo is None:
        st.caption("No demo data for this method: enter your own data.")
    if not use_demo:
        demo = None

    is_curve = method["type"] == "curve"
    if is_curve:
        default_analyte = (demo or {}).get("analyte") or (
            f"{method['analyte']}" + (f" as {standard['name']}" if standard else ""))
        analyte = st.text_input("Analyte", default_analyte, key=f"an_{mid}_{standard and standard['abbr']}",
                                placeholder="e.g. KMnO₄, ethanol, Fe(II), caffeine…")
        wl_default = (demo or {}).get("wavelength") or (variant or {}).get("wavelength_nm")
        wavelength = st.number_input("Wavelength λ (nm)", 190.0, 1100.0,
                                     float(wl_default) if wl_default else None, 1.0,
                                     placeholder="optional", key=f"wl_{mid}_{variant and variant['name']}")
        unit_default = (demo or {}).get("unit") or method.get("default_unit") or "mol/L"
        unit = st.selectbox("Concentration unit of the standards", list(UNITS),
                            index=list(UNITS).index(unit_default), key=f"unit_{mid}")
        molar_mass = None
        if UNITS[unit] is None:
            mm_default = (demo or {}).get("molar_mass") or (standard or {}).get("molar_mass") or 0.0
            molar_mass = st.number_input("Molar mass (g/mol) for ε", 0.0, 1e6, float(mm_default), 0.001,
                                         format="%.3f", help="0 = do not compute molar ε",
                                         key=f"mm_{mid}_{standard and standard['abbr']}")
        path_length = st.number_input("Path length l (cm)", 0.01, 10.0, 1.0, 0.1)
        reagent_blank = st.number_input(
            "Reagent blank absorbance", -1.0, 3.0, 0.0, 0.001, format="%.4f",
            help="Subtracted from every standard and sample (A_corr = A − A_blank). "
                 "Leave 0 if the blank was used to zero the instrument.")

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
        lod_label = st.selectbox("σ for LOD/LOQ (ICH Q2)", list(an.LOD_BASES))
        lod_basis = an.LOD_BASES[lod_label]
        c1, c2 = st.columns(2)
        r2_min = c1.number_input("R² minimum", 0.9, 1.0, float(ACC["r2_min"]), 0.001, format="%.3f")
        r2_rec = c2.number_input("R² recommended", 0.9, 1.0, float(ACC["r2_recommended"]), 0.001,
                                 format="%.3f")

        st.subheader("Plots")
        lib = st.radio("Library", ["Plotly (interactive)", "Matplotlib + Seaborn", "Matplotlib",
                                   "Altair"], index=0)
        style = st.selectbox("Seaborn style", ["whitegrid", "darkgrid", "ticks", "white"],
                             disabled=lib != "Matplotlib + Seaborn")
    else:
        const = method["constants"]
        st.caption(f"No calibration curve: uses the known ε of {const['pigment']}.")
        mw = st.number_input("Molar mass MW (g/mol)", 1.0, 1e5, float(const["MW_g_mol"]), 0.1)
        eps_known = st.number_input("Molar absorptivity ε (L·mol⁻¹·cm⁻¹)", 1.0, 1e7,
                                    float(const["epsilon_L_mol_cm"]), 100.0)
        path_length = st.number_input("Path length l (cm)", 0.01, 10.0, 1.0, 0.1)
        st.caption(f"⚠️ Default constants: {const['source']} — verify.")
    st.divider()
    st.caption("🤖 " + AI_NOTICE)

st.header("UV-Vis quantification · Beer-Lambert law")
st.markdown(r"Beer-Lambert law: $A = \varepsilon \, l \, c$ → linear regression "
            r"$A = a + b\,C$, where $b = \varepsilon l$ is the sensitivity.")
st.caption(f"Method: **{method['name']}**" + (f" · {variant['name']}" if variant else ""))

# =========================================================== pH differential
if not is_curve:
    t_data, t_res, t_rep, t_meth, t_ai = st.tabs(
        ["📋 Data", "🧮 Results", "📄 Report", "📚 Method & references", "🤖 AI & license"])
    with t_data:
        st.markdown("One row per replicate. Read each diluted sample at **520 nm** and **700 nm** "
                    "in **pH 1.0** and **pH 4.5** buffers. `extract_volume_mL` and `mass_g` are "
                    "optional (for content per gram).")
        base = editor("Absorbance readings", "ph", load_csv(demo["data"]) if demo else None,
                      {c: (str if c == "sample" else float) for c in phd.COLUMNS})
        for c in phd.COLUMNS:
            if c not in base.columns:
                base[c] = np.nan
        data = st.data_editor(base[phd.COLUMNS], num_rows="dynamic", width="stretch", key="ed_ph")
    rep, summ = phd.compute(data, mw, eps_known, path_length)
    with t_res:
        st.latex(r"A = (A_{520}-A_{700})_{pH\,1.0} - (A_{520}-A_{700})_{pH\,4.5}")
        st.latex(r"C\;(\mathrm{mg/L}) = \frac{A \cdot MW \cdot DF \cdot 1000}{\varepsilon \cdot l}")
        if rep.empty:
            st.info("Enter readings in the Data tab.")
        else:
            st.subheader(f"Summary (mean ± SD, {const['abbr']})")
            st.dataframe(summ.rename(columns={
                "C_mg_L_mean": f"C mean (mg {const['abbr']}/L)", "C_mg_L_sd": "C SD",
                "C_mg_L_rsd_pct": "C RSD (%)", "content_mg_g_mean": f"Content mean (mg {const['abbr']}/g)",
                "content_mg_g_sd": "Content SD", "content_mg_g_rsd_pct": "Content RSD (%)"})
                .style.format(precision=4, na_rep=""), hide_index=True, width="stretch")
            st.subheader("Replicates")
            st.dataframe(rep.style.format(precision=4, na_rep=""), hide_index=True, width="stretch")
            for w in phd.warnings(rep, tuple(ACC["absorbance_range"])):
                st.warning(w)
            if method.get("reported_performance"):
                st.caption(f"Reference performance: {method['reported_performance']}")
    with t_rep:
        if not rep.empty:
            meta = {"Method": method["name"], "Pigment": const["pigment"], "MW (g/mol)": mw,
                    "ε (L/mol/cm)": eps_known, "Path length (cm)": path_length}
            refs = "<ul>" + "".join(f"<li>{M.reference_text(r)}</li>" for r in method["references"]) + "</ul>"
            html = simple_html_report("Total monomeric anthocyanins – pH differential", meta,
                                      [("Summary", df_html(summ)), ("Replicates", df_html(rep)),
                                       ("References", refs)])
            st.download_button("⬇️ HTML report", html, "ph_differential_report.html", "text/html")
            st.download_button("⬇️ Results CSV", rep.to_csv(index=False), "ph_differential.csv", "text/csv")
    with t_meth:
        show_method_tab(method, variant, standard)
    with t_ai:
        show_ai_tab()
    st.stop()

# ======================================================== calibration curve
xlab = f"Concentration ({unit})"
abbr = standard["abbr"] if standard else None
banner = st.container()
tabs = st.tabs(["📋 Data", "📊 Statistics", "📈 Plots", "🧫 Samples & content", "➕ Standard addition",
                "✅ Validation", "📄 Report", "📚 Method & references", "🤖 AI & license"])
(t_data, t_stats, t_plots, t_samples, t_add, t_val, t_rep, t_meth, t_ai) = tabs

with t_data:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Standards")
        base = editor("Standards (col. 1: concentration, col. 2: absorbance)", "std",
                      load_csv(demo["standards"]) if demo else None, {"c": float, "A": float})
        base = base.iloc[:, :2].copy()
        base.columns = ["Concentration", "Absorbance"]
        standards = st.data_editor(base, num_rows="dynamic", width="stretch", key=f"ed_std_{mid}")
    with c2:
        st.subheader("Unknown samples (optional)")
        base_u = editor("Samples (one row per replicate)", "unk",
                        load_csv(demo["samples"]) if demo else None,
                        {c: (str if c == "sample" else float) for c in SAMPLE_COLS},
                        "Columns: sample, absorbance, sample_blank, extract_volume_mL, "
                        "dilution_factor, mass_g")
        samples = st.data_editor(normalize_samples(base_u), num_rows="dynamic", width="stretch",
                                 key=f"ed_unk_{mid}")
        st.caption("`sample_blank`: extract with all reagents except the chromogenic one (coloured "
                   "extracts). `extract_volume_mL`, `dilution_factor` and `mass_g` give the content "
                   "per gram: Content = C · V · DF / m.")
    blank_readings = None
    if lod_basis == "blanks":
        st.subheader("Blank readings for LOD/LOQ (≥ 10 recommended)")
        blank_readings = st.data_editor(empty({"blank_absorbance": float}), num_rows="dynamic",
                                        key="ed_blanks")["blank_absorbance"]
    st.info(f"Recommended design: ≥ {ACC['min_levels']} levels × {ACC['replicates_per_level']} replicates; "
            f"absorbances between {ACC['absorbance_range'][0]} and {ACC['absorbance_range'][1]}.")

# --------------------------------------------------------------- computation
if len(standards.dropna()) < 3:
    banner.info("Enter at least 3 standards (concentration, absorbance) in the Data tab, "
            "or upload a CSV/Excel file.")
    st.stop()
title = " · ".join(t for t in (analyte.strip(), f"λ = {wavelength:.0f} nm" if wavelength else "")
                   if t) or None
std_corr = an.correct_standards(standards.dropna(), reagent_blank)
smp = samples.dropna(subset=["absorbance"]).copy()
smp["sample"] = smp["sample"].replace({"nan": None, "None": None}).fillna("S")
smp_corr = an.correct_samples(smp, reagent_blank)
try:
    res = compute(std_corr, smp_corr[["sample", "absorbance"]], engine=engine, conf=conf,
                  origin=origin, path_length=path_length)
except Exception as exc:  # noqa: BLE001
    st.error(f"The regression could not be computed: {exc}")
    st.stop()
an.apply_lod_basis(res, lod_basis, blank_readings)
if res.get("engine_note"):
    st.warning(res["engine_note"])
eps = molar_absorptivity(res, unit, molar_mass)
verdict, reasons = an.curve_verdict(res, r2_min)
design = an.design_check(res, ACC["min_levels"], ACC["replicates_per_level"])
a_lo, a_hi = ACC["absorbance_range"]

if verdict == "accepted":
    banner.success(f"✅ Calibration curve accepted (R² = {res['r_squared']:.5f} ≥ {r2_min}).")
else:
    banner.error("❌ Calibration curve rejected: " + "; ".join(reasons) +
             ". Review the standards before quantifying samples.")

with t_stats:
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("R²", f"{res['r_squared']:.5f}")
    m2.metric("Slope b", f"{res['coefficients']['slope']['estimate']:.5g}")
    m3.metric("s(y/x)", f"{res['s_yx']:.3g}")
    m4.metric(f"LOD ({unit})", f"{res['lod']:.3g}")
    m5.metric(f"LOQ ({unit})", f"{res['loq']:.3g}")
    st.markdown(f"**Equation:** `{P.equation(res, 6)}`  ·  **Engine:** {res['engine']}  ·  "
                f"**σ for LOD/LOQ:** {lod_label}" + (f"  ·  **Reagent blank:** {reagent_blank:.4f}"
                                                     if reagent_blank else ""))
    if res.get("lod_note"):
        st.warning(res["lod_note"])
    if eps is not None:
        st.markdown(f"**Molar absorptivity ε** = {eps:,.0f} L·mol⁻¹·cm⁻¹ "
                    + (f"(at {wavelength:.0f} nm, " if wavelength else "(")
                    + f"l = {path_length} cm)")
    if not design["levels_ok"]:
        st.warning(f"Only {design['levels']} concentration levels (≥ {ACC['min_levels']} recommended).")
    if not design["reps_ok"]:
        st.warning(f"Some levels have {design['min_reps']} replicate(s) "
                   f"(≥ {ACC['replicates_per_level']} recommended).")
    out_range = [y for y in res["points"]["y"] if not (a_lo <= y <= a_hi)]
    if out_range:
        st.info(f"{len(out_range)} standard(s) outside the working absorbance range {a_lo}–{a_hi}.")

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
    for e in evaluate(res, r2_min, r2_rec):
        st.markdown(f"{icon[e['status']]} **{e['test']}** — {e['value']}  \n{e['message']}")

    with st.expander("Data, residuals and influence"):
        st.dataframe(points_table(res).style.format(precision=5), hide_index=True,
                     width="stretch")

fig_p = P.plotly_calibration(res, xlab, title=title)
fig_d = P.plotly_diagnostics(res, xlab)

with t_plots:
    if lib.startswith("Plotly"):
        st.plotly_chart(fig_p, width="stretch")
        st.plotly_chart(fig_d, width="stretch")
    elif lib.startswith("Matplotlib"):
        use_sns = "Seaborn" in lib
        f1 = P.mpl_calibration(res, xlab, title=title, seaborn_style=style, use_seaborn=use_sns)
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

# ----------------------------------------------------------- samples/content
content_df, content_label = pd.DataFrame(), ""
with t_samples:
    tm = samples_table(res, unit)
    if tm.empty:
        st.info("Add sample absorbances in the Data tab.")
    else:
        st.markdown(r"Concentration by inverse regression: $\hat C_0 = (\bar A_0 - a)/b$, with "
                    r"$s_{C_0} = \frac{s_{y/x}}{b}\sqrt{\frac1m + \frac1n + "
                    r"\frac{(\bar A_0-\bar A)^2}{b^2 S_{xx}}}$  (absorbances blank-corrected)")
        st.subheader("Concentration in the measured solution")
        st.dataframe(tm.style.format(precision=5, na_rep=""), hide_index=True, width="stretch")
        for msg in sample_warnings(res):
            st.warning(msg)
        if verdict == "rejected":
            st.error("The curve was rejected: these results should not be reported.")

        st.subheader("Content in the sample")
        basis = st.selectbox("Mass basis", ["DW (dry weight)", "FW (fresh weight)", "extract"])
        content_label = an.content_unit(unit, abbr, "g " + basis.split()[0])
        st.latex(r"\text{Content} = \frac{C \cdot V_{extract} \cdot DF}{m_{sample}}")
        content_df = an.sample_content(res, smp_corr, unit)
        if content_df.empty or content_df["content_mean"].isna().all():
            st.info("Fill `extract_volume_mL` and `mass_g` (and `dilution_factor`) in the samples "
                    "table to obtain the content per gram.")
        else:
            conf_pct = int(conf * 100)
            content_df = content_df.rename(columns={
                "sample": "Sample", "n": "Replicates", "C_mean": f"C mean ({unit})",
                "content_mean": f"Content ({content_label})", "content_sd": "SD",
                "content_rsd_pct": "RSD (%)", "ci_low": f"Calibration {conf_pct}% CI lower",
                "ci_high": f"Calibration {conf_pct}% CI upper"})
            st.dataframe(content_df.style.format(precision=4, na_rep=""), hide_index=True,
                         width="stretch")
            st.caption("Report as mean ± SD (RSD%) of replicates, stating the standard and the mass "
                       "basis. The calibration CI is shown only when V, DF and m are identical "
                       "across replicates.")

# --------------------------------------------------------- standard addition
sa = None
with t_add:
    st.markdown("Add increasing amounts of standard to equal aliquots of sample. Enter the "
                "**final concentration of added standard** in the measured solution (same unit as "
                "the curve) and the absorbance. The sample concentration is the |x-intercept|: "
                r"$C = a/b$.")
    base_a = editor("Standard addition data (col. 1: added concentration, col. 2: absorbance)", "add",
                    load_csv(demo["addition"]) if demo and "addition" in demo else None,
                    {"added": float, "A": float})
    base_a = base_a.iloc[:, :2].copy()
    base_a.columns = ["Added concentration", "Absorbance"]
    add_data = st.data_editor(base_a, num_rows="dynamic", width="stretch", key=f"ed_add_{mid}")
    df_aliquot = st.number_input("Dilution factor of the sample aliquot in the measured solution",
                                 1.0, 1e6, 1.0, 1.0)
    add_corr = an.correct_standards(add_data.dropna(), reagent_blank)
    if len(add_corr.dropna()) >= 3 and add_corr.iloc[:, 0].nunique() >= 2:
        try:
            res_add = compute(add_corr, None, engine=engine, conf=conf)
            sa = an.standard_addition(res_add, res, ACC["standard_addition_slope_diff_pct"])
            c1, c2, c3 = st.columns(3)
            c1.metric(f"C in measured solution ({unit})", f"{sa['C']:.4g}",
                      help=f"{int(conf * 100)}% CI: {sa['ci_low']:.4g} – {sa['ci_high']:.4g}")
            c2.metric(f"C in original sample ({unit})", f"{sa['C'] * df_aliquot:.4g}")
            c3.metric("Slope difference vs external curve", f"{sa['slope_diff_pct']:.2f} %")
            st.markdown(f"{int(conf * 100)}% CI (measured solution): **{sa['ci_low']:.4g} – "
                        f"{sa['ci_high']:.4g} {unit}** · R² = {sa['r_squared']:.5f} · "
                        f"s(C) = {sa['s_C']:.3g}")
            lim = ACC["standard_addition_slope_diff_pct"]
            if sa["parallel"]:
                st.success(f"Slopes are parallel (difference < {lim}%): no significant matrix effect "
                           f"({ACC['standard_addition_source']}).")
            else:
                st.warning(f"Slope difference ≥ {lim}%: possible matrix effect — quantify by "
                           "standard addition rather than with the external curve.")
            st.plotly_chart(P.plotly_standard_addition(res_add, sa, f"Added concentration ({unit})"),
                            width="stretch")
            st.caption(r"Uncertainty: $s_{C} = \frac{s_{y/x}}{b}\sqrt{\frac1n + "
                       r"\frac{\bar y^2}{b^2 S_{xx}}}$ (Miller & Miller). Regression by "
                       f"{res_add['engine']}.")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Standard addition could not be computed: {exc}")
    else:
        st.info("Enter at least 3 points with 2 different added concentrations.")

# ---------------------------------------------------------------- validation
prec_rows, prec_all, rec_rows, rec_all = pd.DataFrame(), {}, pd.DataFrame(), {}
with t_val:
    st.subheader("ICH Q2 checklist")
    lof = res["diagnostics"].get("lack_of_fit")
    checks = [
        (design["levels_ok"], f"Linearity: {design['levels']} levels (≥ {ACC['min_levels']})"),
        (design["reps_ok"], f"Replicates per level: min {design['min_reps']} (≥ {ACC['replicates_per_level']})"),
        (res["r_squared"] >= r2_min, f"R² = {res['r_squared']:.5f} (≥ {r2_min})"),
        (lof is None or lof["p"] > 0.05, "Lack of fit not significant" if lof else
         "Lack of fit: needs replicates"),
        (1.5 <= res["diagnostics"]["durbin_watson"] <= 2.5,
         f"Residuals without trend (Durbin-Watson = {res['diagnostics']['durbin_watson']:.2f})"),
        (True, f"LOD = {res['lod']:.4g} {unit}; LOQ = {res['loq']:.4g} {unit} ({lod_label})"),
    ]
    for ok, text in checks:
        st.markdown(("✅ " if ok else "⚠️ ") + text)

    st.subheader("Precision (repeatability / intermediate precision)")
    crit_rsd_label = st.selectbox("RSD criterion", list(ACC["rsd_criteria_pct"]), index=1)
    max_rsd = ACC["rsd_criteria_pct"][crit_rsd_label]
    st.caption("Repeatability: n ≥ 6 at 100% or 9 determinations at 3 levels. Use the `series` "
               "column for another day / analyst / instrument (intermediate precision).")
    base_p = editor("Precision readings (series, absorbance)", "prec",
                    load_csv(demo["precision"]) if demo and "precision" in demo else None,
                    {"series": str, "absorbance": float})
    prec = st.data_editor(base_p, num_rows="dynamic", width="stretch", key=f"ed_prec_{mid}")
    if "series" in prec and "absorbance" in prec and len(prec.dropna(subset=["absorbance"])):
        p_in = prec.copy()
        p_in["absorbance"] = pd.to_numeric(p_in["absorbance"], errors="coerce") - reagent_blank
        prec_rows, prec_all = an.precision(res, p_in, max_rsd)
        st.dataframe(prec_rows.rename(columns={"mean_C": f"Mean C ({unit})", "rsd_pct": "RSD (%)"})
                     .style.format(precision=4, na_rep=""), hide_index=True, width="stretch")
        msg = (f"Overall: n = {prec_all['n']}, mean = {prec_all['mean_C']:.4g} {unit}, "
               f"RSD = {prec_all['rsd_pct']:.2f}% (criterion ≤ {max_rsd}%)")
        (st.success if prec_all["pass"] else st.error)(msg)
        if not prec_all["enough_n"]:
            st.warning("Fewer than 6 determinations.")

    st.subheader("Accuracy (recovery)")
    crit_rec_label = st.selectbox("Recovery criterion", list(ACC["recovery_criteria_pct"]))
    lims = tuple(ACC["recovery_criteria_pct"][crit_rec_label])
    st.latex(r"\text{Recovery}\,\% = 100\cdot\frac{C_{spiked}-C_{unspiked}}{C_{added}}")
    base_r = editor("Recovery data (level, A_unspiked, A_spiked, C_added)", "rec",
                    load_csv(demo["recovery"]) if demo and "recovery" in demo else None,
                    {"level": str, "A_unspiked": float, "A_spiked": float, "C_added": float})
    rec = st.data_editor(base_r, num_rows="dynamic", width="stretch", key=f"ed_rec_{mid}")
    if {"A_unspiked", "A_spiked", "C_added"} <= set(rec.columns) and len(rec.dropna()):
        r_in = rec.copy()
        for c in ("A_unspiked", "A_spiked"):
            r_in[c] = pd.to_numeric(r_in[c], errors="coerce") - reagent_blank
        rec_rows, rec_all = an.recovery(res, r_in, lims)
        if not rec_rows.empty:
            st.dataframe(rec_all["per_level"].rename(columns={"count": "n", "mean": "Mean recovery (%)",
                                                              "std": "SD"})
                         .style.format(precision=2, na_rep=""), hide_index=True, width="stretch")
            msg = (f"Mean recovery = {rec_all['mean']:.1f}% ± {rec_all['sd']:.1f}% "
                   f"(n = {rec_all['n']}; criterion {lims[0]}–{lims[1]}%)")
            (st.success if rec_all["pass"] else st.error)(msg)
            st.caption(ACC["recovery_source"])
    st.caption("Specificity: see the Standard addition tab. Robustness: repeat the curve varying "
               "reaction time, reagent concentration, temperature and λ (± 2 nm).")

# -------------------------------------------------------------------- report
with t_rep:
    meta = {"Method": method["name"], "Variant": variant["name"] if variant else "",
            "Reference standard": f"{standard['name']} ({standard['abbr']})" if standard else "",
            "Analyte": analyte, "Wavelength (nm)": wavelength, "Path length (cm)": path_length,
            "Reagent blank (A)": reagent_blank if reagent_blank else "",
            "unit": unit, "Confidence level": f"{conf:.0%}",
            "Model": "A = b·C (through the origin)" if origin else "A = a + b·C",
            "Curve verdict": "Accepted" if verdict == "accepted" else "Rejected: " + "; ".join(reasons)}
    extra = []
    if not content_df.empty and not content_df.iloc[:, 3].isna().all():
        extra.append((f"Content in sample ({content_label})", df_html(content_df)))
    if sa:
        extra.append(("Standard addition", df_html(pd.DataFrame([{
            f"C measured ({unit})": sa["C"], "s(C)": sa["s_C"], "CI lower": sa["ci_low"],
            "CI upper": sa["ci_high"], f"C original ({unit})": sa["C"] * df_aliquot,
            "Slope (addition)": sa["slope"], "Slope (external)": sa["slope_ext"],
            "Slope difference (%)": sa["slope_diff_pct"], "Parallel": sa["parallel"]}]))))
    if prec_all:
        extra.append((f"Precision (criterion RSD ≤ {max_rsd}%)", df_html(prec_rows)))
    if rec_all:
        extra.append((f"Recovery (criterion {lims[0]}–{lims[1]}%)", df_html(rec_all["per_level"])))
    if method.get("references"):
        extra.append(("Method references", "<ul>" + "".join(
            f"<li>{M.reference_text(r)}</li>" for r in method["references"]) + "</ul>"))
    report = html_report(res, meta, fig_p, fig_d, eps, extra, r2_min, r2_rec)
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇️ HTML report", report, "calibration_report.html", "text/html")
    c2.download_button("⬇️ Results JSON", json.dumps(res, indent=2, ensure_ascii=False, default=str),
                       "results.json", "application/json")
    c3.download_button("⬇️ Residuals CSV", points_table(res).to_csv(index=False),
                       "residuals.csv", "text/csv")
    st.caption("The HTML report includes tables, interpretation, method references and interactive "
               "plots; it can be printed to PDF from the browser.")

with t_meth:
    show_method_tab(method, variant, standard)

with t_ai:
    show_ai_tab()
