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

## Laboratory protocols

Three presets reproduce the laboratory protocol of the Natural Products Laboratory
(Universidad de Sucre), used for honey extracts of *Apis mellifera* (V2.2) and the
hydroalcoholic extract of fresh *Citrus paradisi* flavedo and its fractions (V3.1),
measured on a Spectroquant Pharo 300 UV-Vis spectrophotometer. They appear first in the
method list.

| Preset | Standard | λ (nm) | Calibration levels (µg/mL) | Result |
|---|---|---|---|---|
| Total phenolics – Folin-Ciocalteu / NaOH 0.35 M, reagent 1:50, 3 min dark (Tovar 2013; Recuero Pacheco 2018) | gallic acid | 760 | 0, 2, 4, 6, 8, 10 | mg GAE/g extract |
| Flavonoids – NaNO₂ 5% (5 min), AlCl₃ 2.5% (6 min), NaOH 1 M, read after 5 min (Tovar 2013; Recuero Pacheco 2018) | quercetin (or catechin) | 500 | 5, 10, 20, 40 | mg QE/g extract |
| Tannins – Folin-Ciocalteu (Na₂CO₃ 7.5%, reagent 10%) with casein precipitation, by difference (Gomes et al. 2021) | tannic acid | 760 | 0.5, 2, 4, 6, 8, 10, 12, 14 | mg TAE/g extract |

**Content per gram of extract.** Samples are read as a solution of the extract at a
known concentration (e.g. 50 µg/mL for phenolics), entered in `extract_conc_ug_mL`:

    Content (mg/g) = C (µg/mL) · DF / C_extract (µg/mL) · 1000

All three assays are reported on the **same scale** (mg/g by default, µg/g optional),
which resolves the mixed units of the original protocol (µg/g for phenolics and
flavonoids, mg/g for tannins).

**Tannins by difference.** For each replicate enter `A_TP` (total polyphenols) and
`A_RP` (residual polyphenols in the casein supernatant). Because 6 mL of sample are
mixed with 12 mL of water, RP is diluted ×3 with respect to TP; this casein dilution
factor (editable in the sidebar) is applied before subtracting:

    Tannins = TP − RP · DF_casein

**Notes carried over from the protocol** (shown as warnings in the app):

- Phenolics and tannins use two Folin-Ciocalteu variants (NaOH 0.35 M + reagent 1:50
  vs Na₂CO₃ 7.5% + reagent 10%); deciding whether to harmonize them is pending.
- NaNO₂–AlCl₃–NaOH responds mainly to flavonoids with a catechol group; with quercetin
  it may underestimate. Options: catechin as standard, or direct AlCl₃ at ~415 nm with
  quercetin. In honey, a sample blank is recommended (Sultana et al., 2024).
- The flavonoid curve has 4 levels; ICH Q2 recommends at least 5.
- Replicates are technical (triplicate of the same sample) and do not replace
  biological replicates.

**Fraction selection.** Honey: quantification in the ethyl acetate fraction (petroleum
ether, dichloromethane and n-butanol fractions are used for screening and the UV-Vis
scan). *C. paradisi*: quantification only in fractions positive in the specific
phytochemical screening tests (Valentin et al., 2024).

References: Tovar (2013); Recuero Pacheco (2018); Gomes et al. (2021); Valentin et al.
(2024) — full citations in `methods.json` and in the app.

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
