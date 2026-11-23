# Contributing to CalibraUV

Thank you for your interest! A few guidelines:

1. **Open an issue** before large changes to discuss the idea.
2. **Computations:** any statistical change must be implemented **in both engines**
   (`r/calibration.R` and `calibrauv/engine_python.py`), with the same key in the
   JSON output, a test in `tests/`, and the formula with its reference in
   `docs/THEORY.md`.
3. **Compatibility:** the R script must keep using only base R + `stats`. The code
   must work on Windows and Linux (use `pathlib`, no hard-coded paths).
4. **Tests:** `python -m pytest -v` must pass (it includes the R vs Python comparison).
5. **AI use:** allowed; declare it in the pull request and make sure you understand
   every line. See [RESPONSIBLE_AI_POLICY.md](RESPONSIBLE_AI_POLICY.md).
6. **New methods:** add them to `calibrauv/methods.json` (see
   [docs/METHODS.md](docs/METHODS.md)), with references and the `source` of every value.
7. **Language:** the interface and documentation are in English.

Open ideas: weighted regression (1/x, 1/x²), Mandel's linearity test, direct import of spectrophotometer files, and
translations (e.g. Spanish).
