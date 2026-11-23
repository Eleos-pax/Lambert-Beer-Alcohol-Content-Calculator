"""Plain-language interpretation of the calibration statistics.

The criteria are indicative (ICH Q2(R2), Eurachem, Miller & Miller). Each
laboratory must apply the acceptance criteria of its own method.
"""

from __future__ import annotations

from .i18n import t

ALPHA = 0.05


def _fmt_p(p):
    if p is None:
        return "n/a"
    return "< 0.0001" if p < 1e-4 else f"{p:.4f}"


def evaluate(res: dict, r2_min: float = 0.99, r2_rec: float = 0.995) -> list[dict]:
    """Return a list of {test, value, status, message}. status: ok|warn|bad|info."""
    out = []
    d = res["diagnostics"]
    pts = res["points"]

    r2 = res["r_squared"]
    msg = (t("Excellent linearity (≥ {v}).", v=r2_rec) if r2 >= r2_rec else
           t("Acceptable linearity (≥ {v}), check the residuals.", v=r2_min) if r2 >= r2_min else
           t("Poor linearity: check standards, range or deviations from Beer-Lambert."))
    msg += " " + t("A high R² alone does NOT prove linearity: look at the residuals.")
    if res["origin"]:
        msg += " " + t("(With the intercept forced to 0, R² is uncentered and tends to be inflated.)")
    out.append({"test": t("Coefficient of determination R²"), "value": f"{r2:.5f}",
                "status": "ok" if r2 >= r2_rec else ("warn" if r2 >= r2_min else "bad"),
                "message": msg})

    inter = res["coefficients"]["intercept"]
    if inter is not None:
        p = inter["p"]
        out.append({
            "test": t("Intercept = 0 (t test)"), "value": f"p = {_fmt_p(p)}",
            "status": "ok" if p > ALPHA else "warn",
            "message": t("The intercept is not significantly different from zero: no evidence of "
                         "constant bias (blank).") if p > ALPHA else
                       t("The intercept is significant: possible blank absorbance, interferences or "
                         "constant systematic error. Do not force through the origin.")})

    sp = d.get("shapiro_p")
    if sp is not None:
        out.append({
            "test": t("Normality of residuals (Shapiro-Wilk)"),
            "value": f"W = {d['shapiro_w']:.4f}; p = {_fmt_p(sp)}",
            "status": "ok" if sp > ALPHA else "warn",
            "message": t("Residuals are consistent with a normal distribution.") if sp > ALPHA else
                       t("Non-normal residuals: confidence intervals may be unreliable.")})

    bp = d.get("bp_p")
    if bp is not None:
        out.append({
            "test": t("Homoscedasticity (Breusch-Pagan)"),
            "value": f"BP = {d['bp_stat']:.3f}; p = {_fmt_p(bp)}",
            "status": "ok" if bp > ALPHA else "warn",
            "message": t("Constant variance across the range.") if bp > ALPHA else
                       t("Non-constant variance (heteroscedasticity): consider weighted regression.")})

    dw = d["durbin_watson"]
    out.append({
        "test": t("Independence (Durbin-Watson)"), "value": f"DW = {dw:.3f}",
        "status": "ok" if 1.5 <= dw <= 2.5 else "warn",
        "message": t("No apparent autocorrelation (DW ≈ 2).") if 1.5 <= dw <= 2.5 else
                   t("Possible autocorrelation: instrument drift or measurement order?")})

    lof = d.get("lack_of_fit")
    if lof is not None:
        out.append({
            "test": t("Lack of fit (ANOVA with replicates)"),
            "value": f"F = {lof['f']:.3f}; p = {_fmt_p(lof['p'])}",
            "status": "ok" if lof["p"] > ALPHA else "bad",
            "message": t("The linear model is adequate.") if lof["p"] > ALPHA else
                       t("Significant lack of fit: the relationship is not linear in this range.")})
    else:
        out.append({"test": t("Lack of fit"), "value": "n/a", "status": "info",
                    "message": t("Measure replicates of each standard to evaluate lack of fit.")})

    n = res["n"]
    outl = [i + 1 for i, v in enumerate(pts["std_residuals"]) if v is not None and abs(v) > 2.5]
    infl = [i + 1 for i, v in enumerate(pts["cooks"]) if v is not None and v > 4 / n]
    out.append({
        "test": t("Outliers / influential points"),
        "value": t("{a} outliers, {b} influential", a=len(outl), b=len(infl)),
        "status": "ok" if not outl and not infl else "warn",
        "message": t("No point with |standardized residual| > 2.5 or Cook > 4/n.")
        if not outl and not infl else
        t("Outliers (row): {a}; influential (Cook > 4/n): {b}. Review them, but do not remove them "
          "without a justified experimental cause.", a=outl or "-", b=infl or "-")})

    amax = max(pts["y"])
    if amax > 1.5:
        out.append({"test": t("Absorbance range"), "value": f"max A = {amax:.3f}",
                    "status": "warn",
                    "message": t("Absorbances > 1.5 often deviate from Beer-Lambert (stray light, "
                                 "detector non-linearity). Dilute.")})
    return out


def sample_warnings(res: dict) -> list[str]:
    msgs = []
    for u in res["unknowns"]:
        if u["x0"] > res["x_max"]:
            msgs.append(t("'{s}' is above the highest standard (extrapolation): dilute it and multiply "
                          "the result by the dilution factor.", s=u["sample"]))
        elif u["extrapolated"]:
            msgs.append(t("'{s}' is below the lowest standard (extrapolation): concentrate it or "
                          "extend the curve downwards.", s=u["sample"]))
        elif u["below_lod"]:
            msgs.append(t("'{s}' is below the LOD: report as < LOD.", s=u["sample"]))
        elif u["below_loq"]:
            msgs.append(t("'{s}' is between LOD and LOQ: detectable but not quantifiable with the "
                          "required precision.", s=u["sample"]))
    return msgs
