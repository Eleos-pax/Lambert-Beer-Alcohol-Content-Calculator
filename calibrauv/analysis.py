"""Analytical calculations built on the regression results.

The regression itself (slope, intercept, s(y/x), bands...) always comes from
the statistical engine (R or Python). This module only applies arithmetic on
top of it: blank correction, LOD/LOQ basis, content in the sample, standard
addition, and ICH Q2 validation figures (precision, recovery).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .i18n import t

# ------------------------------------------------------------ unit handling
# Amount factor: (concentration unit × L) → (mg) for mass units, (µmol) for molar units
_AMOUNT = {
    "mg/L (ppm)": (1.0, "mg"), "µg/mL": (1.0, "mg"), "µg/L (ppb)": (1e-3, "mg"),
    "g/L": (1e3, "mg"),
    "mol/L": (1e6, "µmol"), "mmol/L": (1e3, "µmol"), "µmol/L": (1.0, "µmol"),
}


SCALES = {"mg": 1.0, "µg": 1e3}   # only for mass-based units


def is_mass_unit(conc_unit: str) -> bool:
    return _AMOUNT[conc_unit][1] == "mg"


def content_unit(conc_unit: str, standard_abbr: str | None = None, basis: str = "g",
                 scale: str = "mg") -> str:
    _, amt = _AMOUNT[conc_unit]
    if amt == "mg":
        amt = scale
    return f"{amt} {standard_abbr}/{basis}" if standard_abbr else f"{amt}/{basis}"


def content_from_c(c, rows: pd.DataFrame, conc_unit: str, scale: str = "mg") -> pd.Series:
    """Content per gram from a concentration C (curve units) for each row.

    Two ways (the first available is used, per row):
      * extract_conc_ug_mL given: Content = C · DF / C_extract  (extract dissolved at a known
        concentration, e.g. 50 µg/mL) → mg/g = C(mg/L) · DF / C_extract(mg/L) · 1000
      * extract_volume_mL and mass_g: Content = C · V · DF / m
    """
    factor, amt = _AMOUNT[conc_unit]
    if amt == "mg":
        factor *= SCALES[scale]
    num = lambda col: pd.to_numeric(rows[col], errors="coerce") if col in rows else \
        pd.Series(np.nan, index=rows.index)
    df_ = num("dilution_factor").fillna(1.0)
    c = pd.Series(np.asarray(c, float), index=rows.index)
    by_conc = c * factor * df_ / num("extract_conc_ug_mL") * 1000
    by_mass = c * factor * (num("extract_volume_mL") / 1000) * df_ / num("mass_g")
    return by_conc.where(by_conc.notna(), by_mass)


def intercept(res: dict) -> float:
    c = res["coefficients"]["intercept"]
    return 0.0 if c is None else c["estimate"]


def slope(res: dict) -> float:
    return res["coefficients"]["slope"]["estimate"]


def inverse_predict(res: dict, absorbance) -> np.ndarray:
    """C = (A − a) / b for corrected absorbances."""
    return (np.asarray(absorbance, float) - intercept(res)) / slope(res)


# ------------------------------------------------------------ blank correction
def correct_standards(standards: pd.DataFrame, reagent_blank: float) -> pd.DataFrame:
    out = standards.iloc[:, :2].copy()
    out.iloc[:, 1] = pd.to_numeric(out.iloc[:, 1], errors="coerce") - reagent_blank
    return out


def correct_samples(samples: pd.DataFrame, reagent_blank: float) -> pd.DataFrame:
    """A_corr = A − reagent blank − sample blank (for coloured extracts)."""
    s = samples.copy()
    s["absorbance"] = pd.to_numeric(s["absorbance"], errors="coerce")
    sb = pd.to_numeric(s["sample_blank"], errors="coerce").fillna(0.0) \
        if "sample_blank" in s else 0.0
    s["absorbance_raw"] = s["absorbance"]
    s["absorbance"] = s["absorbance"] - reagent_blank - sb
    return s


# --------------------------------------------------------------- LOD basis
LOD_BASES = {
    "s(y/x) – residual SD": "syx",
    "s(a) – SD of the intercept": "sa",
    "SD of ≥ 10 blanks": "blanks",
}


def apply_lod_basis(res: dict, basis: str, blank_readings=None) -> dict:
    """LOD = 3.3·σ/b, LOQ = 10·σ/b (ICH Q2) with the chosen σ. Updates sample flags."""
    b = slope(res)
    note = None
    if basis == "sa":
        inter = res["coefficients"]["intercept"]
        if inter is None:
            sigma, basis, note = res["s_yx"], "syx", t("No intercept (model through origin): s(y/x) used.")
        else:
            sigma = inter["se"]
    elif basis == "blanks":
        vals = pd.to_numeric(pd.Series(blank_readings if blank_readings is not None else []),
                             errors="coerce").dropna().to_numpy()
        if len(vals) < 2:
            sigma, basis, note = res["s_yx"], "syx", t("Fewer than 2 blank readings: s(y/x) used.")
        else:
            sigma = float(np.std(vals, ddof=1))
            if len(vals) < 10:
                note = t("Only {n} blank readings; ICH Q2 suggests at least 10.", n=len(vals))
    else:
        sigma, basis = res["s_yx"], "syx"
    res["lod_sigma"], res["lod_basis"], res["lod_note"] = sigma, basis, note
    res["lod"], res["loq"] = 3.3 * sigma / b, 10 * sigma / b
    for u in res["unknowns"]:
        u["below_lod"] = bool(u["x0"] < res["lod"])
        u["below_loq"] = bool(u["x0"] < res["loq"])
    return res


# ------------------------------------------------------- content in sample
def sample_content(res: dict, samples_corr: pd.DataFrame, conc_unit: str,
                   scale: str = "mg") -> pd.DataFrame:
    """Content per replicate (see content_from_c), then mean ± SD and RSD% per sample.

    The calibration CI is scaled by the same factor when all replicates of a sample share
    the same dilution and extract data.
    """
    if samples_corr is None or samples_corr.empty:
        return pd.DataFrame()
    s = samples_corr.dropna(subset=["absorbance"]).copy()
    s["C"] = inverse_predict(res, s["absorbance"])
    s["content"] = content_from_c(s["C"], s, conc_unit, scale)
    rows = []
    by_name = {u["sample"]: u for u in res["unknowns"]}
    tq = res["t_crit"]
    cols = [c for c in ("extract_conc_ug_mL", "extract_volume_mL", "dilution_factor", "mass_g") if c in s]
    for name, g in s.groupby("sample", sort=False):
        cont = g["content"].dropna()
        n = len(cont)
        mean = cont.mean() if n else np.nan
        sd = cont.std(ddof=1) if n > 1 else np.nan
        row = {"sample": name, "n": n, "C_mean": g["C"].mean(),
               "content_mean": mean, "content_sd": sd,
               "content_rsd_pct": 100 * sd / abs(mean) if n > 1 and mean else np.nan,
               "ci_low": np.nan, "ci_high": np.nan}
        same = all(g[c].nunique(dropna=False) == 1 for c in cols)
        u = by_name.get(str(name))
        if same and n and u is not None and u["x0"]:
            k = float(content_from_c([1.0], g.iloc[[0]], conc_unit, scale).iloc[0])
            row["ci_low"], row["ci_high"] = (u["x0"] - tq * u["s_x0"]) * k, (u["x0"] + tq * u["s_x0"]) * k
        rows.append(row)
    return pd.DataFrame(rows)


def tannins_by_difference(res: dict, data: pd.DataFrame, conc_unit: str, casein_df: float = 3.0,
                          reagent_blank: float = 0.0, scale: str = "mg") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tannins = TP − RP (casein precipitation, Folin-Ciocalteu by difference).

    data columns (one row per replicate): sample, A_TP, A_RP, and optionally sample_blank,
    extract_conc_ug_mL, extract_volume_mL, dilution_factor, mass_g.
    RP is read in the casein supernatant, so it is multiplied by casein_df before subtracting.
    Returns (per replicate, per sample summary).
    """
    d = data.copy()
    for c in ("A_TP", "A_RP", "sample_blank"):
        d[c] = pd.to_numeric(d[c], errors="coerce") if c in d else np.nan
    d = d.dropna(subset=["A_TP", "A_RP"])
    if d.empty:
        return pd.DataFrame(), pd.DataFrame()
    sb = d["sample_blank"].fillna(0.0)
    d["C_TP"] = inverse_predict(res, d["A_TP"] - reagent_blank - sb)
    d["C_RP"] = inverse_predict(res, d["A_RP"] - reagent_blank - sb) * casein_df
    d["C_tannins"] = d["C_TP"] - d["C_RP"]
    d["TP_content"] = content_from_c(d["C_TP"], d, conc_unit, scale)
    d["RP_content"] = content_from_c(d["C_RP"], d, conc_unit, scale)
    d["tannins_content"] = content_from_c(d["C_tannins"], d, conc_unit, scale)

    def summ(g):
        out = {"n": len(g)}
        for col in ("C_TP", "C_RP", "C_tannins", "TP_content", "RP_content", "tannins_content"):
            v = g[col].dropna()
            out[f"{col}_mean"] = v.mean() if len(v) else np.nan
            out[f"{col}_sd"] = v.std(ddof=1) if len(v) > 1 else np.nan
        m, sd = out["tannins_content_mean"], out["tannins_content_sd"]
        out["tannins_rsd_pct"] = 100 * sd / abs(m) if m == m and sd == sd and m else np.nan
        out["tannin_fraction_pct"] = 100 * out["C_tannins_mean"] / out["C_TP_mean"] \
            if out["C_TP_mean"] else np.nan
        return pd.Series(out)

    value_cols = [c for c in d.columns if c != "sample"]
    summary = d.groupby("sample", sort=False)[value_cols].apply(summ).reset_index()
    summary["n"] = summary["n"].astype(int)
    return d, summary


