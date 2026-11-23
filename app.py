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
from calibrauv import concepts
from calibrauv import handcalc as hc
from calibrauv import methods as M
from calibrauv import ph_differential as phd
from calibrauv import plots as P
from calibrauv.engine import UNITS, available_engines, compute, molar_absorptivity
from calibrauv.i18n import LANGUAGES, field, get_lang, set_lang, t
from calibrauv.interpretation import evaluate, sample_warnings
from calibrauv.report import (ai_notice, anova_table, coefficients_table, df_html, html_report,
                              points_table, samples_table, simple_html_report, summary_table)

ROOT = Path(__file__).resolve().parent
SETTINGS = ROOT / "user_settings.json"          # local, git-ignored (remembers the language)
ACC = M.acceptance()
SAMPLE_COLS = ["sample", "absorbance", "sample_blank", "extract_conc_ug_mL", "extract_volume_mL",
               "dilution_factor", "mass_g"]
TANNIN_COLS = ["sample", "A_TP", "A_RP", "sample_blank", "extract_conc_ug_mL", "extract_volume_mL",
               "dilution_factor", "mass_g"]
st.set_page_config(page_title="CalibraUV", page_icon="🧪", layout="wide")

# Synthetic demo data available for some methods
DEMOS = {
    "GENERIC": {"standards": "example_iron_calibration.csv", "samples": "example_samples.csv",
                "analyte": "Demo: Fe(II)–o-phenanthroline", "wavelength": 510.0,
                "unit": "mg/L (ppm)", "molar_mass": 55.845},
    "LAB_TPC_FOLIN_NAOH": {"standards": "demo_lab_tpc_gallic_acid.csv", "samples": "demo_lab_tpc_samples.csv"},
    "LAB_TFC_NANO2": {"standards": "demo_lab_tfc_quercetin.csv", "samples": "demo_lab_tfc_samples.csv"},
    "LAB_TANNINS_CASEIN": {"standards": "demo_lab_tannins_tannic_acid.csv",
                           "samples": "demo_lab_tannins_samples.csv"},
    "TPC_FOLIN": {"standards": "demo_tpc_gallic_acid.csv", "samples": "demo_tpc_samples.csv",
                  "addition": "demo_tpc_standard_addition.csv", "precision": "demo_tpc_precision.csv",
                  "recovery": "demo_tpc_recovery.csv"},
    "TMA_PH_DIFF": {"data": "demo_ph_differential.csv"},
}


# ------------------------------------------------------------------ helpers
def load_settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(**kw) -> None:
    data = load_settings() | kw
    try:
        SETTINGS.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


@st.cache_data
def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / name)


def read_file(f) -> pd.DataFrame:
    if f.name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(f)
    content = f.getvalue().decode("utf-8-sig", errors="replace")
    sep = ";" if content.count(";") > content.count(",") else ","
    df = pd.read_csv(StringIO(content), sep=sep)
    if sep == ";":  # regional format with decimal comma (e.g. Excel in Spanish)
        for col in df.columns:
            conv = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce")
            if conv.notna().all():
                df[col] = conv
    return df


def empty(columns: dict) -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=ty) for c, ty in columns.items()})


