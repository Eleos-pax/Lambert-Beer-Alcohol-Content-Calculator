"""Plain-language interpretation of the calibration statistics.

The criteria are indicative (ICH Q2(R2), Eurachem, Miller & Miller). Each
laboratory must apply the acceptance criteria of its own method.
"""

from __future__ import annotations

ALPHA = 0.05


def _fmt_p(p):
    if p is None:
        return "n/a"
    return "< 0.0001" if p < 1e-4 else f"{p:.4f}"


def evaluate(res: dict) -> list[dict]:
    """Return a list of {test, value, status, message}. status: ok|warn|bad|info."""
    out = []
    d = res["diagnostics"]
    pts = res["points"]

    r2 = res["r_squared"]
    out.append({
        "test": "Coefficient of determination R²", "value": f"{r2:.5f}",
        "status": "ok" if r2 >= 0.995 else ("warn" if r2 >= 0.99 else "bad"),
        "message": ("Excellent linearity." if r2 >= 0.995 else
                    "Acceptable linearity, check the residuals." if r2 >= 0.99 else
                    "Poor linearity: check standards, range or deviations from Beer-Lambert.")
                   + " A high R² alone does NOT prove linearity: look at the residuals."
                   + (" (With the intercept forced to 0, R² is uncentered and tends to be inflated.)"
                      if res["origin"] else "")})

    inter = res["coefficients"]["intercept"]
    if inter is not None:
        p = inter["p"]
        out.append({
            "test": "Intercept = 0 (t test)", "value": f"p = {_fmt_p(p)}",
            "status": "ok" if p > ALPHA else "warn",
            "message": ("The intercept is not significantly different from zero: "
                        "no evidence of constant bias (blank)." if p > ALPHA else
                        "The intercept is significant: possible blank absorbance, "
                        "interferences or constant systematic error. Do not force through the origin.")})

    sp = d.get("shapiro_p")
    if sp is not None:
        out.append({
            "test": "Normality of residuals (Shapiro-Wilk)",
            "value": f"W = {d['shapiro_w']:.4f}; p = {_fmt_p(sp)}",
            "status": "ok" if sp > ALPHA else "warn",
            "message": "Residuals are consistent with a normal distribution." if sp > ALPHA else
                       "Non-normal residuals: confidence intervals may be unreliable."})

    bp = d.get("bp_p")
    if bp is not None:
        out.append({
            "test": "Homoscedasticity (Breusch-Pagan)",
            "value": f"BP = {d['bp_stat']:.3f}; p = {_fmt_p(bp)}",
            "status": "ok" if bp > ALPHA else "warn",
            "message": "Constant variance across the range." if bp > ALPHA else
                       "Non-constant variance (heteroscedasticity): consider weighted regression."})

    dw = d["durbin_watson"]
    out.append({
        "test": "Independence (Durbin-Watson)", "value": f"DW = {dw:.3f}",
        "status": "ok" if 1.5 <= dw <= 2.5 else "warn",
        "message": "No apparent autocorrelation (DW ≈ 2)." if 1.5 <= dw <= 2.5 else
                   "Possible autocorrelation: instrument drift or measurement order?"})

    lof = d.get("lack_of_fit")
    if lof is not None:
        out.append({
            "test": "Lack of fit (ANOVA with replicates)",
            "value": f"F = {lof['f']:.3f}; p = {_fmt_p(lof['p'])}",
            "status": "ok" if lof["p"] > ALPHA else "bad",
            "message": "The linear model is adequate." if lof["p"] > ALPHA else
                       "Significant lack of fit: the relationship is not linear in this range."})
    else:
        out.append({"test": "Lack of fit", "value": "n/a", "status": "info",
                    "message": "Measure replicates of each standard to evaluate lack of fit."})

    n = res["n"]
    outl = [i + 1 for i, v in enumerate(pts["std_residuals"]) if v is not None and abs(v) > 2.5]
    infl = [i + 1 for i, v in enumerate(pts["cooks"]) if v is not None and v > 4 / n]
    out.append({
        "test": "Outliers / influential points", "value":
            f"{len(outl)} outliers, {len(infl)} influential",
        "status": "ok" if not outl and not infl else "warn",
        "message": ("No point with |standardized residual| > 2.5 or Cook > 4/n."
                    if not outl and not infl else
                    f"Outliers (row): {outl or '-'}; influential (Cook > 4/n): {infl or '-'}. "
                    "Review them, but do not remove them without a justified experimental cause.")})

    amax = max(pts["y"])
    if amax > 1.5:
        out.append({"test": "Absorbance range", "value": f"max A = {amax:.3f}",
                    "status": "warn",
                    "message": "Absorbances > 1.5 often deviate from Beer-Lambert "
                               "(stray light, detector non-linearity). Dilute."})
    return out


def sample_warnings(res: dict) -> list[str]:
    msgs = []
    for u in res["unknowns"]:
        if u["extrapolated"]:
            msgs.append(f"'{u['sample']}' is outside the calibrated range (extrapolation): "
                        "dilute it or extend the curve.")
        elif u["below_lod"]:
            msgs.append(f"'{u['sample']}' is below the LOD: report as < LOD.")
        elif u["below_loq"]:
            msgs.append(f"'{u['sample']}' is between LOD and LOQ: detectable but not quantifiable "
                        "with the required precision.")
    return msgs
