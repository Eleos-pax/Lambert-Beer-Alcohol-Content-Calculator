# Responsible AI Use Policy

**Project:** CalibraUV · **Policy version:** 1.1 · **Date:** November 2026

## 1. Transparency statement

CalibraUV was **designed and programmed mostly with the help of Claude**, an
artificial intelligence assistant developed by Anthropic. The AI took part in:

- designing the architecture (statistical engine in R + interface in Python),
- writing the source code, automated tests and installers,
- writing the documentation and this policy.

The people responsible for the project defined the requirements, reviewed the
work, ran it and are accountable for it. Commits produced with AI assistance
state so through the corresponding `Co-Authored-By` line.

This is an independent project, **not affiliated with or endorsed by Anthropic**.
Claude is a trademark of Anthropic.

## 2. Principles

1. **Human accountability.** AI is a tool; scientific, technical and ethical
   responsibility for the results always lies with the people who use, maintain
   or contribute to the software.
2. **Verifiability.** Every computation must be reproducible. Therefore:
   - the reference engine is R's `stats::lm`, a widely validated standard;
   - an independent Python engine (NumPy/SciPy) repeats the same computations, and
     the automated tests require **both to agree** (relative tolerance 10⁻⁶);
   - the formulas are documented in [`docs/THEORY.md`](docs/THEORY.md) with
     bibliographic references.
3. **Transparency.** The app states in its interface and in every report that it
   was developed with AI assistance. This notice must not be hidden or removed in
   redistributions.
4. **Privacy.** CalibraUV works **offline** and **does not send data to any AI
   service** or third party. Your laboratory data is processed only on your
   computer. (Streamlit is configured with `gatherUsageStats = false`.)
5. **Honesty about limitations.** AI-generated code may contain subtle errors.
   The interpretation criteria included (e.g. R² ≥ 0.995) are indicative and do
   not replace the acceptance criteria of your validated method or applicable
   regulations (ICH Q2(R2), ISO/IEC 17025, pharmacopoeias, etc.).

## 3. Responsible use by users

- **Verify** critical results with a second method (validated spreadsheet, other
  software or manual calculation) before using them in regulatory, clinical,
  environmental, legal or commercial decisions.
- **Do not remove** calibration points just because the software flags them as
  outliers: do so only with a justified and documented experimental cause.
- **Do not present** reports as if they came from a validated system unless your
  organization has formally validated it.
- **In educational settings**, use the tool to understand calibration statistics,
  not to replace learning: review the formulas, compare them with your own
  calculations, and cite the software if you use it in your work.

## 4. AI-assisted contributions

Contributions written with the help of AI tools are welcome, provided that:

1. the contributor **understands and can explain** every change;
2. AI use is declared in the pull request description;
3. changes to computations include tests and, where applicable, the
   bibliographic reference for the formula;
4. the automated tests pass on Windows and Linux;
5. no code, data or text under third-party copyright is included without a
   compatible license.

## 5. Reporting problems

If you find a calculation error, a dubious result or misuse of the tool, open an
issue in the repository stating: input data (if you can share it), expected
result, obtained result, operating system and R and Python versions.
Calculation errors have top priority.

## 6. Review of this policy

This policy will be reviewed when the AI tools used or the scope of the project
change significantly. Suggestions are welcome.
