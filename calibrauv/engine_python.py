"""Fallback statistical engine in Python (NumPy/SciPy).

Reproduces exactly the same formulas as r/calibration.R. It is used:
  * when R is not installed, and
  * as a cross-check (the tests compare both engines).
"""

from __future__ import annotations

import platform

import numpy as np
import pandas as pd
from scipy import stats


def _coef(est, se, df, tval):
    t = est / se
    return {"estimate": est, "se": se, "t": t,
            "p": 2 * stats.t.sf(abs(t), df),
            "ci_low": est - tval * se, "ci_high": est + tval * se}


def compute_python(standards: pd.DataFrame, samples: pd.DataFrame | None = None,
                   conf: float = 0.95, origin: bool = False, path_length: float = 1.0,
                   n_grid: int = 100) -> dict:
    data = standards.iloc[:, :2].apply(pd.to_numeric, errors="coerce").dropna()
    x = data.iloc[:, 0].to_numpy(float)
    y = data.iloc[:, 1].to_numpy(float)
    n = len(x)
    if n < 3:
        raise ValueError("At least 3 valid standards are required")
    if len(np.unique(x)) < 2:
        raise ValueError("At least 2 different concentrations are required")

    p = 1 if origin else 2
    df_res = n - p
    if df_res < 1:
        raise ValueError("Not enough degrees of freedom: add more standards")
    x_mean, y_mean = x.mean(), y.mean()
    sxx = np.sum((x - x_mean) ** 2)
    sx2 = np.sum(x ** 2)
    tval = stats.t.ppf(1 - (1 - conf) / 2, df_res)

    if origin:
        b = np.sum(x * y) / sx2
        a = 0.0
    else:
        b = np.sum((x - x_mean) * (y - y_mean)) / sxx
        a = y_mean - b * x_mean
    fitted = a + b * x
    e = y - fitted
    ss_res = np.sum(e ** 2)
    s_yx = np.sqrt(ss_res / df_res)

    if origin:
        se_b = s_yx / np.sqrt(sx2)
        ss_tot = np.sum(y ** 2)              # uncentered R² (same as R)
        lev = x ** 2 / sx2
        intercept = None
    else:
        se_b = s_yx / np.sqrt(sxx)
        se_a = s_yx * np.sqrt(sx2 / (n * sxx))
        ss_tot = np.sum((y - y_mean) ** 2)
        lev = 1 / n + (x - x_mean) ** 2 / sxx
        intercept = _coef(a, se_a, df_res, tval)

    ss_reg = ss_tot - ss_res
    r2 = 1 - ss_res / ss_tot
    df_tot = n if origin else n - 1
    r2_adj = 1 - (1 - r2) * df_tot / df_res
    f_stat = (ss_reg / 1) / (ss_res / df_res)
    f_p = stats.f.sf(f_stat, 1, df_res)

    std_res = e / (s_yx * np.sqrt(1 - lev))
    cooks = std_res ** 2 * lev / (p * (1 - lev))

    # Diagnostics
    try:
        sw = stats.shapiro(e)
        sh_w, sh_p = float(sw.statistic), float(sw.pvalue)
    except Exception:  # noqa: BLE001
        sh_w = sh_p = None
    dw = np.sum(np.diff(e) ** 2) / ss_res
    e2 = e ** 2
    r_aux = np.corrcoef(x, e2)[0, 1] if np.std(e2) > 0 else 0.0
    bp_stat = n * r_aux ** 2
    bp_p = stats.chi2.sf(bp_stat, 1)

    lof = None
    groups = pd.Series(y).groupby(x)
    k = groups.ngroups
    df_pe, df_lof = n - k, k - p
    if df_pe > 0 and df_lof > 0:
        ss_pe = float(groups.apply(lambda g: np.sum((g - g.mean()) ** 2)).sum())
        ss_lof = ss_res - ss_pe
        f_lof = (ss_lof / df_lof) / (ss_pe / df_pe)
        lof = {"ss_lof": ss_lof, "df_lof": df_lof, "ss_pe": ss_pe, "df_pe": df_pe,
               "f": f_lof, "p": stats.f.sf(f_lof, df_lof, df_pe)}

    # Confidence and prediction bands
    gx = np.linspace(min(0.0, x.min()), x.max() * 1.05, n_grid)
    gfit = a + b * gx
    if origin:
        h = gx ** 2 / sx2
    else:
        h = 1 / n + (gx - x_mean) ** 2 / sxx
    hc = tval * s_yx * np.sqrt(h)
    hp = tval * s_yx * np.sqrt(1 + h)

    lod, loq = 3.3 * s_yx / b, 10 * s_yx / b

    unknowns = []
    if samples is not None and len(samples) > 0:
        mu = samples.copy()
        mu["absorbance"] = pd.to_numeric(mu["absorbance"], errors="coerce")
        mu = mu.dropna(subset=["absorbance"])
        for name, g in mu.groupby("sample", sort=False):
            yy = g["absorbance"].to_numpy(float)
            m = len(yy)
            y0 = yy.mean()
            x0 = (y0 - a) / b
            if origin:
                sx0 = s_yx / abs(b) * np.sqrt(1 / m + y0 ** 2 / (b ** 2 * sx2))
            else:
                sx0 = s_yx / abs(b) * np.sqrt(1 / m + 1 / n + (y0 - y_mean) ** 2 / (b ** 2 * sxx))
            unknowns.append({
                "sample": str(name), "m": m, "y_mean": y0,
                "y_sd": float(np.std(yy, ddof=1)) if m > 1 else None,
                "x0": x0, "s_x0": sx0, "ci_low": x0 - tval * sx0, "ci_high": x0 + tval * sx0,
                "rsd_pct": 100 * sx0 / abs(x0) if x0 != 0 else None,
                "extrapolated": bool(x0 < x.min() or x0 > x.max()),
                "below_lod": bool(x0 < lod), "below_loq": bool(x0 < loq)})

    def lst(v):
        return [float(t) for t in v]

    return {
        "engine": f"Python {platform.python_version()} (NumPy/SciPy)",
        "n": n, "p": p, "df_resid": df_res, "conf_level": conf, "origin": origin,
        "t_crit": tval,
        "coefficients": {"slope": _coef(b, se_b, df_res, tval), "intercept": intercept},
        "r": float(np.corrcoef(x, y)[0, 1]), "r_squared": r2, "adj_r_squared": r2_adj,
        "s_yx": s_yx, "f_stat": f_stat, "f_p": f_p,
        "anova": {"df_reg": 1, "ss_reg": ss_reg, "ms_reg": ss_reg,
                  "df_res": df_res, "ss_res": ss_res, "ms_res": ss_res / df_res,
                  "f": f_stat, "p": f_p},
        "lod": lod, "loq": loq, "path_length": path_length,
        "absorptivity": b / path_length, "slope_rsd_pct": 100 * se_b / abs(b),
        "x_mean": x_mean, "y_mean": y_mean, "sxx": sxx,
        "x_min": float(x.min()), "x_max": float(x.max()),
        "diagnostics": {"shapiro_w": sh_w, "shapiro_p": sh_p, "durbin_watson": dw,
                        "bp_stat": bp_stat, "bp_p": bp_p, "lack_of_fit": lof},
        "points": {"x": lst(x), "y": lst(y), "fitted": lst(fitted), "residuals": lst(e),
                   "std_residuals": lst(std_res), "leverage": lst(lev), "cooks": lst(cooks)},
        "band": {"x": lst(gx), "fit": lst(gfit),
                 "conf_low": lst(gfit - hc), "conf_high": lst(gfit + hc),
                 "pred_low": lst(gfit - hp), "pred_high": lst(gfit + hp)},
        "unknowns": unknowns,
    }
