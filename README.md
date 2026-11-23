# 🧪 CalibraUV

**Calibration curves for UV-Vis spectroscopy based on the Beer-Lambert law**, for
**any analyte** that follows the law (metals, dyes, drugs, ethanol by colorimetric
methods, proteins, etc.), with full statistics computed in **R** and plots made with **Matplotlib, Seaborn, Plotly and Altair**.

[![Tests](../../actions/workflows/tests.yml/badge.svg)](../../actions/workflows/tests.yml)
![MIT License](https://img.shields.io/badge/license-MIT-blue)
![Windows | Linux](https://img.shields.io/badge/platform-Windows%20%7C%20Ubuntu%20%7C%20Mint-informational)
![Built with the help of Claude](https://img.shields.io/badge/built%20with%20the%20help%20of-Claude%20(Anthropic)-d97757)

> 🤖 **AI notice:** this application was designed and programmed **mostly with the
> help of Claude** (Anthropic) and reviewed by humans. Please read the
> [Responsible AI Use Policy](RESPONSIBLE_AI_POLICY.md).
>
> Independent project, not affiliated with or endorsed by Anthropic. Claude is a
> trademark of Anthropic.

![CalibraUV screenshot](docs/screenshot.png)

---

## What does it do?

| Area | Contents |
|---|---|
| **Regression** | A = a + b·C by least squares (R's `stats::lm`), optionally forced through the origin |
| **Coefficients** | Estimates, standard errors, t, p and confidence intervals (90/95/99 %) |
| **Fit** | r, R², adjusted R², s(y/x), regression ANOVA, slope RSD |
| **Assumptions** | Shapiro-Wilk, Breusch-Pagan, Durbin-Watson, lack of fit (with replicates), standardized residuals, leverage, Cook's distance |
| **Analytical** | LOD and LOQ (ICH Q2), absorptivity a = b/l and **molar absorptivity ε** (also from mg/L using the molar mass) |
| **Samples** | Concentration by inverse regression with its uncertainty s(C₀) and confidence interval; warnings for extrapolation, < LOD and < LOQ |
| **Plots** | Curve with confidence and prediction bands, LOD/LOQ and samples; diagnostics panel (residuals, Q-Q, Cook) |
| **Libraries** | Plotly (interactive), Matplotlib + Seaborn, plain Matplotlib, Altair — 300 dpi PNG for publications |
| **Export** | HTML report with interpretation, JSON results and residuals CSV |
| **Input** | Editable table, CSV (comma, or semicolon with decimal comma) and Excel |

All formulas are explained in [docs/THEORY.md](docs/THEORY.md).

## Architecture

```
Interface (Streamlit, Python)
   │  CSV data ──►  Rscript r/calibration.R  ──► JSON   (reference engine: base R + stats)
   │            └►  calibrauv/engine_python.py          (fallback & cross-check: NumPy/SciPy)
   └─ plots:  Matplotlib · Seaborn · Plotly · Altair
```

- The R script **needs no extra packages** (base R only), so it works the same on
  Windows and Linux.
- If R is not installed, the app automatically uses the Python engine.
- The automated tests check that **R and Python give the same results**
  (relative tolerance 10⁻⁶) on Ubuntu and Windows.

## Installation

Requirements: **Python 3.10+** and (recommended) **R 4.x**.

### 🐧 Ubuntu / Linux Mint

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip r-base git
```

```bash
git clone https://github.com/Eleos-pax/Lambert-Beer-Alcohol-Content-Calculator.git
```

```bash
cd Lambert-Beer-Alcohol-Content-Calculator && ./scripts/install_linux.sh
```

```bash
./scripts/run_linux.sh
```

### 🪟 Windows 10 / 11

1. Install Python and R (from PowerShell, or from their official sites:
   [python.org](https://www.python.org/downloads/) ticking *Add python.exe to PATH*,
   and [CRAN](https://cran.r-project.org/bin/windows/base/)):

   ```bash
   winget install Python.Python.3.12
   ```

   ```bash
   winget install RProject.R
   ```

2. Download the project (**Code → Download ZIP** button, or `git clone`).
3. Double-click `scripts\install_windows.bat` (first time only).
4. Double-click `scripts\run_windows.bat`. Your browser will open at `http://localhost:8501`.

CalibraUV finds R automatically in `C:\Program Files\R\R-*`. If you installed it
somewhere else, set the `CALIBRAUV_RSCRIPT` environment variable to the full path
of `Rscript.exe`.

### Manual installation (any system)

```bash
python -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip ...
```

```bash
.venv/bin/streamlit run app.py                   # Windows: .venv\Scripts\streamlit ...
```

## Usage

1. **Data:** type or paste your standards (concentration, absorbance), or upload a
   CSV/Excel file. Enter replicates as repeated rows with the same concentration.
2. **Samples (optional):** columns `sample` and `absorbance`; one row per replicate.
3. In the sidebar, set the unit, path length, molar mass, confidence level and
   plotting library.
4. Check **Statistics** → **Plots** → **Samples** and download the **Report**.

The app is **not tied to any specific method**: enter the analyte, wavelength, units
and molar mass of your own assay. Demo data is included in [`data/`](data/)
(Fe(II)–o-phenanthroline at 510 nm, in triplicate; synthetic values) only to show how
the app works — untick **Load demo data** in the sidebar to start with an empty table.

### Using the R engine without the interface

The R script can be used on its own, for example from RStudio or the terminal:

```bash
Rscript r/calibration.R --data=data/example_iron_calibration.csv --unknowns=data/example_samples.csv --conf=0.95 --out=results.json
```

## Tests

```bash
pip install -r requirements-dev.txt && python -m pytest -v
```

## Project structure

```
Lambert-Beer-Alcohol-Content-Calculator/
├── app.py                        Streamlit interface
├── r/calibration.R               Statistical engine in R (reference)
├── calibrauv/
│   ├── engine.py                 Engine selection and molar absorptivity
│   ├── engine_r.py               Python → Rscript bridge (Windows/Linux)
│   ├── engine_python.py          NumPy/SciPy verification engine
│   ├── interpretation.py         Plain-language interpretation of assumptions
│   ├── plots.py                  Matplotlib, Seaborn, Plotly, Altair
│   └── report.py                 Tables and HTML report
├── data/                         Example data
├── docs/THEORY.md                Formulas and references
├── scripts/                      Installers for Windows and Linux
├── tests/                        Tests (R vs Python)
└── RESPONSIBLE_AI_POLICY.md
```

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and the
[AI policy](RESPONSIBLE_AI_POLICY.md).

## License and credits

Free software under the **MIT license** ([LICENSE](LICENSE)).

Built on: [R](https://www.r-project.org/), [Streamlit](https://streamlit.io/),
[NumPy](https://numpy.org/), [SciPy](https://scipy.org/), [pandas](https://pandas.pydata.org/),
[Matplotlib](https://matplotlib.org/), [Seaborn](https://seaborn.pydata.org/),
[Plotly](https://plotly.com/python/) and [Altair](https://altair-viz.github.io/).

Designed mostly with the help of **Claude** (Anthropic).

> ⚠️ CalibraUV is an educational and laboratory support tool. It is not validated
> software for regulatory use; verify critical results according to your quality system.
