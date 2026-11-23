"""Choice of computation engine: R (preferred) or Python (fallback)."""

from __future__ import annotations

import pandas as pd

from .engine_python import compute_python
from .i18n import t
from .engine_r import REngineError, compute_r, find_rscript

# Factors to convert 1 concentration unit to mol/L.
# None = depends on the molar mass (mass-based units).
UNITS = {
    "mol/L": 1.0,
    "mmol/L": 1e-3,
    "µmol/L": 1e-6,
    "mg/L (ppm)": None,
    "µg/mL": None,        # = mg/L
    "µg/L (ppb)": None,
    "g/L": None,
}
_MASS_TO_G = {"mg/L (ppm)": 1e-3, "µg/mL": 1e-3, "µg/L (ppb)": 1e-6, "g/L": 1.0}


def available_engines() -> dict[str, bool]:
    return {"R": find_rscript() is not None, "Python": True}


def compute(standards: pd.DataFrame, samples: pd.DataFrame | None = None, *,
            engine: str = "auto", conf: float = 0.95, origin: bool = False,
            path_length: float = 1.0, n_grid: int = 100) -> dict:
    """Fit the calibration curve A = a + b·C.

    engine: "auto" (R if available, otherwise Python), "R" or "Python".
    """
    kwargs = dict(conf=conf, origin=origin, path_length=path_length, n_grid=n_grid)
    if engine in ("auto", "R"):
        try:
            res = compute_r(standards, samples, **kwargs)
            res["engine_note"] = None
            return res
        except REngineError as exc:
            if engine == "R":
                raise
            res = compute_python(standards, samples, **kwargs)
            res["engine_note"] = t("Python was used because R is not available: {e}", e=exc)
            return res
    res = compute_python(standards, samples, **kwargs)
    res["engine_note"] = None
    return res


def molar_absorptivity(res: dict, unit: str, molar_mass: float | None) -> float | None:
    """ε in L·mol⁻¹·cm⁻¹ from the slope, when the units allow it."""
    a = res["absorptivity"]  # (unit)⁻¹ · cm⁻¹
    factor = UNITS.get(unit)
    if factor is not None:
        return a / factor
    if molar_mass and molar_mass > 0:
        g_per_unit = _MASS_TO_G[unit]          # g/L per unit
        return a / (g_per_unit / molar_mass)   # mol/L per unit
    return None
