"""Motor estadístico de respaldo en Python (NumPy/SciPy).

Reproduce exactamente las mismas fórmulas que r/calibracion.R. Sirve:
  * cuando R no está instalado, y
  * como verificación cruzada (las pruebas comparan ambos motores).
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


def calcular_python(estandares: pd.DataFrame, muestras: pd.DataFrame | None = None,
                    conf: float = 0.95, origen: bool = False, paso_optico: float = 1.0,
                    n_grid: int = 100) -> dict:
    datos = estandares.iloc[:, :2].apply(pd.to_numeric, errors="coerce").dropna()
    x = datos.iloc[:, 0].to_numpy(float)
    y = datos.iloc[:, 1].to_numpy(float)
    n = len(x)
    if n < 3:
        raise ValueError("Se necesitan al menos 3 estándares válidos")
    if len(np.unique(x)) < 2:
        raise ValueError("Se necesitan al menos 2 concentraciones distintas")

    p = 1 if origen else 2
    df_res = n - p
    if df_res < 1:
        raise ValueError("Grados de libertad insuficientes: agregue más estándares")
    x_mean, y_mean = x.mean(), y.mean()
    sxx = np.sum((x - x_mean) ** 2)
    sx2 = np.sum(x ** 2)
    tval = stats.t.ppf(1 - (1 - conf) / 2, df_res)

    if origen:
        b = np.sum(x * y) / sx2
        a = 0.0
    else:
        b = np.sum((x - x_mean) * (y - y_mean)) / sxx
        a = y_mean - b * x_mean
    fitted = a + b * x
    e = y - fitted
    ss_res = np.sum(e ** 2)
    s_yx = np.sqrt(ss_res / df_res)

    if origen:
        se_b = s_yx / np.sqrt(sx2)
        ss_tot = np.sum(y ** 2)              # R²  no centrado (igual que R)
        lev = x ** 2 / sx2
        intercepto = None
    else:
        se_b = s_yx / np.sqrt(sxx)
        se_a = s_yx * np.sqrt(sx2 / (n * sxx))
        ss_tot = np.sum((y - y_mean) ** 2)
        lev = 1 / n + (x - x_mean) ** 2 / sxx
        intercepto = _coef(a, se_a, df_res, tval)

    ss_reg = ss_tot - ss_res
    r2 = 1 - ss_res / ss_tot
    df_tot = n if origen else n - 1
    r2_adj = 1 - (1 - r2) * df_tot / df_res
    f_stat = (ss_reg / 1) / (ss_res / df_res)
    f_p = stats.f.sf(f_stat, 1, df_res)

    std_res = e / (s_yx * np.sqrt(1 - lev))
    cooks = std_res ** 2 * lev / (p * (1 - lev))

    # Diagnósticos
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
    grupos = pd.Series(y).groupby(x)
    k = grupos.ngroups
    df_pe, df_lof = n - k, k - p
    if df_pe > 0 and df_lof > 0:
        ss_pe = float(grupos.apply(lambda g: np.sum((g - g.mean()) ** 2)).sum())
        ss_lof = ss_res - ss_pe
        f_lof = (ss_lof / df_lof) / (ss_pe / df_pe)
        lof = {"ss_lof": ss_lof, "df_lof": df_lof, "ss_pe": ss_pe, "df_pe": df_pe,
               "f": f_lof, "p": stats.f.sf(f_lof, df_lof, df_pe)}

    # Bandas de confianza y predicción
    gx = np.linspace(min(0.0, x.min()), x.max() * 1.05, n_grid)
    gfit = a + b * gx
    if origen:
        h = gx ** 2 / sx2
    else:
        h = 1 / n + (gx - x_mean) ** 2 / sxx
    hc = tval * s_yx * np.sqrt(h)
    hp = tval * s_yx * np.sqrt(1 + h)

    lod, loq = 3.3 * s_yx / b, 10 * s_yx / b

    desconocidas = []
    if muestras is not None and len(muestras) > 0:
        mu = muestras.copy()
        mu["absorbancia"] = pd.to_numeric(mu["absorbancia"], errors="coerce")
        mu = mu.dropna(subset=["absorbancia"])
        for nombre, g in mu.groupby("muestra", sort=False):
            yy = g["absorbancia"].to_numpy(float)
            m = len(yy)
            y0 = yy.mean()
            x0 = (y0 - a) / b
            if origen:
                sx0 = s_yx / abs(b) * np.sqrt(1 / m + y0 ** 2 / (b ** 2 * sx2))
            else:
                sx0 = s_yx / abs(b) * np.sqrt(1 / m + 1 / n + (y0 - y_mean) ** 2 / (b ** 2 * sxx))
            desconocidas.append({
                "sample": str(nombre), "m": m, "y_mean": y0,
                "y_sd": float(np.std(yy, ddof=1)) if m > 1 else None,
                "x0": x0, "s_x0": sx0, "ci_low": x0 - tval * sx0, "ci_high": x0 + tval * sx0,
                "rsd_pct": 100 * sx0 / abs(x0) if x0 != 0 else None,
                "extrapolated": bool(x0 < x.min() or x0 > x.max()),
                "below_lod": bool(x0 < lod), "below_loq": bool(x0 < loq)})

    def lst(v):
        return [float(t) for t in v]

    return {
        "engine": f"Python {platform.python_version()} (NumPy/SciPy)",
        "n": n, "p": p, "df_resid": df_res, "conf_level": conf, "origin": origen,
        "t_crit": tval,
        "coefficients": {"slope": _coef(b, se_b, df_res, tval), "intercept": intercepto},
        "r": float(np.corrcoef(x, y)[0, 1]), "r_squared": r2, "adj_r_squared": r2_adj,
        "s_yx": s_yx, "f_stat": f_stat, "f_p": f_p,
        "anova": {"df_reg": 1, "ss_reg": ss_reg, "ms_reg": ss_reg,
                  "df_res": df_res, "ss_res": ss_res, "ms_res": ss_res / df_res,
                  "f": f_stat, "p": f_p},
        "lod": lod, "loq": loq, "path_length": paso_optico,
        "absorptivity": b / paso_optico, "slope_rsd_pct": 100 * se_b / abs(b),
        "x_mean": x_mean, "y_mean": y_mean, "sxx": sxx,
        "x_min": float(x.min()), "x_max": float(x.max()),
        "diagnostics": {"shapiro_w": sh_w, "shapiro_p": sh_p, "durbin_watson": dw,
                        "bp_stat": bp_stat, "bp_p": bp_p, "lack_of_fit": lof},
        "points": {"x": lst(x), "y": lst(y), "fitted": lst(fitted), "residuals": lst(e),
                   "std_residuals": lst(std_res), "leverage": lst(lev), "cooks": lst(cooks)},
        "band": {"x": lst(gx), "fit": lst(gfit),
                 "conf_low": lst(gfit - hc), "conf_high": lst(gfit + hc),
                 "pred_low": lst(gfit - hp), "pred_high": lst(gfit + hp)},
        "unknowns": desconocidas,
    }