# --------------------------------------------------------- standard addition
def standard_addition(res_add: dict, res_ext: dict | None = None,
                      max_slope_diff_pct: float = 3.0) -> dict:
    """Analyte concentration by standard addition: C = a / b (|x-intercept|).

    Uncertainty (Miller & Miller): s_xE = (s_y/x / b)·√(1/n + ȳ² / (b²·Sxx)).
    Specificity: slope of the addition line vs slope of the external curve.
    """
    a, b = intercept(res_add), slope(res_add)
    n, s, ybar, sxx, t = (res_add["n"], res_add["s_yx"], res_add["y_mean"],
                          res_add["sxx"], res_add["t_crit"])
    c = a / b
    s_c = (s / abs(b)) * np.sqrt(1 / n + ybar ** 2 / (b ** 2 * sxx))
    out = {"C": c, "s_C": s_c, "ci_low": c - t * s_c, "ci_high": c + t * s_c,
           "slope": b, "intercept": a, "r_squared": res_add["r_squared"], "n": n,
           "slope_ext": None, "slope_diff_pct": None, "parallel": None}
    if res_ext is not None:
        b_ext = slope(res_ext)
        diff = 100 * abs(b - b_ext) / abs(b_ext)
        out.update(slope_ext=b_ext, slope_diff_pct=diff, parallel=bool(diff < max_slope_diff_pct))
    return out


