"""Total monomeric anthocyanins by the pH differential method (AOAC 2005.02).

No calibration curve: a known molar absorptivity is used.

    A = (A520 − A700)pH1.0 − (A520 − A700)pH4.5
    C (mg/L) = A · MW · DF · 1000 / (ε · l)

Defaults (cyanidin-3-glucoside): MW = 449.2 g/mol, ε = 26 900 L·mol⁻¹·cm⁻¹.
Reference: Lee J., Durst R.W., Wrolstad R.E. (2005) J AOAC Int 88(5):1269-78.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

COLUMNS = ["sample", "A520_pH1", "A700_pH1", "A520_pH4.5", "A700_pH4.5",
           "dilution_factor", "extract_volume_mL", "mass_g"]


def compute(data: pd.DataFrame, mw: float = 449.2, epsilon: float = 26900.0,
            path_length: float = 1.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (per replicate, per sample summary)."""
    d = data.copy()
    for c in COLUMNS[1:]:
        d[c] = pd.to_numeric(d[c], errors="coerce") if c in d else np.nan
    d["dilution_factor"] = d["dilution_factor"].fillna(1.0)
    d = d.dropna(subset=["A520_pH1", "A700_pH1", "A520_pH4.5", "A700_pH4.5"])
    d["A"] = (d["A520_pH1"] - d["A700_pH1"]) - (d["A520_pH4.5"] - d["A700_pH4.5"])
    d["C_mg_L"] = d["A"] * mw * d["dilution_factor"] * 1000 / (epsilon * path_length)
    d["content_mg_g"] = d["C_mg_L"] * (d["extract_volume_mL"] / 1000) / d["mass_g"]

    def summary(g):
        out = {"n": len(g)}
        for col in ("C_mg_L", "content_mg_g"):
            v = g[col].dropna()
            m = v.mean() if len(v) else np.nan
            sd = v.std(ddof=1) if len(v) > 1 else np.nan
            out[f"{col}_mean"] = m
            out[f"{col}_sd"] = sd
            out[f"{col}_rsd_pct"] = 100 * sd / abs(m) if len(v) > 1 and m else np.nan
        return pd.Series(out)

    summ = d.groupby("sample", sort=False)[["C_mg_L", "content_mg_g"]].apply(summary).reset_index() \
        if not d.empty else pd.DataFrame()
    if not summ.empty:
        summ["n"] = summ["n"].astype(int)
    return d, summ


def warnings(rep: pd.DataFrame, a_range=(0.1, 1.0)) -> list[str]:
    msgs = []
    for _, r in rep.iterrows():
        if r["A"] <= 0:
            msgs.append(f"'{r['sample']}': corrected A ≤ 0 — no monomeric anthocyanins detected "
                        "or a reading error.")
        a1 = r["A520_pH1"]
        if not (a_range[0] <= a1 <= a_range[1]):
            msgs.append(f"'{r['sample']}': A520 at pH 1.0 = {a1:.3f} outside {a_range[0]}–{a_range[1]}; "
                        "adjust the dilution factor.")
    return list(dict.fromkeys(msgs))
