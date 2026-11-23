"""Step-by-step ("by hand") calculation of one sample, from the regression results.

It recomputes every intermediate value explicitly (blank correction, mean, inverse
regression, uncertainty, confidence interval and content) so the user can follow
the formulas with their own numbers, and so it can be compared with the engine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .analysis import content_from_c, intercept, slope


def curve_constants(res: dict) -> dict:
    x = np.asarray(res["points"]["x"], float)
    return {"a": intercept(res), "b": slope(res), "n": res["n"], "y_mean": res["y_mean"],
            "x_mean": res["x_mean"], "sxx": res["sxx"], "sx2": float(np.sum(x ** 2)),
            "s": res["s_yx"], "t": res["t_crit"], "df": res["df_resid"], "conf": res["conf_level"],
            "origin": res["origin"], "x_min": res["x_min"], "x_max": res["x_max"],
            "lod": res["lod"], "loq": res["loq"]}


def sample_steps(res: dict, rows: pd.DataFrame, reagent_blank: float = 0.0,
                 conc_unit: str = "µg/mL", scale: str = "mg", absorbance_col: str = "absorbance",
                 extra_dilution: float = 1.0) -> dict:
    """Every intermediate value for one sample (rows = its replicates, raw absorbances).

    extra_dilution multiplies C (used for RP in the casein method).
    """
    k = curve_constants(res)
    a, b = k["a"], k["b"]
    r = rows.copy()
    A = pd.to_numeric(r[absorbance_col], errors="coerce")
    sb = pd.to_numeric(r["sample_blank"], errors="coerce").fillna(0.0) if "sample_blank" in r \
        else pd.Series(0.0, index=r.index)
    keep = A.notna()
    r, A, sb = r[keep], A[keep], sb[keep]
    A_corr = A - reagent_blank - sb
    m = int(len(A_corr))
    y0 = float(A_corr.mean())
    c0 = (y0 - a) / b
    if k["origin"]:
        inside = 1 / m + y0 ** 2 / (b ** 2 * k["sx2"])
    else:
        inside = 1 / m + 1 / k["n"] + (y0 - k["y_mean"]) ** 2 / (b ** 2 * k["sxx"])
    s_c0 = k["s"] / abs(b) * np.sqrt(inside)
    c_i = (A_corr - a) / b * extra_dilution
    content_i = content_from_c(c_i, r, conc_unit, scale)
    reps = pd.DataFrame({"A": A.to_numpy(), "sample_blank": sb.to_numpy(), "A_corr": A_corr.to_numpy(),
                         "C": c_i.to_numpy(), "content": content_i.to_numpy()})
    for col in ("extract_conc_ug_mL", "extract_volume_mL", "dilution_factor", "mass_g"):
        reps[col] = pd.to_numeric(r[col], errors="coerce").to_numpy() if col in r else np.nan
    cont = reps["content"].dropna()
    return {
        "k": k, "m": m, "reagent_blank": reagent_blank, "reps": reps, "y0": y0,
        "c0": c0 * extra_dilution, "c0_raw": c0, "s_c0": s_c0 * extra_dilution, "inside": inside,
        "ci_low": (c0 - k["t"] * s_c0) * extra_dilution, "ci_high": (c0 + k["t"] * s_c0) * extra_dilution,
        "extra_dilution": extra_dilution,
        "in_range": bool(k["x_min"] <= c0 <= k["x_max"]), "above_loq": bool(c0 >= k["loq"]),
        "above_lod": bool(c0 >= k["lod"]),
        "content_mean": float(cont.mean()) if len(cont) else None,
        "content_sd": float(cont.std(ddof=1)) if len(cont) > 1 else None,
    }


def fmt(v, d: int = 5) -> str:
    """Number for LaTeX; negative numbers in parentheses so substitutions read correctly."""
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return r"\text{n/a}"
    s = f"{v:.{d}g}"
    if "e" in s:
        mant, exp = s.split("e")
        s = rf"{mant}\times10^{{{int(exp)}}}"
    return f"({s})" if v < 0 else s
