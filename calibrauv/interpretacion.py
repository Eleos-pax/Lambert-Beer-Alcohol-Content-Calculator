"""Interpretación en lenguaje claro de los estadísticos de la calibración.

Los criterios son orientativos (ICH Q2(R2), Eurachem, Miller & Miller). Cada
laboratorio debe aplicar los criterios de aceptación de su propio método.
"""

from __future__ import annotations

ALFA = 0.05


def _fmt_p(p):
    if p is None:
        return "n/d"
    return "< 0.0001" if p < 1e-4 else f"{p:.4f}"


def evaluar(res: dict) -> list[dict]:
    """Devuelve una lista de {prueba, valor, estado, mensaje}. estado: ok|aviso|mal|info."""
    out = []
    d = res["diagnostics"]
    pts = res["points"]

    r2 = res["r_squared"]
    out.append({
        "prueba": "Coeficiente de determinación R²", "valor": f"{r2:.5f}",
        "estado": "ok" if r2 >= 0.995 else ("aviso" if r2 >= 0.99 else "mal"),
        "mensaje": ("Excelente linealidad." if r2 >= 0.995 else
                    "Linealidad aceptable, revise residuales." if r2 >= 0.99 else
                    "Linealidad pobre: revise estándares, rango o desviaciones de Lambert-Beer.")
                   + " R² alto por sí solo NO demuestra linealidad: mire los residuales."
                   + (" (Con intercepto forzado a 0, R² es no centrado y tiende a inflarse.)"
                      if res["origin"] else "")})

    inter = res["coefficients"]["intercept"]
    if inter is not None:
        p = inter["p"]
        out.append({
            "prueba": "Intercepto = 0 (prueba t)", "valor": f"p = {_fmt_p(p)}",
            "estado": "ok" if p > ALFA else "aviso",
            "mensaje": ("El intercepto no difiere significativamente de cero: "
                        "no hay evidencia de sesgo constante (blanco)." if p > ALFA else
                        "El intercepto es significativo: posible absorción del blanco, "
                        "interferencias o error sistemático constante. No fuerce por el origen.")})

    sp = d.get("shapiro_p")
    if sp is not None:
        out.append({
            "prueba": "Normalidad de residuales (Shapiro-Wilk)",
            "valor": f"W = {d['shapiro_w']:.4f}; p = {_fmt_p(sp)}",
            "estado": "ok" if sp > ALFA else "aviso",
            "mensaje": "Residuales compatibles con distribución normal." if sp > ALFA else
                       "Residuales no normales: los intervalos de confianza pueden no ser fiables."})

    bp = d.get("bp_p")
    if bp is not None:
        out.append({
            "prueba": "Homocedasticidad (Breusch-Pagan)",
            "valor": f"BP = {d['bp_stat']:.3f}; p = {_fmt_p(bp)}",
            "estado": "ok" if bp > ALFA else "aviso",
            "mensaje": "Varianza constante en el rango." if bp > ALFA else
                       "Varianza no constante (heterocedasticidad): considere regresión ponderada."})

    dw = d["durbin_watson"]
    out.append({
        "prueba": "Independencia (Durbin-Watson)", "valor": f"DW = {dw:.3f}",
        "estado": "ok" if 1.5 <= dw <= 2.5 else "aviso",
        "mensaje": "Sin autocorrelación aparente (DW ≈ 2)." if 1.5 <= dw <= 2.5 else
                   "Posible autocorrelación: ¿deriva del instrumento u orden de medición?"})

    lof = d.get("lack_of_fit")
    if lof is not None:
        out.append({
            "prueba": "Falta de ajuste (ANOVA con réplicas)",
            "valor": f"F = {lof['f']:.3f}; p = {_fmt_p(lof['p'])}",
            "estado": "ok" if lof["p"] > ALFA else "mal",
            "mensaje": "El modelo lineal es adecuado." if lof["p"] > ALFA else
                       "Falta de ajuste significativa: la relación no es lineal en este rango."})
    else:
        out.append({"prueba": "Falta de ajuste", "valor": "n/d", "estado": "info",
                    "mensaje": "Mida réplicas de cada estándar para evaluar la falta de ajuste."})

    n = res["n"]
    atip = [i + 1 for i, v in enumerate(pts["std_residuals"]) if v is not None and abs(v) > 2.5]
    infl = [i + 1 for i, v in enumerate(pts["cooks"]) if v is not None and v > 4 / n]
    out.append({
        "prueba": "Puntos atípicos / influyentes", "valor":
            f"{len(atip)} atípicos, {len(infl)} influyentes",
        "estado": "ok" if not atip and not infl else "aviso",
        "mensaje": ("Ningún punto con |residual estandarizado| > 2.5 ni Cook > 4/n."
                    if not atip and not infl else
                    f"Atípicos (fila): {atip or '-'}; influyentes (Cook > 4/n): {infl or '-'}. "
                    "Revíselos, pero no los elimine sin una causa experimental justificada.")})

    amax = max(pts["y"])
    if amax > 1.5:
        out.append({"prueba": "Rango de absorbancia", "valor": f"A máx = {amax:.3f}",
                    "estado": "aviso",
                    "mensaje": "Absorbancias > 1.5 suelen desviarse de Lambert-Beer "
                               "(luz parásita, no linealidad del detector). Diluya."})
    return out


def advertencias_muestras(res: dict) -> list[str]:
    msgs = []
    for u in res["unknowns"]:
        if u["extrapolated"]:
            msgs.append(f"«{u['sample']}» está fuera del rango calibrado (extrapolación): "
                        "diluya o amplíe la curva.")
        elif u["below_lod"]:
            msgs.append(f"«{u['sample']}» está por debajo del LOD: reportar como < LOD.")
        elif u["below_loq"]:
            msgs.append(f"«{u['sample']}» está entre LOD y LOQ: detectable pero no cuantificable "
                        "con la precisión requerida.")
    return msgs