def normalize(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    canon = {c.lower(): c for c in cols}
    canon.update({"muestra": "sample", "absorbancia": "absorbance", "a_pt": "A_TP", "a_pr": "A_RP"})
    df.columns = [canon.get(str(c).strip().lower(), str(c).strip()) for c in df.columns]
    if "sample" not in df.columns:
        df.insert(0, "sample", [f"S{i + 1}" for i in range(len(df))])
    if cols[1] not in df.columns:
        num = df.select_dtypes("number").columns
        df[cols[1]] = df[num[0]] if len(num) else np.nan
    for c in cols[1:]:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["sample"] = df["sample"].astype(str)
    return df[cols]


# ------------------------------------------------------- state persistence
# Streamlit forgets the value of a widget when it is not shown in a run (e.g. after
# switching method) and rebuilds tables whose labels change (e.g. after switching
# language). Everything the user types is therefore kept in st.session_state:
#   * sidebar/tab widgets use stable keys starting with "w_" (re-saved on every run);
#   * tables live in st.session_state["_tables"] and survive any change of mode.
def keep_widget_state() -> None:
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith("w_"):
            st.session_state[k] = st.session_state[k]


def init(key: str, value):
    """Default value for a widget key (only the first time)."""
    if key not in st.session_state:
        st.session_state[key] = value
    return key


def init_follow(key: str, default):
    """Default that follows the context (language, demo) until the user edits the value."""
    dkey = "_default_" + key
    if key not in st.session_state or st.session_state.get(dkey) == st.session_state[key]:
        st.session_state[key] = default
    st.session_state[dkey] = default
    return key


def uploader(label: str, key: str, help_text: str = ""):
    return st.file_uploader(t("{l} — CSV or Excel", l=label), type=["csv", "xlsx", "xls"],
                            key=f"up_{key}", help=help_text or None)


def table(name: str, initial: pd.DataFrame, use_demo: bool, upload=None, column_config=None) -> pd.DataFrame:
    """Editable table whose content survives changes of language, method, tab or options.

    The table is replaced only when the user uploads a new file or toggles the demo data.
    """
    store = st.session_state.setdefault("_tables", {})
    up_id = f"{upload.name}:{upload.size}" if upload is not None else None
    e = store.get(name)
    if e is None or (up_id and e["up"] != up_id) or e["demo"] != use_demo:
        clean = initial.reset_index(drop=True)
        e = store[name] = {"src": clean, "cur": clean, "ver": 0, "sig": None, "up": up_id, "demo": use_demo}
    key = f"_ed_{name}_{e['ver']}"
    if e["sig"] != get_lang() or key not in st.session_state:
        # rebuild the widget from the last saved content (nothing typed is lost)
        e["ver"] += 1
        e["src"], e["sig"] = e["cur"].reset_index(drop=True), get_lang()
        key = f"_ed_{name}_{e['ver']}"
    out = st.data_editor(e["src"], key=key, num_rows="dynamic", width="stretch", column_config=column_config)
    e["cur"] = out
    return out


def source(upload, demo_df: pd.DataFrame | None, cols: dict) -> pd.DataFrame:
    if upload is not None:
        return read_file(upload)
    if demo_df is not None:
        return demo_df.copy()
    return empty(cols)


def sample_column_config(default_extract_conc=None) -> dict:
    nc = st.column_config.NumberColumn
    return {
        "sample": st.column_config.TextColumn(t("sample"), help=t("Sample name (repeat it for each replicate)")),
        "absorbance": nc(t("absorbance"), format="%.4f"),
        "A_TP": nc("A_TP", help=t("Absorbance of total polyphenols (TP), before casein"), format="%.4f"),
        "A_RP": nc("A_RP", help=t("Absorbance of residual polyphenols (RP), casein supernatant"), format="%.4f"),
        "sample_blank": nc(t("sample_blank"), help=t("Extract with all reagents except the chromogenic one "
                                                     "(coloured extracts, e.g. honey)"), format="%.4f"),
        "extract_conc_ug_mL": nc(t("extract_conc_ug_mL"), default=default_extract_conc,
                                 help=t("Concentration of the extract in the solution analysed (µg/mL), "
                                        "e.g. 50 µg/mL. Content = C · DF / C_extract")),
        "extract_volume_mL": nc(t("extract_volume_mL"), help=t("Alternative: total extract volume (mL); "
                                                               "Content = C · V · DF / m")),
        "dilution_factor": nc(t("dilution_factor"), default=1.0, help=t("Dilution applied before reading")),
        "mass_g": nc(t("mass_g"), help=t("Alternative: sample mass (g) used with extract_volume_mL")),
    }


def show_method_tab(m: dict, variant: dict | None, standard: dict | None):
    st.subheader(field(m, "name"))
    if field(m, "analyte"):
        st.markdown(f"**{t('Analyte')}:** {field(m, 'analyte')}")
    st.markdown(f"**{t('Principle')}:** {field(m, 'principle')}")
    if field(m, "basis"):
        st.markdown(f"**{t('Basis')}:** {field(m, 'basis')}")
    if variant:
        flag = t("📚 literature") if variant.get("source") == "literature" else \
            t("⚠️ general analytical practice — verify against your laboratory protocol")
        st.markdown(f"**{t('Selected variant')}:** {field(variant, 'name')} ({flag})")
        if field(variant, "note"):
            st.caption(field(variant, "note"))
        if variant.get("reaction_time_min"):
            st.markdown(f"**{t('Reaction time')}:** {variant['reaction_time_min']} min")
    if m.get("reaction_time_range_min"):
        lo, hi = m["reaction_time_range_min"]
        st.markdown(f"**{t('Reported reaction times')}:** {lo}–{hi} min")
    if m.get("calibration_levels_ug_mL"):
        st.markdown(f"**{t('Calibration levels')}:** "
                    + ", ".join(f"{v:g}" for v in m["calibration_levels_ug_mL"]) + " µg/mL"
                    + (f" · **{t('Replicates')}:** {m['replicates']}" if m.get("replicates") else ""))
    if m.get("sample_concentration_ug_mL"):
        st.markdown(f"**{t('Sample solution')}:** {m['sample_concentration_ug_mL']} µg/mL "
                    + t("(enter it in the extract_conc_ug_mL column)"))
    if field(m, "conditions"):
        st.markdown(f"**{t('Conditions')}:** " + "; ".join(f"{k.replace('_', ' ')}: {v}"
                                                         for k, v in field(m, "conditions").items()))
    if m.get("buffers"):
        b = m["buffers"]
        st.markdown(f"**{t('Buffers')}:** pH 1.0 → {b['pH_1.0']}; pH 4.5 → {b['pH_4.5']} "
                    f"(⚠️ {b['source']} — {t('verify')})")
    if m.get("standards"):
        st.markdown(f"**{t('Standards')}:** " + ", ".join(f"{field(s, 'name')} ({field(s, 'abbr')})"
                                                         for s in m["standards"])
                    + (f" — {t('selected')}: **{field(standard, 'name')}**" if standard else ""))
        st.caption(t("Molar masses of standards are general reference values; verify them for your reagent."))
    if m.get("linear_range_examples_ug_mL"):
        st.markdown(f"**{t('Reported linear ranges')}:** " + ", ".join(
            f"{a}–{b} µg/mL" for a, b in m["linear_range_examples_ug_mL"]))
    if field(m, "reported_performance"):
        st.markdown(f"**{t('Reported performance')}:** {field(m, 'reported_performance')}")
    if field(m, "steps"):
        st.markdown(f"**{t('Procedure')}**")
        st.markdown("\n".join(f"{i}. {s}" for i, s in enumerate(field(m, "steps"), 1)))
    if m.get("difference"):
        st.info(field(m, "casein_dilution_note"))
    for w in field(m, "warnings") or []:
        st.warning(w)
    if m.get("group") == "lab":
        lab = M.lab_protocol()
        st.markdown(f"**{t('Laboratory')}:** {field(lab, 'institution')} · "
                    f"**{t('Equipment')}:** {field(lab, 'equipment')}")
        with st.expander(t("Criterion for selecting fractions")):
            for fr in lab.get("fraction_selection", []):
                st.markdown(f"**{field(fr, 'matrix')}:** {field(fr, 'criterion')}")
                for r in fr.get("references", []):
                    st.markdown(f"- {M.reference_markdown(r)}")
    if m.get("references"):
        st.markdown(f"**{t('References')}**")
        for r in m["references"]:
            st.markdown(f"- {M.reference_markdown(r)}")
    st.caption(t("Method parameters are stored in calibrauv/methods.json. Values marked as general "
                 "practice are not taken from the cited references."))


def show_concepts():
    st.markdown(t("What each quantity means and how to interpret it. Use it together with the "
                  "**Step-by-step calculation** tab."))
    for title, items in concepts.sections():
        st.subheader(title)
        for term, body in items:
            with st.expander(term):
                st.markdown(body)


def show_steps(stp: dict, unit: str, content_label: str, label: str = ""):
    """Formulas with the user's own numbers for one sample (see calibrauv/handcalc.py)."""
    F = hc.fmt
    k = stp["k"]
    a, b = k["a"], k["b"]
    reps = stp["reps"]
    if label:
        st.markdown(f"##### {label}")
    st.markdown(f"**1. {t('Calibration curve')}**")
    if k["origin"]:
        st.latex(rf"A = b\,C = {F(b)}\,C")
    else:
        st.latex(rf"A = a + b\,C = {F(a)} + {F(b)}\,C")
    st.caption(t("n = {n} standards · mean absorbance of the standards Ā = {y} · Sxx = {sxx} · "
                 "s(y/x) = {s} · t({df}; {c}%) = {tv}", n=k["n"], y=f"{k['y_mean']:.5g}",
                 sxx=f"{k['sxx']:.5g}", s=f"{k['s']:.4g}", df=k["df"], c=int(k["conf"] * 100),
                 tv=f"{k['t']:.4f}"))

    st.markdown(f"**2. {t('Blank correction of each replicate')}**")
    for i, r in enumerate(reps.itertuples(), 1):
        st.latex(rf"A_{{corr,{i}}} = A_{{{i}}} - A_{{\text{{{t('blank')}}}}} - A_{{\text{{{t('sample blank')}}}}} = "
                 rf"{F(r.A)} - {F(stp['reagent_blank'])} - {F(r.sample_blank)} = {F(r.A_corr)}")

    st.markdown(f"**3. {t('Mean of the m = {m} replicates', m=stp['m'])}**")
    st.latex(rf"\bar A_0 = \frac{{{' + '.join(F(v) for v in reps['A_corr'])}}}{{{stp['m']}}} = {F(stp['y0'])}")

    st.markdown(f"**4. {t('Concentration by inverse regression')}**")
    if k["origin"]:
        st.latex(rf"C_0 = \frac{{\bar A_0}}{{b}} = \frac{{{F(stp['y0'])}}}{{{F(b)}}} = {F(stp['c0_raw'])}")
    else:
        st.latex(rf"C_0 = \frac{{\bar A_0 - a}}{{b}} = \frac{{{F(stp['y0'])} - {F(a)}}}{{{F(b)}}} = {F(stp['c0_raw'])}")
    if stp["extra_dilution"] != 1:
        st.latex(rf"C_0 \times DF_{{casein}} = {F(stp['c0_raw'])} \times {F(stp['extra_dilution'])} = {F(stp['c0'])}")
    st.markdown(f"➡️ **C₀ = {stp['c0']:.5g} {unit}**")

    st.markdown(f"**5. {t('Uncertainty of the concentration')}**")
    if k["origin"]:
        st.latex(r"s_{C_0} = \frac{s_{y/x}}{|b|}\sqrt{\frac{1}{m}+\frac{\bar A_0^2}{b^2\sum x_i^2}}")
        st.latex(rf"s_{{C_0}} = \frac{{{F(k['s'])}}}{{{F(abs(b))}}}\sqrt{{\frac{{1}}{{{stp['m']}}}+"
                 rf"\frac{{{F(stp['y0'])}^2}}{{{F(b)}^2\cdot{F(k['sx2'])}}}}} = {F(stp['s_c0'])}")
    else:
        st.latex(r"s_{C_0} = \frac{s_{y/x}}{|b|}\sqrt{\frac{1}{m}+\frac{1}{n}+\frac{(\bar A_0-\bar A)^2}{b^2 S_{xx}}}")
        st.latex(rf"s_{{C_0}} = \frac{{{F(k['s'])}}}{{{F(abs(b))}}}\sqrt{{\frac{{1}}{{{stp['m']}}}+\frac{{1}}{{{k['n']}}}+"
                 rf"\frac{{({F(stp['y0'])}-{F(k['y_mean'])})^2}}{{{F(b)}^2\cdot{F(k['sxx'])}}}}} = {F(stp['s_c0'])}")

    st.markdown(f"**6. {t('Confidence interval')}**")
    st.latex(rf"C_0 \pm t\,s_{{C_0}} = {F(stp['c0'])} \pm {F(k['t'])}\times{F(stp['s_c0'])} = "
             rf"[{F(stp['ci_low'])};\ {F(stp['ci_high'])}]")

    st.markdown(f"**7. {t('Checks')}**")
    st.markdown(("✅ " if stp["in_range"] else "⚠️ ")
                + t("Calibrated range {lo}–{hi} {u}: C₀ = {c}", lo=f"{k['x_min']:.4g}", hi=f"{k['x_max']:.4g}",
                    u=unit, c=f"{stp['c0_raw']:.4g}"))
    st.markdown(("✅ " if stp["above_loq"] else "⚠️ ")
                + t("LOQ = {q} {u} (LOD = {d} {u})", q=f"{k['loq']:.4g}", d=f"{k['lod']:.4g}", u=unit))

    if reps["content"].notna().any():
        st.markdown(f"**8. {t('Content of each replicate')} ({content_label})**")
        factor = reps["content"] / reps["C"]
        for i, r in enumerate(reps.itertuples(), 1):
            dfv = r.dilution_factor if r.dilution_factor == r.dilution_factor else 1.0   # NaN → 1
            if r.extract_conc_ug_mL == r.extract_conc_ug_mL:  # extract concentration given
                # unit/scale factor (1000 for mg/g with C and C_extract in µg/mL)
                kf = r.content * r.extract_conc_ug_mL / (r.C * dfv) if r.C else factor.iloc[i - 1]
                st.latex(rf"\text{{{t('Content')}}}_{{{i}}} = \frac{{C_{{{i}}}\cdot DF}}{{C_{{extract}}}}\times{F(kf)} = "
                         rf"\frac{{{F(r.C)}\times{F(dfv)}}}{{{F(r.extract_conc_ug_mL)}}}\times{F(kf)} = {F(r.content)}")
            elif r.content == r.content:
                st.latex(rf"\text{{{t('Content')}}}_{{{i}}} = C_{{{i}}}\cdot\frac{{V}}{{1000}}\cdot\frac{{DF}}{{m}} = "
                         rf"{F(r.C)}\cdot\frac{{{F(r.extract_volume_mL)}}}{{1000}}\cdot"
                         rf"\frac{{{F(dfv)}}}{{{F(r.mass_g)}}} = {F(r.content)}")
        if stp["content_mean"] is not None:
            sd = stp["content_sd"]
            st.markdown(f"➡️ **{stp['content_mean']:.5g}" + (f" ± {sd:.3g}" if sd is not None else "")
                        + f" {content_label}** " + t("(mean ± SD)"))


def show_ai_tab():
    st.subheader(t("Free and open-source software"))
    st.markdown(t("CalibraUV is distributed under the **MIT license**: you may use, study, modify "
                  "and redistribute it freely."))
    st.subheader(t("Built with AI assistance"))
    st.markdown(ai_notice())
    st.markdown(t("This is an independent project, not affiliated with or endorsed by Anthropic. "
                  "Claude is a trademark of Anthropic."))
    st.subheader(t("Update or uninstall"))
    st.markdown(t("Close this window and run, from the `scripts` folder:\n\n"
                  "- **Update:** `update_windows.bat` (Windows) or `./scripts/update_linux.sh` (Linux)\n"
                  "- **Uninstall:** `uninstall_windows.bat` (Windows) or `./scripts/uninstall_linux.sh` (Linux)"))
    pol = ROOT / "RESPONSIBLE_AI_POLICY.md"
    if pol.exists():
        with st.expander(t("Responsible AI use policy (English)"), expanded=False):
            st.markdown(pol.read_text(encoding="utf-8"))


# ===================================================================== sidebar
keep_widget_state()
settings = load_settings()
with st.sidebar:
    langs = list(LANGUAGES)
    init("w_lang", settings.get("lang") if settings.get("lang") in langs else "en")
    lang = st.radio("🌐 Language / Idioma", langs, horizontal=True, key="w_lang",
                    format_func=lambda k: LANGUAGES[k])
    if lang != settings.get("lang"):
        save_settings(lang=lang)
    set_lang(lang)

engines = available_engines()
all_methods = M.methods()
with st.sidebar:
    st.title("🧪 CalibraUV")
    st.caption(t("v{v} · UV-Vis calibration curve · Beer-Lambert law", v=__version__))

    st.subheader(t("Method"))
    init("w_method", all_methods[0]["id"])
    mid = st.selectbox(t("Assay / method"), [m["id"] for m in all_methods], key="w_method",
                       format_func=lambda i: field(M.get(i), "name"),
                       help=t("Presets from the literature and from the laboratory protocol "
                              "(calibrauv/methods.json). 'Generic' works for any analyte that follows "
                              "the Beer-Lambert law."))
    method = M.get(mid)
    variant = None
    if method.get("variants"):
        vi = st.selectbox(t("Variant / conditions"), range(len(method["variants"])),
                          format_func=lambda i: field(method["variants"][i], "name"), key=init(f"w_var_{mid}", 0))
        variant = method["variants"][vi]
    standard = None
    if method.get("standards"):
        si = st.selectbox(t("Reference standard"), range(len(method["standards"])),
                          format_func=lambda i: f"{field(method['standards'][i], 'name')} "
                                                f"({field(method['standards'][i], 'abbr')})",
                          key=init(f"w_std_{mid}", 0))
        standard = method["standards"][si]

    demo = DEMOS.get(mid)
    use_demo = st.checkbox(t("Load demo data"), disabled=demo is None, key=init(f"w_demo_{mid}", demo is not None),
                           help=t("Synthetic values, only to show how the app works. Untick it to start "
                                  "with empty tables."))
    if demo is None:
        st.caption(t("No demo data for this method: enter your own data."))
    if not use_demo:
        demo = None

    is_curve = method["type"] == "curve"
    if is_curve:
        std_suffix = f" ({field(standard, 'abbr')})" if standard else ""
        default_analyte = (demo or {}).get("analyte") or (f"{field(method, 'analyte')}{std_suffix}")
        analyte = st.text_input(t("Analyte"), key=init_follow(f"w_an_{mid}_{standard and standard['abbr']}",
                                                               default_analyte),
                                placeholder=t("e.g. KMnO₄, ethanol, Fe(II), caffeine…"))
        wl_default = (demo or {}).get("wavelength") or (variant or {}).get("wavelength_nm")
        wavelength = st.number_input(t("Wavelength λ (nm)"), 190.0, 1100.0, step=1.0, placeholder=t("optional"),
                                     key=init_follow(f"w_wl_{mid}_{variant and variant['name']}",
                                                     float(wl_default) if wl_default else None))
        unit_default = (demo or {}).get("unit") or method.get("default_unit") or "mol/L"
        unit = st.selectbox(t("Concentration unit of the standards"), list(UNITS),
                            key=init_follow(f"w_unit_{mid}", unit_default))
        molar_mass = None
        if UNITS[unit] is None:
            mm_default = (demo or {}).get("molar_mass") or (standard or {}).get("molar_mass") or 0.0
            molar_mass = st.number_input(t("Molar mass (g/mol) for ε"), 0.0, 1e6, step=0.001,
                                         format="%.3f", help=t("0 = do not compute molar ε"),
                                         key=init_follow(f"w_mm_{mid}_{standard and standard['abbr']}",
                                                         float(mm_default)))
        path_length = st.number_input(t("Path length l (cm)"), 0.01, 10.0, step=0.1, key=init("w_path", 1.0))
        reagent_blank = st.number_input(
            t("Reagent blank absorbance"), -1.0, 3.0, step=0.001, format="%.4f", key=init(f"w_blank_{mid}", 0.0),
            help=t("Subtracted from every standard and sample (A_corr = A − A_blank). Leave 0 if the "
                   "blank was used to zero the instrument."))
        casein_df = None
        if method.get("difference"):
            casein_df = st.number_input(t("Casein step dilution factor (RP)"), 1.0, 100.0, step=0.1,
                                        key=init(f"w_casein_{mid}", float(method.get("casein_dilution_factor", 1.0))),
                                        help=field(method, "casein_dilution_note"))

        st.subheader(t("Statistics"))
        conf = st.select_slider(t("Confidence level"), [0.90, 0.95, 0.99], key=init("w_conf", 0.95),
                                format_func=lambda v: f"{v:.0%}")
        origin = st.checkbox(t("Force through the origin (A = b·C)"), key=init("w_origin", False),
                             help=t("Only if the intercept is not significant and the blank is corrected."))
        engine_options = ["auto", "R", "Python"] if engines["R"] else ["Python"]
        if st.session_state.get("w_engine") not in engine_options:
            st.session_state["w_engine"] = engine_options[0]
        engine = st.selectbox(t("Computation engine"), engine_options, key="w_engine",
                              help=t("R (stats::lm) is the reference engine; Python is the fallback."))
        if not engines["R"]:
            st.warning(t("R not found: Python will be used. Install R to use stats::lm."))
        lod_key = st.selectbox(t("σ for LOD/LOQ (ICH Q2)"), list(an.LOD_BASES), format_func=t,
                               key=init("w_lod", list(an.LOD_BASES)[0]))
        lod_basis = an.LOD_BASES[lod_key]
        c1, c2 = st.columns(2)
        r2_min = c1.number_input(t("R² minimum"), 0.9, 1.0, step=0.001, format="%.3f",
                                 key=init("w_r2min", float(ACC["r2_min"])))
        r2_rec = c2.number_input(t("R² recommended"), 0.9, 1.0, step=0.001, format="%.3f",
                                 key=init("w_r2rec", float(ACC["r2_recommended"])))

        st.subheader(t("Plots"))
        libs = ["Plotly", "Matplotlib + Seaborn", "Matplotlib", "Altair"]
        lib = st.radio(t("Library"), libs, key=init("w_lib", libs[0]),
                       format_func=lambda k: t("Plotly (interactive)") if k == "Plotly" else k)
        style = st.selectbox(t("Seaborn style"), ["whitegrid", "darkgrid", "ticks", "white"], key=init("w_style", "whitegrid"),
                             disabled=lib != "Matplotlib + Seaborn")
    else:
        const = method["constants"]
        st.caption(t("No calibration curve: uses the known ε of {p}.", p=field(const, "pigment")))
        mw = st.number_input(t("Molar mass MW (g/mol)"), 1.0, 1e5, step=0.1, key=init("w_mw", float(const["MW_g_mol"])))
        eps_known = st.number_input(t("Molar absorptivity ε (L·mol⁻¹·cm⁻¹)"), 1.0, 1e7, step=100.0,
                                    key=init("w_epsk", float(const["epsilon_L_mol_cm"])))
        path_length = st.number_input(t("Path length l (cm)"), 0.01, 10.0, step=0.1, key=init("w_path", 1.0))
        st.caption(t("⚠️ Default constants: {s} — verify.", s=const["source"]))
    st.divider()
    st.caption("🤖 " + ai_notice())

st.header(t("UV-Vis quantification · Beer-Lambert law"))
st.markdown(t(r"Beer-Lambert law: $A = \varepsilon \, l \, c$ → linear regression $A = a + b\,C$, "
              r"where $b = \varepsilon l$ is the sensitivity."))
st.caption(f"{t('Method')}: **{field(method, 'name')}**" + (f" · {field(variant, 'name')}" if variant else ""))

# =========================================================== pH differential
if not is_curve:
    t_data, t_res, t_rep, t_conc, t_meth, t_ai = st.tabs(
        [t("📋 Data"), t("🧮 Results"), t("📄 Report"), t("📖 Concepts"), t("📚 Method & references"),
         t("🤖 AI & license")])
    with t_data:
        st.markdown(t("One row per replicate. Read each diluted sample at **520 nm** and **700 nm** in "
                      "**pH 1.0** and **pH 4.5** buffers. `extract_volume_mL` and `mass_g` are optional "
                      "(for content per gram)."))
        up = uploader(t("Absorbance readings"), f"ph_{mid}")
        base = source(up, load_csv(demo["data"]) if demo else None,
                      {c: (str if c == "sample" else float) for c in phd.COLUMNS})
        for c in phd.COLUMNS:
            if c not in base.columns:
                base[c] = np.nan
        data = table(f"ph_{mid}", base[phd.COLUMNS], use_demo, up)
    rep, summ = phd.compute(data, mw, eps_known, path_length)
    abbr_c = const["abbr"]
    with t_res:
        st.latex(r"A = (A_{520}-A_{700})_{pH\,1.0} - (A_{520}-A_{700})_{pH\,4.5}")
        st.latex(r"C\;(\mathrm{mg/L}) = \frac{A \cdot MW \cdot DF \cdot 1000}{\varepsilon \cdot l}")
        if rep.empty:
            st.info(t("Enter readings in the Data tab."))
        else:
            st.subheader(t("Summary (mean ± SD, {a})", a=abbr_c))
            summ_show = summ.rename(columns={
                "sample": t("Sample"),
                "C_mg_L_mean": t("C mean (mg {a}/L)", a=abbr_c), "C_mg_L_sd": t("C SD"),
                "C_mg_L_rsd_pct": t("C RSD (%)"), "content_mg_g_mean": t("Content mean (mg {a}/g)", a=abbr_c),
                "content_mg_g_sd": t("Content SD"), "content_mg_g_rsd_pct": t("Content RSD (%)")})
            st.dataframe(summ_show.style.format(precision=4, na_rep=""), hide_index=True, width="stretch")
            st.subheader(t("Replicates"))
            st.dataframe(rep.style.format(precision=4, na_rep=""), hide_index=True, width="stretch")
            for w in phd.warnings(rep, tuple(ACC["absorbance_range"])):
                st.warning(w)
            if field(method, "reported_performance"):
                st.caption(t("Reference performance: {p}", p=field(method, "reported_performance")))
    with t_rep:
        if not rep.empty:
            meta = {t("Method"): field(method, "name"), t("Pigment"): field(const, "pigment"),
                    "MW (g/mol)": mw, "ε (L/mol/cm)": eps_known, t("Path length (cm)"): path_length}
            refs = "<ul>" + "".join(f"<li>{M.reference_text(r)}</li>" for r in method["references"]) + "</ul>"
            html = simple_html_report(field(method, "name"), meta,
                                      [(t("Summary"), df_html(summ_show)), (t("Replicates"), df_html(rep)),
                                       (t("References"), refs)])
            st.download_button(t("⬇️ HTML report"), html, "ph_differential_report.html", "text/html")
            st.download_button(t("⬇️ Results CSV"), rep.to_csv(index=False), "ph_differential.csv", "text/csv")
    with t_conc:
        show_concepts()
    with t_meth:
        show_method_tab(method, variant, standard)
    with t_ai:
        show_ai_tab()
    st.stop()

# ======================================================== calibration curve
xlab = t("Concentration ({u})", u=unit)
abbr = field(standard, "abbr") if standard else None
is_diff = bool(method.get("difference"))
banner = st.container()
tabs = st.tabs([t("📋 Data"), t("📊 Statistics"), t("📈 Plots"), t("🧫 Samples & content"),
                t("🔍 Step-by-step calculation"), t("➕ Standard addition"), t("✅ Validation"), t("📄 Report"),
                t("📖 Concepts"), t("📚 Method & references"), t("🤖 AI & license")])
(t_data, t_stats, t_plots, t_samples, t_steps, t_add, t_val, t_rep, t_conc, t_meth, t_ai) = tabs

with t_data:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader(t("Standards"))
        up = uploader(t("Standards (col. 1: concentration, col. 2: absorbance)"), f"std_{mid}")
        base = source(up, load_csv(demo["standards"]) if demo else None, {"c": float, "A": float})
        base = base.iloc[:, :2].copy()
        base.columns = ["concentration", "absorbance"]
        standards = table(f"std_{mid}", base, use_demo, up, column_config={
            "concentration": st.column_config.NumberColumn(t("Concentration"), format="%g"),
            "absorbance": st.column_config.NumberColumn(t("Absorbance"), format="%.4f")})
        if method.get("calibration_levels_ug_mL"):
            st.caption(t("Protocol levels: {l} µg/mL", l=", ".join(f"{v:g}" for v in method["calibration_levels_ug_mL"])))
    with c2:
        cols = TANNIN_COLS if is_diff else SAMPLE_COLS
        st.subheader(t("Samples: TP and RP per replicate") if is_diff else t("Unknown samples (optional)"))
        up = uploader(t("Samples (one row per replicate)"), f"unk_{mid}", t("Columns: {c}", c=", ".join(cols)))
        base_u = source(up, load_csv(demo["samples"]) if demo else None,
                        {c: (str if c == "sample" else float) for c in cols})
        samples = table(f"unk_{mid}", normalize(base_u, cols), use_demo, up,
                        column_config=sample_column_config(method.get("default_extract_conc_ug_mL")))
        st.caption(t("Content per gram: fill `extract_conc_ug_mL` (extract dissolved at a known "
                     "concentration, e.g. 50 µg/mL) **or** `extract_volume_mL` + `mass_g`. "
                     "`sample_blank`: extract with all reagents except the chromogenic one."))
    blank_readings = None
    if lod_basis == "blanks":
        st.subheader(t("Blank readings for LOD/LOQ (≥ 10 recommended)"))
        blank_readings = table(f"blanks_{mid}", empty({"blank_absorbance": float}), use_demo)["blank_absorbance"]
    st.info(t("Recommended design: ≥ {l} levels × {r} replicates; absorbances between {lo} and {hi}.",
              l=ACC["min_levels"], r=ACC["replicates_per_level"], lo=ACC["absorbance_range"][0],
              hi=ACC["absorbance_range"][1]))

# --------------------------------------------------------------- computation
if len(standards.dropna()) < 3:
    banner.info(t("Enter at least 3 standards (concentration, absorbance) in the Data tab, or upload "
                  "a CSV/Excel file."))
    st.stop()
title = " · ".join(x for x in (analyte.strip(), f"λ = {wavelength:.0f} nm" if wavelength else "") if x) or None
std_corr = an.correct_standards(standards.dropna(), reagent_blank)

if is_diff:
    # Each replicate gives two readings (TP and RP); both are sent to the engine as samples
    d = samples.dropna(subset=["A_TP", "A_RP"], how="all").copy()
    sb = pd.to_numeric(d["sample_blank"], errors="coerce").fillna(0.0)
    long = pd.concat([
        pd.DataFrame({"sample": d["sample"] + " (TP)", "absorbance": d["A_TP"] - reagent_blank - sb}),
        pd.DataFrame({"sample": d["sample"] + " (RP)", "absorbance": d["A_RP"] - reagent_blank - sb})])
    smp_corr = long.dropna(subset=["absorbance"])
else:
    smp = samples.dropna(subset=["absorbance"]).copy()
    smp["sample"] = smp["sample"].replace({"nan": None, "None": None}).fillna("S")
    smp_corr = an.correct_samples(smp, reagent_blank)
try:
    res = compute(std_corr, smp_corr[["sample", "absorbance"]], engine=engine, conf=conf,
                  origin=origin, path_length=path_length)
except Exception as exc:  # noqa: BLE001
    banner.error(t("The regression could not be computed: {e}", e=exc))
    st.stop()
an.apply_lod_basis(res, lod_basis, blank_readings)
if res.get("engine_note"):
    banner.warning(res["engine_note"])
eps = molar_absorptivity(res, unit, molar_mass)
verdict, reasons = an.curve_verdict(res, r2_min)
design = an.design_check(res, ACC["min_levels"], ACC["replicates_per_level"])
a_lo, a_hi = ACC["absorbance_range"]

if verdict == "accepted":
    banner.success(t("✅ Calibration curve accepted (R² = {r} ≥ {m}).", r=f"{res['r_squared']:.5f}", m=r2_min))
else:
    banner.error(t("❌ Calibration curve rejected: {r}. Review the standards before quantifying samples.",
                   r="; ".join(reasons)))

with t_stats:
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("R²", f"{res['r_squared']:.5f}")
    m2.metric(t("Slope b"), f"{res['coefficients']['slope']['estimate']:.5g}")
    m3.metric("s(y/x)", f"{res['s_yx']:.3g}")
    m4.metric(f"LOD ({unit})", f"{res['lod']:.3g}")
    m5.metric(f"LOQ ({unit})", f"{res['loq']:.3g}")
    st.markdown(f"**{t('Equation')}:** `{P.equation(res, 6)}`  ·  **{t('Engine')}:** {res['engine']}  ·  "
                f"**{t('σ for LOD/LOQ')}:** {t(lod_key)}"
                + (f"  ·  **{t('Reagent blank')}:** {reagent_blank:.4f}" if reagent_blank else ""))
    if res.get("lod_note"):
        st.warning(res["lod_note"])
    if eps is not None:
        st.markdown(f"**{t('Molar absorptivity ε')}** = {eps:,.0f} L·mol⁻¹·cm⁻¹ "
                    + (t("(at {w} nm, ", w=f"{wavelength:.0f}") if wavelength else "(")
                    + f"l = {path_length} cm)")
    if not design["levels_ok"]:
        st.warning(t("Only {n} concentration levels (≥ {m} recommended).", n=design["levels"], m=ACC["min_levels"]))
    if not design["reps_ok"]:
        st.warning(t("Some levels have {n} replicate(s) (≥ {m} recommended).", n=design["min_reps"],
                     m=ACC["replicates_per_level"]))
    out_range = [y for y in res["points"]["y"] if not (a_lo <= y <= a_hi)]
    if out_range:
        st.info(t("{n} standard(s) outside the working absorbance range {lo}–{hi}.", n=len(out_range), lo=a_lo, hi=a_hi))

    a, b = st.columns([1, 1])
    with a:
        st.subheader(t("Summary"))
        st.dataframe(summary_table(res, unit, eps), hide_index=True, width="stretch")
    with b:
        st.subheader(t("Coefficients"))
        st.dataframe(coefficients_table(res).style.format(precision=6), hide_index=True, width="stretch")
        st.subheader("ANOVA")
        st.dataframe(anova_table(res).style.format(precision=6, na_rep=""), hide_index=True, width="stretch")

    st.subheader(t("Assumption checks"))
    icon = {"ok": "✅", "warn": "⚠️", "bad": "❌", "info": "ℹ️"}
    for e in evaluate(res, r2_min, r2_rec):
        st.markdown(f"{icon[e['status']]} **{e['test']}** — {e['value']}  \n{e['message']}")

    with st.expander(t("Data, residuals and influence")):
        st.dataframe(points_table(res).style.format(precision=5), hide_index=True, width="stretch")

fig_p = P.plotly_calibration(res, xlab, title=title)
fig_d = P.plotly_diagnostics(res, xlab)

with t_plots:
    if lib == "Plotly":
        st.plotly_chart(fig_p, width="stretch")
        st.plotly_chart(fig_d, width="stretch")
    elif lib.startswith("Matplotlib"):
        use_sns = "Seaborn" in lib
        f1 = P.mpl_calibration(res, xlab, title=title, seaborn_style=style, use_seaborn=use_sns)
        f2 = P.mpl_diagnostics(res, xlab, seaborn_style=style, use_seaborn=use_sns)
        st.pyplot(f1)
        st.download_button(t("⬇️ Curve PNG (300 dpi)"), P.fig_to_png(f1), "calibration_curve.png", "image/png")
        st.pyplot(f2)
        st.download_button(t("⬇️ Diagnostics PNG (300 dpi)"), P.fig_to_png(f2), "diagnostics.png", "image/png")
    else:
        st.altair_chart(P.altair_calibration(res, xlab), width="stretch")
        st.altair_chart(P.altair_residuals(res, xlab), width="stretch")

# ----------------------------------------------------------- samples/content
content_df, content_label, tannin_summary, scale = pd.DataFrame(), "", pd.DataFrame(), "mg"
with t_samples:
    tm = samples_table(res, unit)
    if tm.empty:
        st.info(t("Add sample absorbances in the Data tab."))
    else:
        st.markdown(t(r"Concentration by inverse regression: $\hat C_0 = (\bar A_0 - a)/b$, with "
                      r"$s_{C_0} = \frac{s_{y/x}}{b}\sqrt{\frac1m + \frac1n + \frac{(\bar A_0-\bar A)^2}"
                      r"{b^2 S_{xx}}}$ (absorbances blank-corrected)"))
        st.subheader(t("Concentration in the measured solution"))
        st.dataframe(tm.style.format(precision=5, na_rep=""), hide_index=True, width="stretch")
        for msg in sample_warnings(res):
            st.warning(msg)
        if verdict == "rejected":
            st.error(t("The curve was rejected: these results should not be reported."))

        st.subheader(t("Content in the sample"))
        c1, c2 = st.columns(2)
        bases = ["extract", "DW", "FW"]
        basis = c1.selectbox(t("Mass basis"), bases, key=init(f"w_basis_{mid}", "extract" if method.get("group") == "lab" else "DW"),
                             format_func=lambda k: {"extract": t("g of extract"), "DW": t("g dry weight (DW)"),
                                                    "FW": t("g fresh weight (FW)")}[k])
        scale = "mg"
        if an.is_mass_unit(unit):
            scale = c2.radio(t("Result scale"), ["mg", "µg"], horizontal=True, key=init("w_scale", "mg"),
                             format_func=lambda k: f"{k}/g",
                             help=t("Use the same scale for all assays so results can be compared."))
        basis_txt = {"extract": t("g extract"), "DW": t("g DW"), "FW": t("g FW")}[basis]
        content_label = an.content_unit(unit, abbr, basis_txt, scale)   # e.g. "mg GAE/g extract"
        if is_diff:
            st.latex(rf"\text{{{t('Tannins')}}} = TP - RP \cdot DF_{{casein}}")
            rep_t, tannin_summary = an.tannins_by_difference(res, samples, unit, casein_df, reagent_blank, scale)
            if tannin_summary.empty:
                st.info(t("Enter A_TP and A_RP for each replicate in the Data tab."))
            else:
                show = tannin_summary[["sample", "n", "C_TP_mean", "C_RP_mean", "C_tannins_mean",
                                       "tannin_fraction_pct", "TP_content_mean", "RP_content_mean",
                                       "tannins_content_mean", "tannins_content_sd", "tannins_rsd_pct"]]
                content_df = show.rename(columns={
                    "sample": t("Sample"), "n": t("Replicates"),
                    "C_TP_mean": f"TP ({unit})", "C_RP_mean": t("RP × DF ({u})", u=unit),
                    "C_tannins_mean": t("Tannins ({u})", u=unit), "tannin_fraction_pct": t("Tannins / TP (%)"),
                    "TP_content_mean": f"TP ({content_label})", "RP_content_mean": f"RP ({content_label})",
                    "tannins_content_mean": t("Tannins ({u})", u=content_label), "tannins_content_sd": "SD",
                    "tannins_rsd_pct": t("RSD (%)")})
                st.dataframe(content_df.style.format(precision=4, na_rep=""), hide_index=True, width="stretch")
                if content_df.iloc[:, 8].isna().all():
                    st.info(t("Fill `extract_conc_ug_mL` (or `extract_volume_mL` + `mass_g`) to obtain the "
                              "content per gram."))
                if (tannin_summary["C_tannins_mean"] < 0).any():
                    st.warning(t("Negative tannins: RP is larger than TP. Check the casein dilution factor and "
                                 "the readings."))
                with st.expander(t("Replicates")):
                    st.dataframe(rep_t.style.format(precision=4, na_rep=""), hide_index=True, width="stretch")
        else:
            st.latex(rf"\text{{{t('Content')}}} = \frac{{C \cdot DF}}{{C_{{extract}}}}\quad\text{{{t('or')}}}\quad"
                     r"\frac{C \cdot V_{extract} \cdot DF}{m_{sample}}")
            content_df = an.sample_content(res, smp_corr, unit, scale)
            if content_df.empty or content_df["content_mean"].isna().all():
                st.info(t("Fill `extract_conc_ug_mL` (or `extract_volume_mL` + `mass_g`) to obtain the "
                          "content per gram."))
            else:
                conf_pct = int(conf * 100)
                content_df = content_df.rename(columns={
                    "sample": t("Sample"), "n": t("Replicates"), "C_mean": t("C mean ({u})", u=unit),
                    "content_mean": t("Content ({u})", u=content_label), "content_sd": "SD",
                    "content_rsd_pct": t("RSD (%)"), "ci_low": t("Calibration {c}% CI lower", c=conf_pct),
                    "ci_high": t("Calibration {c}% CI upper", c=conf_pct)})
                st.dataframe(content_df.style.format(precision=4, na_rep=""), hide_index=True, width="stretch")
        st.caption(t("Report as mean ± SD (RSD%) of replicates, stating the standard and the mass basis. "
                     "Technical replicates do not replace biological replicates."))

# ------------------------------------------------------- step-by-step tab
with t_steps:
    st.markdown(t("The same calculation the app does, written out as you would do it by hand, with the "
                  "numbers of the selected sample. The result is compared with the statistical engine."))
    if is_diff:
        names = list(dict.fromkeys(samples.dropna(subset=["A_TP", "A_RP"])["sample"].astype(str)))
    else:
        names = list(dict.fromkeys(smp["sample"].astype(str)))
    if not names:
        st.info(t("Add sample absorbances in the Data tab."))
    else:
        if st.session_state.get(f"w_hc_{mid}") not in names:
            st.session_state[f"w_hc_{mid}"] = names[0]
        name = st.selectbox(t("Sample"), names, key=f"w_hc_{mid}")
        by_engine = {u["sample"]: u for u in res["unknowns"]}
        if is_diff:
            rows = samples[samples["sample"].astype(str) == name]
            s_tp = hc.sample_steps(res, rows, reagent_blank, unit, scale, absorbance_col="A_TP")
            show_steps(s_tp, unit, content_label, t("Total polyphenols (TP)"))
            st.divider()
            s_rp = hc.sample_steps(res, rows, reagent_blank, unit, scale, absorbance_col="A_RP",
                                   extra_dilution=casein_df)
            show_steps(s_rp, unit, content_label, t("Residual polyphenols (RP)"))
            st.divider()
            st.markdown(f"**{t('Tannins by difference')}**")
            st.latex(rf"\text{{{t('Tannins')}}} = TP - RP\cdot DF_{{casein}} = {hc.fmt(s_tp['c0'])} - "
                     rf"{hc.fmt(s_rp['c0'])} = {hc.fmt(s_tp['c0'] - s_rp['c0'])}")
            if s_tp["content_mean"] is not None and s_rp["content_mean"] is not None:
                st.markdown(f"➡️ **{s_tp['content_mean'] - s_rp['content_mean']:.5g} {content_label}**")
            checks = [(s_tp, by_engine.get(f"{name} (TP)")), (s_rp, by_engine.get(f"{name} (RP)"))]
        else:
            rows = smp[smp["sample"].astype(str) == name]
            s1 = hc.sample_steps(res, rows, reagent_blank, unit, scale)
            show_steps(s1, unit, content_label)
            checks = [(s1, by_engine.get(name))]
        ok = all(u is not None and np.isclose(sx["c0_raw"], u["x0"], rtol=1e-8) and
                 np.isclose(sx["s_c0"] / sx["extra_dilution"], u["s_x0"], rtol=1e-6) for sx, u in checks)
        if ok:
            st.success(t("✓ The hand calculation gives exactly the same result as the engine ({e}).", e=res["engine"]))
        else:
            st.error(t("The hand calculation differs from the engine result; please report it."))

# --------------------------------------------------------- standard addition
sa = None
with t_add:
    st.markdown(t("Add increasing amounts of standard to equal aliquots of sample. Enter the **final "
                  "concentration of added standard** in the measured solution (same unit as the curve) and "
                  "the absorbance. The sample concentration is the |x-intercept|: $C = a/b$."))
    up = uploader(t("Standard addition data (col. 1: added concentration, col. 2: absorbance)"), f"add_{mid}")
    base_a = source(up, load_csv(demo["addition"]) if demo and "addition" in demo else None,
                    {"added": float, "A": float})
    base_a = base_a.iloc[:, :2].copy()
    base_a.columns = ["added", "absorbance"]
    add_data = table(f"add_{mid}", base_a, use_demo, up, column_config={
        "added": st.column_config.NumberColumn(t("Added concentration"), format="%g"),
        "absorbance": st.column_config.NumberColumn(t("Absorbance"), format="%.4f")})
    df_aliquot = st.number_input(t("Dilution factor of the sample aliquot in the measured solution"),
                                 1.0, 1e6, step=1.0, key=init(f"w_dfaliq_{mid}", 1.0))
    add_corr = an.correct_standards(add_data.dropna(), reagent_blank)
    if len(add_corr.dropna()) >= 3 and add_corr.iloc[:, 0].nunique() >= 2:
        try:
            res_add = compute(add_corr, None, engine=engine, conf=conf)
            sa = an.standard_addition(res_add, res, ACC["standard_addition_slope_diff_pct"])
            c1, c2, c3 = st.columns(3)
            c1.metric(t("C in measured solution ({u})", u=unit), f"{sa['C']:.4g}",
                      help=f"{int(conf * 100)}% CI: {sa['ci_low']:.4g} – {sa['ci_high']:.4g}")
            c2.metric(t("C in original sample ({u})", u=unit), f"{sa['C'] * df_aliquot:.4g}")
            c3.metric(t("Slope difference vs external curve"), f"{sa['slope_diff_pct']:.2f} %")
            st.markdown(t("{c}% CI (measured solution): **{lo} – {hi} {u}** · R² = {r} · s(C) = {s}",
                          c=int(conf * 100), lo=f"{sa['ci_low']:.4g}", hi=f"{sa['ci_high']:.4g}", u=unit,
                          r=f"{sa['r_squared']:.5f}", s=f"{sa['s_C']:.3g}"))
            lim = ACC["standard_addition_slope_diff_pct"]
            if sa["parallel"]:
                st.success(t("Slopes are parallel (difference < {l}%): no significant matrix effect ({s}).",
                             l=lim, s=ACC["standard_addition_source"]))
            else:
                st.warning(t("Slope difference ≥ {l}%: possible matrix effect — quantify by standard "
                             "addition rather than with the external curve.", l=lim))
            st.plotly_chart(P.plotly_standard_addition(res_add, sa, t("Added concentration ({u})", u=unit)),
                            width="stretch")
            st.caption(t(r"Uncertainty: $s_{C} = \frac{s_{y/x}}{b}\sqrt{\frac1n + \frac{\bar y^2}{b^2 S_{xx}}}$ "
                         r"(Miller & Miller). Regression by {e}.").replace("{e}", res_add["engine"]))
        except Exception as exc:  # noqa: BLE001
            st.error(t("Standard addition could not be computed: {e}", e=exc))
    else:
        st.info(t("Enter at least 3 points with 2 different added concentrations."))

# ---------------------------------------------------------------- validation
prec_rows, prec_all, rec_rows, rec_all = pd.DataFrame(), {}, pd.DataFrame(), {}
with t_val:
    st.subheader(t("ICH Q2 checklist"))
    lof = res["diagnostics"].get("lack_of_fit")
    dw = res["diagnostics"]["durbin_watson"]
    checks = [
        (design["levels_ok"], t("Linearity: {n} levels (≥ {m})", n=design["levels"], m=ACC["min_levels"])),
        (design["reps_ok"], t("Replicates per level: min {n} (≥ {m})", n=design["min_reps"],
                              m=ACC["replicates_per_level"])),
        (res["r_squared"] >= r2_min, f"R² = {res['r_squared']:.5f} (≥ {r2_min})"),
        (lof is None or lof["p"] > 0.05, t("Lack of fit not significant") if lof else
         t("Lack of fit: needs replicates")),
        (1.5 <= dw <= 2.5, t("Residuals without trend (Durbin-Watson = {d})", d=f"{dw:.2f}")),
        (True, f"LOD = {res['lod']:.4g} {unit}; LOQ = {res['loq']:.4g} {unit} ({t(lod_key)})"),
    ]
    for ok, text in checks:
        st.markdown(("✅ " if ok else "⚠️ ") + text)

    st.subheader(t("Precision (repeatability / intermediate precision)"))
    rsd_keys = list(ACC["rsd_criteria_pct"])
    crit_rsd = st.selectbox(t("RSD criterion"), rsd_keys, format_func=t, key=init("w_rsd", rsd_keys[1]))
    max_rsd = ACC["rsd_criteria_pct"][crit_rsd]
    st.caption(t("Repeatability: n ≥ 6 at 100% or 9 determinations at 3 levels. Use the `series` column for "
                 "another day / analyst / instrument (intermediate precision)."))
    up = uploader(t("Precision readings (series, absorbance)"), f"prec_{mid}")
    base_p = source(up, load_csv(demo["precision"]) if demo and "precision" in demo else None,
                    {"series": str, "absorbance": float})
    prec = table(f"prec_{mid}", base_p, use_demo, up)
    if "series" in prec and "absorbance" in prec and len(prec.dropna(subset=["absorbance"])):
        p_in = prec.copy()
        p_in["absorbance"] = pd.to_numeric(p_in["absorbance"], errors="coerce") - reagent_blank
        prec_rows, prec_all = an.precision(res, p_in, max_rsd)
        st.dataframe(prec_rows.rename(columns={"series": t("Series"), "mean_C": t("Mean C ({u})", u=unit),
                                               "sd": "SD", "rsd_pct": t("RSD (%)"), "pass": t("Pass")})
                     .style.format(precision=4, na_rep=""), hide_index=True, width="stretch")
        msg = t("Overall: n = {n}, mean = {m} {u}, RSD = {r}% (criterion ≤ {c}%)", n=prec_all["n"],
                m=f"{prec_all['mean_C']:.4g}", u=unit, r=f"{prec_all['rsd_pct']:.2f}", c=max_rsd)
        (st.success if prec_all["pass"] else st.error)(msg)
        if not prec_all["enough_n"]:
            st.warning(t("Fewer than 6 determinations."))

    st.subheader(t("Accuracy (recovery)"))
    rec_keys = list(ACC["recovery_criteria_pct"])
    crit_rec = st.selectbox(t("Recovery criterion"), rec_keys, format_func=t, key=init("w_rec", rec_keys[0]))
    lims = tuple(ACC["recovery_criteria_pct"][crit_rec])
    st.latex(rf"\text{{{t('Recovery')}}}\,\% = 100\cdot\frac{{C_{{spiked}}-C_{{unspiked}}}}{{C_{{added}}}}")
    up = uploader(t("Recovery data (level, A_unspiked, A_spiked, C_added)"), f"rec_{mid}")
    base_r = source(up, load_csv(demo["recovery"]) if demo and "recovery" in demo else None,
                    {"level": str, "A_unspiked": float, "A_spiked": float, "C_added": float})
    rec = table(f"rec_{mid}", base_r, use_demo, up)
    if {"A_unspiked", "A_spiked", "C_added"} <= set(rec.columns) and len(rec.dropna()):
        r_in = rec.copy()
        for c in ("A_unspiked", "A_spiked"):
            r_in[c] = pd.to_numeric(r_in[c], errors="coerce") - reagent_blank
        rec_rows, rec_all = an.recovery(res, r_in, lims)
        if not rec_rows.empty:
            st.dataframe(rec_all["per_level"].rename(columns={"level": t("Level"), "count": "n",
                                                              "mean": t("Mean recovery (%)"), "std": "SD",
                                                              "pass": t("Pass")})
                         .style.format(precision=2, na_rep=""), hide_index=True, width="stretch")
            msg = t("Mean recovery = {m}% ± {s}% (n = {n}; criterion {lo}–{hi}%)", m=f"{rec_all['mean']:.1f}",
                    s=f"{rec_all['sd']:.1f}", n=rec_all["n"], lo=lims[0], hi=lims[1])
            (st.success if rec_all["pass"] else st.error)(msg)
            st.caption(t(ACC["recovery_source"]))
    st.caption(t("Specificity: see the Standard addition tab. Robustness: repeat the curve varying reaction "
                 "time, reagent concentration, temperature and λ (± 2 nm)."))

# -------------------------------------------------------------------- report
with t_rep:
    meta = {t("Method"): field(method, "name"), t("Variant"): field(variant, "name") if variant else "",
            t("Reference standard"): f"{field(standard, 'name')} ({abbr})" if standard else "",
            t("Analyte"): analyte, t("Wavelength (nm)"): wavelength, t("Path length (cm)"): path_length,
            t("Reagent blank (A)"): reagent_blank if reagent_blank else "",
            t("Casein step dilution factor (RP)"): casein_df if is_diff else "",
            "unit": unit, t("Confidence level"): f"{conf:.0%}",
            t("Model"): t("A = b·C (through the origin)") if origin else "A = a + b·C",
            t("Curve verdict"): t("Accepted") if verdict == "accepted" else t("Rejected") + ": " + "; ".join(reasons)}
    extra = []
    if not content_df.empty:
        extra.append((t("Tannins by difference") if is_diff else t("Content in sample ({u})", u=content_label),
                      df_html(content_df)))
    if sa:
        extra.append((t("Standard addition"), df_html(pd.DataFrame([{
            t("C measured ({u})", u=unit): sa["C"], "s(C)": sa["s_C"], t("CI lower"): sa["ci_low"],
            t("CI upper"): sa["ci_high"], t("C original ({u})", u=unit): sa["C"] * df_aliquot,
            t("Slope (addition)"): sa["slope"], t("Slope (external)"): sa["slope_ext"],
            t("Slope difference (%)"): sa["slope_diff_pct"], t("Parallel"): sa["parallel"]}]))))
    if prec_all:
        extra.append((t("Precision (criterion RSD ≤ {c}%)", c=max_rsd), df_html(prec_rows)))
    if rec_all:
        extra.append((t("Recovery (criterion {lo}–{hi}%)", lo=lims[0], hi=lims[1]), df_html(rec_all["per_level"])))
    if method.get("references"):
        extra.append((t("Method references"), "<ul>" + "".join(
            f"<li>{M.reference_text(r)}</li>" for r in method["references"]) + "</ul>"))
    report = html_report(res, meta, fig_p, fig_d, eps, extra, r2_min, r2_rec)
    c1, c2, c3 = st.columns(3)
    c1.download_button(t("⬇️ HTML report"), report, "calibration_report.html", "text/html")
    c2.download_button(t("⬇️ Results JSON"), json.dumps(res, indent=2, ensure_ascii=False, default=str),
                       "results.json", "application/json")
    c3.download_button(t("⬇️ Residuals CSV"), points_table(res).to_csv(index=False), "residuals.csv", "text/csv")
    st.caption(t("The HTML report includes tables, interpretation, method references and interactive plots; "
                 "it can be printed to PDF from the browser."))

with t_conc:
    show_concepts()

with t_meth:
    show_method_tab(method, variant, standard)

with t_ai:
    show_ai_tab()
