"""Pruebas: el motor Python es correcto y coincide con R (si R está instalado)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from calibrauv.motor import absortividad_molar
from calibrauv.motor_python import calcular_python
from calibrauv.motor_r import buscar_rscript, calcular_r

DATOS = Path(__file__).resolve().parent.parent / "datos"
STD = pd.read_csv(DATOS / "ejemplo_calibracion_hierro.csv")
UNK = pd.read_csv(DATOS / "ejemplo_muestras.csv")

hay_r = pytest.mark.skipif(buscar_rscript() is None, reason="R no está instalado")


def _aplanar(d, pref=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_aplanar(v, f"{pref}{k}."))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            out.update(_aplanar(v, f"{pref}{i}."))
    else:
        out[pref[:-1]] = d
    return out


def test_python_coincide_con_polyfit():
    res = calcular_python(STD)
    b, a = np.polyfit(STD.iloc[:, 0], STD.iloc[:, 1], 1)
    assert res["coefficients"]["slope"]["estimate"] == pytest.approx(b)
    assert res["coefficients"]["intercept"]["estimate"] == pytest.approx(a)
    assert 0.999 < res["r_squared"] <= 1


def test_ajuste_perfecto_por_origen():
    df = pd.DataFrame({"c": [1, 2, 3, 4, 5], "A": [0.1, 0.2, 0.3, 0.4, 0.5]})
    df.loc[2, "A"] = 0.3001
    res = calcular_python(df, origen=True)
    assert res["coefficients"]["intercept"] is None
    assert res["coefficients"]["slope"]["estimate"] == pytest.approx(0.1, rel=1e-3)


def test_absortividad_molar_hierro():
    res = calcular_python(STD)
    eps = absortividad_molar(res, "mg/L (ppm)", 55.845)
    assert 10000 < eps < 12000   # ε(Fe-fenantrolina, 510 nm) ≈ 11 100


def test_errores_de_entrada():
    with pytest.raises(ValueError):
        calcular_python(pd.DataFrame({"c": [1, 2], "A": [0.1, 0.2]}))


@hay_r
@pytest.mark.parametrize("origen", [False, True])
def test_r_y_python_coinciden(origen):
    r = _aplanar(calcular_r(STD, UNK, origen=origen))
    py = _aplanar(calcular_python(STD, UNK, origen=origen))
    for clave, valor in py.items():
        if clave in ("engine",):
            continue
        assert clave in r, f"falta {clave} en R"
        if isinstance(valor, (bool, str)) or valor is None or r[clave] is None:
            assert valor == r[clave], clave
        else:
            assert valor == pytest.approx(r[clave], rel=1e-6, abs=1e-10), clave