# ---------------------------------------------------------------- validation
def precision(res: dict, data: pd.DataFrame, max_rsd_pct: float) -> tuple[pd.DataFrame, dict]:
    """Repeatability per series (day/analyst) and overall (intermediate precision).

    data columns: series, absorbance (already blank-corrected).
    """
    d = data.copy()
    d["absorbance"] = pd.to_numeric(d["absorbance"], errors="coerce")
    d = d.dropna(subset=["absorbance"])
    if d.empty:
        return pd.DataFrame(), {}
    d["series"] = d["series"].fillna("Series 1").astype(str)
    d["C"] = inverse_predict(res, d["absorbance"])

    def summ(c):
        n = len(c)
        m, sd = c.mean(), (c.std(ddof=1) if n > 1 else np.nan)
        rsd = 100 * sd / abs(m) if n > 1 and m else np.nan
        return n, m, sd, rsd

    rows = []
    for name, g in d.groupby("series", sort=False):
        n, m, sd, rsd = summ(g["C"])
        rows.append({"series": name, "n": n, "mean_C": m, "sd": sd, "rsd_pct": rsd,
                     "pass": bool(rsd <= max_rsd_pct) if rsd == rsd else None})
    n, m, sd, rsd = summ(d["C"])
    overall = {"n": n, "mean_C": m, "sd": sd, "rsd_pct": rsd, "series": d["series"].nunique(),
               "pass": bool(rsd <= max_rsd_pct) if rsd == rsd else None,
               "enough_n": n >= 6}
    return pd.DataFrame(rows), overall


