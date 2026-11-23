"""Tests: the Python engine is correct and matches R (when R is installed)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from calibrauv.engine import molar_absorptivity
from calibrauv.engine_python import compute_python
from calibrauv.engine_r import compute_r, find_rscript

DATA = Path(__file__).resolve().parent.parent / "data"
STD = pd.read_csv(DATA / "example_iron_calibration.csv")
UNK = pd.read_csv(DATA / "example_samples.csv")

needs_r = pytest.mark.skipif(find_rscript() is None, reason="R is not installed")


def _flatten(d, prefix=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(_flatten(v, f"{prefix}{k}."))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            out.update(_flatten(v, f"{prefix}{i}."))
    else:
        out[prefix[:-1]] = d
    return out


def test_python_matches_polyfit():
    res = compute_python(STD)
    b, a = np.polyfit(STD.iloc[:, 0], STD.iloc[:, 1], 1)
    assert res["coefficients"]["slope"]["estimate"] == pytest.approx(b)
    assert res["coefficients"]["intercept"]["estimate"] == pytest.approx(a)
    assert 0.999 < res["r_squared"] <= 1


def test_fit_through_origin():
    df = pd.DataFrame({"c": [1, 2, 3, 4, 5], "A": [0.1, 0.2, 0.3, 0.4, 0.5]})
    df.loc[2, "A"] = 0.3001
    res = compute_python(df, origin=True)
    assert res["coefficients"]["intercept"] is None
    assert res["coefficients"]["slope"]["estimate"] == pytest.approx(0.1, rel=1e-3)


def test_molar_absorptivity_iron():
    res = compute_python(STD)
    eps = molar_absorptivity(res, "mg/L (ppm)", 55.845)
    assert 10000 < eps < 12000   # ε(Fe-phenanthroline, 510 nm) ≈ 11 100


def test_input_errors():
    with pytest.raises(ValueError):
        compute_python(pd.DataFrame({"c": [1, 2], "A": [0.1, 0.2]}))


@needs_r
@pytest.mark.parametrize("origin", [False, True])
def test_r_and_python_agree(origin):
    r = _flatten(compute_r(STD, UNK, origin=origin))
    py = _flatten(compute_python(STD, UNK, origin=origin))
    for key, value in py.items():
        if key == "engine":
            continue
        assert key in r, f"{key} missing in R output"
        if isinstance(value, (bool, str)) or value is None or r[key] is None:
            assert value == r[key], key
        else:
            assert value == pytest.approx(r[key], rel=1e-6, abs=1e-10), key
