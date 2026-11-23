"""Tests for blank correction, content, LOD basis, standard addition, validation and pH differential."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from calibrauv import analysis as an
from calibrauv import methods, ph_differential
from calibrauv.engine_python import compute_python

DATA = Path(__file__).resolve().parent.parent / "data"


def perfect_curve(b=0.1, a=0.02):
    x = np.repeat([1.0, 2, 4, 6, 8, 10], 3)
    noise = np.tile([0.001, -0.001, 0.0], 6)
    return pd.DataFrame({"c": x, "A": a + b * x + noise})


def test_methods_file_is_consistent():
    data = methods.load()
    refs = data["references"]
    ids = [m["id"] for m in data["methods"]]
    assert len(ids) == len(set(ids))
    for m in data["methods"]:
        for r in m.get("references", []):
            assert r in refs, f"{m['id']}: unknown reference {r}"
        for v in m.get("variants", []):
            assert v.get("source") in ("literature", "general_knowledge")
    assert methods.result_unit(methods.get("TPC_FOLIN"), {"abbr": "GAE"}) == "mg GAE/g"


def test_blank_correction():
    s = pd.DataFrame({"sample": ["X", "X"], "absorbance": [0.50, 0.52], "sample_blank": [0.02, None]})
    out = an.correct_samples(s, reagent_blank=0.05)
    assert out["absorbance"].tolist() == pytest.approx([0.43, 0.47])


def test_content_formula():
    res = compute_python(perfect_curve())
    a, b = an.intercept(res), an.slope(res)
    A = a + b * 5.0                       # C = 5 µg/mL exactly
    s = pd.DataFrame({"sample": ["E"] * 3, "absorbance": [A] * 3, "extract_volume_mL": [25] * 3,
                      "dilution_factor": [10] * 3, "mass_g": [0.5] * 3})
    res2 = compute_python(perfect_curve(), s)
    out = an.sample_content(res2, s, "µg/mL")
    # 5 µg/mL · 0.025 L · 10 / 0.5 g = 2.5 mg/g
    assert out.loc[0, "content_mean"] == pytest.approx(2.5)
    assert out.loc[0, "ci_low"] < 2.5 < out.loc[0, "ci_high"]
    assert an.content_unit("µg/mL", "GAE") == "mg GAE/g"
    assert an.content_unit("mmol/L") == "µmol/g"


def test_lod_bases():
    res = compute_python(perfect_curve())
    b = an.slope(res)
    an.apply_lod_basis(res, "sa")
    assert res["lod"] == pytest.approx(3.3 * res["coefficients"]["intercept"]["se"] / b)
    blanks = [0.010, 0.012, 0.011, 0.009, 0.010, 0.013, 0.011, 0.010, 0.012, 0.011]
    an.apply_lod_basis(res, "blanks", blanks)
    assert res["loq"] == pytest.approx(10 * np.std(blanks, ddof=1) / b)
    assert res["lod_note"] is None
    an.apply_lod_basis(res, "blanks", blanks[:4])
    assert "ICH" in res["lod_note"]


def test_standard_addition_exact():
    added = np.array([0, 2, 4, 6, 8.0])
    df = pd.DataFrame({"added": added, "A": 0.09 * (3.0 + added) + np.array([1, -1, 0, 1, -1]) * 1e-4})
    sa = an.standard_addition(compute_python(df), compute_python(perfect_curve(b=0.0927)))
    assert sa["C"] == pytest.approx(3.0, rel=2e-3)
    assert sa["ci_low"] < 3.0 < sa["ci_high"]
    assert sa["slope_diff_pct"] == pytest.approx(100 * abs(0.09 - 0.0927) / 0.0927, rel=1e-2)
    assert sa["parallel"] is True


def test_precision_and_recovery():
    res = compute_python(perfect_curve(b=0.1, a=0.0))
    prec = pd.DataFrame({"series": ["D1"] * 6, "absorbance": [0.5, 0.51, 0.49, 0.5, 0.505, 0.495]})
    rows, overall = an.precision(res, prec, max_rsd_pct=2.0)
    assert overall["n"] == 6 and overall["enough_n"]
    assert overall["rsd_pct"] == pytest.approx(100 * np.std([5, 5.1, 4.9, 5, 5.05, 4.95], ddof=1) / 5, rel=1e-3)
    rec = pd.DataFrame({"level": ["L"], "A_unspiked": [0.3], "A_spiked": [0.5], "C_added": [2.0]})
    d, summ = an.recovery(res, rec, (80, 120))
    assert d["recovery_pct"].iloc[0] == pytest.approx(100, rel=1e-3)
    assert summ["pass"]


def test_ph_differential_formula():
    d = pd.DataFrame({"sample": ["S"], "A520_pH1": [0.62], "A700_pH1": [0.02],
                      "A520_pH4.5": [0.12], "A700_pH4.5": [0.02], "dilution_factor": [10],
                      "extract_volume_mL": [50], "mass_g": [2.0]})
    rep, summ = ph_differential.compute(d)
    assert rep["A"].iloc[0] == pytest.approx(0.5)
    expected = 0.5 * 449.2 * 10 * 1000 / 26900
    assert rep["C_mg_L"].iloc[0] == pytest.approx(expected)
    assert rep["content_mg_g"].iloc[0] == pytest.approx(expected * 0.05 / 2.0)


def test_demo_files_load():
    for f in ("demo_tpc_gallic_acid.csv", "demo_tpc_samples.csv", "demo_tpc_standard_addition.csv",
              "demo_tpc_precision.csv", "demo_tpc_recovery.csv", "demo_ph_differential.csv"):
        assert len(pd.read_csv(DATA / f)) > 0
    rep, summ = ph_differential.compute(pd.read_csv(DATA / "demo_ph_differential.csv"))
    assert len(summ) == 2 and (rep["A"] > 0).all()
