# Theoretical background and formulas

This document describes exactly what CalibraUV computes. The same formulas are
implemented in `r/calibration.R` (reference engine) and in
`calibrauv/engine_python.py` (verification engine).

## 1. Beer-Lambert law

$$A = \log_{10}\frac{I_0}{I} = \varepsilon \, l \, c$$

| Symbol | Meaning | Typical units |
|---|---|---|
| A | absorbance | dimensionless |
| ε | molar absorptivity | L·mol⁻¹·cm⁻¹ |
| l | cell path length | cm |
| c | concentration | mol·L⁻¹ |

Experimentally, **A = a + b·C** is fitted, where the slope **b = ε·l** is the
method's sensitivity and the intercept **a** captures residual blank absorbance
and constant systematic errors.

**Deviations from the law:** high concentrations (> ~0.01 M), chemical
equilibria, non-monochromatic radiation, stray light and absorbances > ~1.5.
That is why linearity must be *checked*, not assumed.

### Molar absorptivity from mass-based units

If C is in mg/L, the slope has units of L·mg⁻¹; with the molar mass M:

$$\varepsilon = \frac{b}{l}\cdot 1000\,M$$

## 2. Ordinary least-squares regression

With n standards (xᵢ, yᵢ):

$$S_{xx}=\sum (x_i-\bar x)^2,\qquad b=\frac{\sum (x_i-\bar x)(y_i-\bar y)}{S_{xx}},\qquad a=\bar y-b\bar x$$

Standard error of the regression (standard deviation of the residuals):

$$s_{y/x}=\sqrt{\frac{\sum (y_i-\hat y_i)^2}{n-2}}$$

Standard errors and confidence intervals (Student's t with n − 2 df):

$$s_b=\frac{s_{y/x}}{\sqrt{S_{xx}}},\qquad s_a=s_{y/x}\sqrt{\frac{\sum x_i^2}{n\,S_{xx}}},\qquad b\pm t\,s_b,\quad a\pm t\,s_a$$

**Model through the origin (A = b·C):** b = Σxy/Σx², s_b = s_{y/x}/√Σx², with
n − 1 df. In this case R² is *uncentered* (it uses Σy² instead of Σ(y−ȳ)²), as in
R, and is usually artificially high. Use this model only if the intercept is not
significant and the blank has been properly subtracted.

## 3. Goodness of fit

- **Pearson r**, **R²** = 1 − SS_res/SS_tot, **adjusted R²**.
- **Regression ANOVA:** F = MS_reg / MS_res with (1, n − p) df.
- **Slope RSD** (%) = 100·s_b/b.

> An R² close to 1 does **not** prove linearity (Anscombe, 1973). Always examine
> the residuals and the lack-of-fit test.

## 4. Assumption checks

| Assumption | Test | Indicative criterion |
|---|---|---|
| Normality of residuals | Shapiro-Wilk | p > 0.05 |
| Constant variance | Studentized Breusch-Pagan (Koenker): n·R² of e² ~ x, χ²(1) | p > 0.05 |
| Independence | Durbin-Watson: Σ(eᵢ − eᵢ₋₁)² / Σeᵢ² | 1.5 – 2.5 |
| Linearity | Lack of fit (requires replicates) | p > 0.05 |
| Influential points | Cook's distance | Dᵢ < 4/n |
| Outliers | Standardized residual rᵢ = eᵢ / (s√(1 − hᵢᵢ)) | \|rᵢ\| < 2.5 |

**Lack of fit:** with k distinct concentration levels,
SS_pe = Σ_j Σ_i (y_ij − ȳ_j)² (pure error, n − k df),
SS_lof = SS_res − SS_pe (k − p df), F = (SS_lof/df_lof)/(SS_pe/df_pe).

**Leverage:** hᵢᵢ = 1/n + (xᵢ − x̄)²/S_xx (or xᵢ²/Σx² through the origin).
**Cook:** Dᵢ = rᵢ²·hᵢᵢ / (p(1 − hᵢᵢ)).

## 5. Confidence and prediction bands

For a value x₀:

$$\hat y_0 \pm t\,s_{y/x}\sqrt{\tfrac1n+\tfrac{(x_0-\bar x)^2}{S_{xx}}}\quad\text{(confidence of the line)}$$

$$\hat y_0 \pm t\,s_{y/x}\sqrt{1+\tfrac1n+\tfrac{(x_0-\bar x)^2}{S_{xx}}}\quad\text{(prediction of a new measurement)}$$

In R these are obtained with `predict(fit, interval = "confidence" | "prediction")`.

## 6. Limits of detection and quantification (ICH Q2)

$$LOD = \frac{3.3\,s_{y/x}}{b},\qquad LOQ=\frac{10\,s_{y/x}}{b}$$

s_{y/x} is used as the estimate of the standard deviation of the response. If you
have ≥ 10 blanks, the blank standard deviation is a preferable alternative for
the LOD.

## 7. Concentration of samples (inverse regression)

With m absorbance replicates of mean ȳ₀:

$$\hat x_0=\frac{\bar y_0-a}{b},\qquad s_{x_0}=\frac{s_{y/x}}{b}\sqrt{\frac1m+\frac1n+\frac{(\bar y_0-\bar y)^2}{b^2S_{xx}}},\qquad \hat x_0\pm t\,s_{x_0}$$

Through the origin: s_{x0} = (s_{y/x}/b)·√(1/m + ȳ₀²/(b²Σx²)).

The app flags samples that are **extrapolated** (outside the calibrated range),
**< LOD** and **< LOQ**. If you diluted the sample, multiply the result and its
interval by the dilution factor.

## References

- Miller, J. N., & Miller, J. C. (2018). *Statistics and Chemometrics for Analytical Chemistry* (7th ed.). Pearson.
- Harris, D. C. (2016). *Quantitative Chemical Analysis* (9th ed.). W. H. Freeman.
- Skoog, D. A., Holler, F. J., & Crouch, S. R. (2017). *Principles of Instrumental Analysis* (7th ed.). Cengage.
- ICH Q2(R2) (2023). *Validation of Analytical Procedures*.
- Eurachem (2014). *The Fitness for Purpose of Analytical Methods* (2nd ed.).
- Anscombe, F. J. (1973). Graphs in statistical analysis. *The American Statistician*, 27(1), 17–21.
- Koenker, R. (1981). A note on studentizing a test for heteroscedasticity. *Journal of Econometrics*, 17(1), 107–112.
- R Core Team. *R: A Language and Environment for Statistical Computing*. R Foundation for Statistical Computing.
