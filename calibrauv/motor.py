"""Selección del motor de cálculo: R (preferido) o Python (respaldo)."""

from __future__ import annotations

import pandas as pd

from .motor_python import calcular_python
from .motor_r import ErrorMotorR, buscar_rscript, calcular_r

# Factores para convertir 1 unidad de concentración a mol/L.
# None = depende de la masa molar (unidades másicas).
UNIDADES = {
    "mol/L": 1.0,
    "mmol/L": 1e-3,
    "µmol/L": 1e-6,
    "mg/L (ppm)": None,   # = µg/mL
    "µg/L (ppb)": None,
    "g/L": None,
}
_MASA_A_G = {"mg/L (ppm)": 1e-3, "µg/L (ppb)": 1e-6, "g/L": 1.0}


def motores_disponibles() -> dict[str, bool]:
    return {"R": buscar_rscript() is not None, "Python": True}


def calcular(estandares: pd.DataFrame, muestras: pd.DataFrame | None = None, *,
             motor: str = "auto", conf: float = 0.95, origen: bool = False,
             paso_optico: float = 1.0, n_grid: int = 100) -> dict:
    """Ajusta la curva de calibración A = a + b·C.

    motor: "auto" (R si está disponible, si no Python), "R" o "Python".
    """
    kwargs = dict(conf=conf, origen=origen, paso_optico=paso_optico, n_grid=n_grid)
    if motor in ("auto", "R"):
        try:
            res = calcular_r(estandares, muestras, **kwargs)
            res["engine_note"] = None
            return res
        except ErrorMotorR as exc:
            if motor == "R":
                raise
            res = calcular_python(estandares, muestras, **kwargs)
            res["engine_note"] = f"Se usó Python porque R no está disponible: {exc}"
            return res
    res = calcular_python(estandares, muestras, **kwargs)
    res["engine_note"] = None
    return res


def absortividad_molar(res: dict, unidad: str, masa_molar: float | None) -> float | None:
    """ε en L·mol⁻¹·cm⁻¹ a partir de la pendiente, si las unidades lo permiten."""
    a = res["absorptivity"]  # (unidad)⁻¹ · cm⁻¹
    factor = UNIDADES.get(unidad)
    if factor is not None:
        return a / factor
    if masa_molar and masa_molar > 0:
        g_por_unidad = _MASA_A_G[unidad]        # g/L por cada unidad
        return a / (g_por_unidad / masa_molar)  # mol/L por cada unidad
    return None