def recovery(res: dict, data: pd.DataFrame, limits: tuple[float, float]) -> tuple[pd.DataFrame, dict]:
    """Recovery % = 100 · (C_spiked − C_unspiked) / C_added.

    data columns: level, A_unspiked, A_spiked, C_added (absorbances blank-corrected).
    """
    d = data.copy()
    for c in ("A_unspiked", "A_spiked", "C_added"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["A_unspiked", "A_spiked", "C_added"])
    if d.empty:
        return pd.DataFrame(), {}
    d["level"] = d["level"].fillna("Level 1").astype(str)
    d["C_unspiked"] = inverse_predict(res, d["A_unspiked"])
    d["C_spiked"] = inverse_predict(res, d["A_spiked"])
    d["recovery_pct"] = 100 * (d["C_spiked"] - d["C_unspiked"]) / d["C_added"]
    lo, hi = limits
    d["pass"] = d["recovery_pct"].between(lo, hi)
    per_level = d.groupby("level", sort=False)["recovery_pct"].agg(["count", "mean", "std"]).reset_index()
    per_level["pass"] = per_level["mean"].between(lo, hi)
    overall = {"mean": d["recovery_pct"].mean(), "sd": d["recovery_pct"].std(ddof=1),
               "n": len(d), "pass": bool(d["recovery_pct"].mean() >= lo and d["recovery_pct"].mean() <= hi)}
    return d, {"per_level": per_level, **overall}


# --------------------------------------------------------- curve acceptance
def design_check(res: dict, min_levels: int, reps: int) -> dict:
    x = pd.Series(res["points"]["x"])
    counts = x.value_counts()
    return {"levels": int(counts.size), "min_reps": int(counts.min()),
            "levels_ok": bool(counts.size >= min_levels), "reps_ok": bool(counts.min() >= reps)}


def curve_verdict(res: dict, r2_min: float, alpha: float = 0.05) -> tuple[str, list[str]]:
    """'accepted' | 'rejected' with reasons (R² below threshold or lack of fit)."""
    reasons = []
    if res["r_squared"] < r2_min:
        reasons.append(f"R² = {res['r_squared']:.4f} < {r2_min}")  # noqa
    lof = res["diagnostics"].get("lack_of_fit")
    if lof is not None and lof["p"] < alpha:
        reasons.append(t("significant lack of fit (p = {p})", p=f"{lof['p']:.4f}"))
    return ("rejected" if reasons else "accepted"), reasons


def t_quantile(conf: float, df: int) -> float:
    return float(stats.t.ppf(1 - (1 - conf) / 2, df))
