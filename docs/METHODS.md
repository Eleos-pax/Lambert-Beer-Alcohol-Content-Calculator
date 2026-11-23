# Built-in method presets

CalibraUV includes presets for the UV-Vis quantification of secondary metabolites.
They are stored in [`calibrauv/methods.json`](../calibrauv/methods.json) and can be
edited or extended without touching the code.

Each value is labelled with its origin:

- 📚 **literature** — taken from the cited references;
- ⚠️ **general_knowledge** — standard analytical practice, **not** taken from the
  cited references. Verify it against your laboratory protocol before using it in
  production.

Selecting a preset fills the wavelength, reference standard, concentration unit and
result unit (e.g. mg GAE/g), and shows the method's principle, warnings and
references. You can always override any value in the sidebar. The calibration
statistics are the same for every method (R `stats::lm`).

| Method | Type | Standard(s) | λ (nm) | Result |
|---|---|---|---|---|
| Generic Beer-Lambert | curve | any | any | any |
| Total phenolics – Folin-Ciocalteu | curve | gallic acid, catechin, pyrogallol | 765 / 760 / 750 📚 | mg GAE/g |
| Total flavonoids – AlCl₃ | curve | quercetin, rutin, catechin | 420, 415, 408, 425 📚; 510 (NaNO₂–AlCl₃–NaOH) ⚠️ | mg QE/g or mg RE/g |
| Condensed tannins – vanillin-HCl | curve | catechin | 500, butanol-HCl 550, DMACA 640 ⚠️ | mg CE/g |
| Total alkaloids – bromocresol green | curve | atropine, caffeine, quinine | 470 ⚠️ / 415 📚 | mg AE/g |
| Total saponins – vanillin-H₂SO₄ | curve | aescin, diosgenin, oleanolic acid | 560 (540–560) 📚 | mg AeE/g |
| Total monomeric anthocyanins – pH differential (AOAC 2005.02) | **no curve** (known ε) | cyanidin-3-glucoside (MW 449.2, ε 26 900 ⚠️) | 520 & 700 | mg C3GE/L or /g |

Molar masses of the reference standards are general reference values (⚠️).

## Key warnings from the literature

- **Folin-Ciocalteu** is not specific: reducing sugars, ascorbic acid and proteins
  interfere; the order of addition matters (Chen et al. 2015); always report the standard.
- **AlCl₃** is not universal: flavonoids differ in λmax and absorptivity (Mammen &
  Daniel 2012); quercetin vs rutin changes the result greatly (Shraim et al. 2021);
  kaempferol and dihydrochalcones give low slopes (Matić 2017, 2021).
- **Tannins:** no single assay quantifies "total tannins" in every matrix (Nastasi 2025).
- **Saponins:** acetone, methanol and n-butanol darken the vanillin reaction; evaporate
  the solvent first (Le et al. 2018).

## Workflow implemented in the app

1. Select the method, variant and standard (λ, reaction time and result unit are loaded).
2. Enter standards (concentration, absorbance) with replicates.
3. Subtract the reagent blank (sidebar) and, for coloured extracts, the sample blank
   (`sample_blank` column).
4. Fit the linear regression: slope, intercept, R², s(y/x), residuals, LOD and LOQ.
5. The curve is **rejected** if R² is below the threshold (default 0.99) or the lack
   of fit is significant.
6. Enter the samples: absorbance, `extract_volume_mL`, `dilution_factor`, `mass_g`.
7. Samples outside the standards range or below the LOQ are flagged; above the highest
   standard the app asks for a dilution.
8. C = (A − a)/b and Content = C · V · DF / m.
9. Results are reported as mean ± SD and RSD% of replicates, with the equivalent unit
   (e.g. mg GAE/g DW).
10. For the pH differential method, no curve is used: the equation with ε and MW is applied.

Additional tabs cover **standard addition** (specificity: slope difference < 3% vs the
external curve, Ruiz-Vásquez et al. 2026) and **validation** (repeatability /
intermediate precision with RSD criteria of 2% or 5%, and recovery with 80–120% or
98–102% criteria).

## Adding a new method

Add an entry to `methods` in `calibrauv/methods.json`:

```json
{
  "id": "MY_ASSAY",
  "name": "My assay – reagent",
  "type": "curve",
  "analyte": "…",
  "principle": "…",
  "standards": [{"name": "Standard X", "abbr": "XE", "molar_mass": 123.4}],
  "variants": [{"name": "540 nm, 30 min (Author 2024)", "wavelength_nm": 540,
                "reaction_time_min": 30, "source": "literature", "ref": "author2024"}],
  "result_unit_label": "mg {abbr}/g",
  "default_unit": "µg/mL",
  "warnings": ["…"],
  "references": ["author2024"]
}
```

and the citation under `references`. The test `tests/test_analysis.py` checks that
every reference key exists and every variant states its source.

## References

See the `references` section of `methods.json`; they are also listed in the app
("Method & references" tab) and in every HTML report.
