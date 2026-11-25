"""Publication export: exact size, resolution, lossless TIFF, embedded TrueType fonts, every design option."""

import io
import re
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from calibrauv import plots as P
from calibrauv.engine_python import compute_python

DATA = Path(__file__).resolve().parent.parent / "data"
RES = compute_python(pd.read_csv(DATA / "demo_lab_tpc_gallic_acid.csv"),
                     pd.read_csv(DATA / "demo_lab_tpc_samples.csv")[["sample", "absorbance"]])


@pytest.mark.parametrize("fmt,dpi", [("tiff", 600), ("tiff", 1200), ("png", 300)])
@pytest.mark.parametrize("width", [85.0, 174.0])
def test_raster_exact_size_and_dpi(fmt, dpi, width):
    d = P.Design(width_mm=width, height_mm=width * 0.75)
    im = Image.open(io.BytesIO(P.export_figure(P.mpl_calibration(RES, "C", design=d), fmt, dpi)))
    assert im.size == (int(width / 25.4 * dpi), int(width * 0.75 / 25.4 * dpi))
    assert round(im.info["dpi"][0]) == dpi
    assert im.mode == "RGB"                                       # no alpha channel
    if fmt == "tiff":
        assert im.info.get("compression") == "tiff_lzw"
        cmyk = Image.open(io.BytesIO(P.export_figure(P.mpl_calibration(RES, "C", design=d), "tiff", 300,
                                                     color_mode="CMYK")))
        assert cmyk.mode == "CMYK"


@pytest.mark.parametrize("font", ["sans", "serif"])
def test_vector_fonts_embedded(font):
    d = P.Design(font=font)
    pdf = P.export_figure(P.mpl_diagnostics(RES, "C", design=replace(d, width_mm=174, height_mm=120)), "pdf")
    assert b"/Type3" not in pdf and b"/FontFile2" in pdf          # TrueType, not Type 3
    names = re.findall(rb"/BaseFont /[A-Z]+\+([A-Za-z\-]+)", pdf)
    assert names and not any(n.startswith(b"DejaVu") for n in names), names   # Arial/Times or metric clone
    svg = P.export_figure(P.mpl_calibration(RES, "C", design=d), "svg")
    assert b"<text" in svg                                         # editable text
    eps = P.export_figure(P.mpl_calibration(RES, "C", design=d), "eps")
    assert eps.startswith(b"%!PS")


def test_every_theme_palette_and_option():
    for theme in P.THEMES:
        for pal in P.PALETTES:
            d = P.Design(theme=theme, palette=pal, replicate_means=True, residual_lines=True, legend="outside",
                         show_title=True, grid="both", marker="D", xlabel="X", ylabel="Y")
            P.export_figure(P.mpl_calibration(RES, "C", design=d), "png", 72)
            P.export_figure(P.mpl_diagnostics(RES, "C", design=d), "png", 72)
            P.plotly_calibration(RES, "C", design=d).to_json()
            P.plotly_diagnostics(RES, "C", design=d).to_json()
            P.altair_calibration(RES, "C", design=d).to_json()


def test_no_transparency_in_publication_figures():
    fig = P.mpl_calibration(RES, "C", design=P.Design())
    alphas = [c.get_alpha() for ax in fig.axes for c in ax.collections]
    assert all(a in (None, 1, 1.0) for a in alphas), alphas
    P.plt.close(fig)
