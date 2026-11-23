"""The step-by-step calculation must reproduce the engine (R and Python) for every sample."""

from pathlib import Path

import pandas as pd
import pytest

from calibrauv import analysis as an
from calibrauv.engine_python import compute_python
from calibrauv.engine_r import compute_r, find_rscript
from calibrauv.handcalc import fmt, sample_steps

DATA = Path(__file__).resolve().parent.parent / "data"
engines = [compute_python] + ([compute_r] if find_rscript() else [])


@pytest.mark.parametrize("engine", engines)
@pytest.mark.parametrize("origin", [False, True])
@pytest.mark.parametrize("blank", [0.0, 0.01])
def test_hand_calculation_matches_engine(engine, origin, blank):
    std = pd.read_csv(DATA / "demo_tpc_gallic_acid.csv")
    smp = pd.read_csv(DATA / "demo_tpc_samples.csv")
    std_c = an.correct_standards(std, blank)
    smp_c = an.correct_samples(smp, blank)
    res = engine(std_c, smp_c[["sample", "absorbance"]], origin=origin)
    for u in res["unknowns"]:
        rows = smp[smp["sample"] == u["sample"]]
        st = sample_steps(res, rows, reagent_blank=blank, conc_unit="µg/mL")
        assert st["m"] == u["m"]
        assert st["y0"] == pytest.approx(u["y_mean"], rel=1e-9)
        assert st["c0"] == pytest.approx(u["x0"], rel=1e-9)
        assert st["s_c0"] == pytest.approx(u["s_x0"], rel=1e-7)
        assert st["ci_low"] == pytest.approx(u["ci_low"], rel=1e-7)
        assert st["ci_high"] == pytest.approx(u["ci_high"], rel=1e-7)
    # content agrees with the content table
    tab = an.sample_content(res, smp_c, "µg/mL")
    for _, row in tab.iterrows():
        st = sample_steps(res, smp[smp["sample"] == row["sample"]], blank, "µg/mL")
        assert st["content_mean"] == pytest.approx(row["content_mean"], rel=1e-9)


def test_fmt():
    assert fmt(-0.0123) == "(-0.0123)"
    assert fmt(2.5) == "2.5"
    assert "10^{-6}" in fmt(1.2e-6)
