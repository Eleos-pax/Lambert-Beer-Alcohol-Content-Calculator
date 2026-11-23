# Fundamentos teóricos y fórmulas

Este documento describe exactamente qué calcula CalibraUV. Las mismas fórmulas
están implementadas en `r/calibracion.R` (motor de referencia) y en
`calibrauv/motor_python.py` (motor de verificación).

## 1. Ley de Lambert-Beer

$$A = \log_{10}\frac{I_0}{I} = \varepsilon \, l \, c$$

| Símbolo | Significado | Unidades típicas |
|---|---|---|
| A | absorbancia | adimensional |
| ε | absortividad molar | L·mol⁻¹·cm⁻¹ |
| l | paso óptico de la celda | cm |
| c | concentración | mol·L⁻¹ |

Experimentalmente se ajusta **A = a + b·C**, donde la pendiente **b = ε·l** es la
sensibilidad del método y el intercepto **a** recoge la absorción residual del
blanco y errores sistemáticos constantes.

**Desviaciones de la ley:** concentraciones altas (> ~0.01 M), equilibrios químicos,
radiación no monocromática, luz parásita y absorbancias > ~1.5. Por eso la
linealidad debe *comprobarse*, no suponerse.

### Absortividad molar con unidades de masa

Si C está en mg/L, la pendiente tiene unidades L·mg⁻¹; con la masa molar M:

$$\varepsilon = \frac{b}{l}\cdot 1000\,M$$

## 2. Regresión por mínimos cuadrados ordinarios

Con n estándares (xᵢ, yᵢ):

$$S_{xx}=\sum (x_i-\bar x)^2,\qquad b=\frac{\sum (x_i-\bar x)(y_i-\bar y)}{S_{xx}},\qquad a=\bar y-b\bar x$$

Error estándar de la regresión (desviación estándar de los residuales):

$$s_{y/x}=\sqrt{\frac{\sum (y_i-\hat y_i)^2}{n-2}}$$

Errores estándar e intervalos de confianza (t de Student con n − 2 gl):

$$s_b=\frac{s_{y/x}}{\sqrt{S_{xx}}},\qquad s_a=s_{y/x}\sqrt{\frac{\sum x_i^2}{n\,S_{xx}}},\qquad b\pm t\,s_b,\quad a\pm t\,s_a$$

**Modelo por el origen (A = b·C):** b = Σxy/Σx², s_b = s_{y/x}/√Σx², con n − 1 gl.
En este caso R² es *no centrado* (usa Σy² en lugar de Σ(y−ȳ)²), igual que R, y
suele ser artificialmente alto. Use este modelo solo si el intercepto no es
significativo y el blanco está correctamente restado.

## 3. Bondad de ajuste

- **r de Pearson**, **R²** = 1 − SC_res/SC_tot, **R² ajustado**.
- **ANOVA de la regresión:** F = CM_reg / CM_res con (1, n − p) gl.
- **DER de la pendiente** (%) = 100·s_b/b.

> R² cercano a 1 **no** demuestra linealidad (Anscombe, 1973). Examine siempre los
> residuales y la prueba de falta de ajuste.

## 4. Diagnóstico de supuestos

| Supuesto | Prueba | Criterio orientativo |
|---|---|---|
| Normalidad de residuales | Shapiro-Wilk | p > 0.05 |
| Varianza constante | Breusch-Pagan studentizado (Koenker): n·R² de e² ~ x, χ²(1) | p > 0.05 |
| Independencia | Durbin-Watson: Σ(eᵢ − eᵢ₋₁)² / Σeᵢ² | 1.5 – 2.5 |
| Linealidad | Falta de ajuste (requiere réplicas) | p > 0.05 |
| Puntos influyentes | Distancia de Cook | Dᵢ < 4/n |
| Atípicos | Residual estandarizado rᵢ = eᵢ / (s√(1 − hᵢᵢ)) | \|rᵢ\| < 2.5 |

**Falta de ajuste:** con k niveles de concentración distintos,
SC_ep = Σ_j Σ_i (y_ij − ȳ_j)² (error puro, n − k gl),
SC_fa = SC_res − SC_ep (k − p gl), F = (SC_fa/gl_fa)/(SC_ep/gl_ep).

**Apalancamiento:** hᵢᵢ = 1/n + (xᵢ − x̄)²/S_xx (o xᵢ²/Σx² por el origen).
**Cook:** Dᵢ = rᵢ²·hᵢᵢ / (p(1 − hᵢᵢ)).

## 5. Bandas de confianza y de predicción

Para un valor x₀:

$$\hat y_0 \pm t\,s_{y/x}\sqrt{\tfrac1n+\tfrac{(x_0-\bar x)^2}{S_{xx}}}\quad\text{(confianza de la recta)}$$

$$\hat y_0 \pm t\,s_{y/x}\sqrt{1+\tfrac1n+\tfrac{(x_0-\bar x)^2}{S_{xx}}}\quad\text{(predicción de una nueva medida)}$$

En R se obtienen con `predict(fit, interval = "confidence" | "prediction")`.

## 6. Límites de detección y cuantificación (ICH Q2)

$$LOD = \frac{3.3\,s_{y/x}}{b},\qquad LOQ=\frac{10\,s_{y/x}}{b}$$

Se usa s_{y/x} como estimación de la desviación estándar de la respuesta. Si
dispone de ≥ 10 blancos, la desviación estándar del blanco es una alternativa
preferible para el LOD.

## 7. Concentración de muestras (regresión inversa)

Con m réplicas de absorbancia de media ȳ₀:

$$\hat x_0=\frac{\bar y_0-a}{b},\qquad s_{x_0}=\frac{s_{y/x}}{b}\sqrt{\frac1m+\frac1n+\frac{(\bar y_0-\bar y)^2}{b^2S_{xx}}},\qquad \hat x_0\pm t\,s_{x_0}$$

Por el origen: s_{x0} = (s_{y/x}/b)·√(1/m + ȳ₀²/(b²Σx²)).

La app marca las muestras **extrapoladas** (fuera del rango calibrado), **< LOD**
y **< LOQ**. Si diluyó la muestra, multiplique el resultado y su intervalo por el
factor de dilución.

## Referencias

- Miller, J. N., & Miller, J. C. (2018). *Statistics and Chemometrics for Analytical Chemistry* (7.ª ed.). Pearson.
- Harris, D. C. (2016). *Quantitative Chemical Analysis* (9.ª ed.). W. H. Freeman.
- Skoog, D. A., Holler, F. J., & Crouch, S. R. (2017). *Principles of Instrumental Analysis* (7.ª ed.). Cengage.
- ICH Q2(R2) (2023). *Validation of Analytical Procedures*.
- Eurachem (2014). *The Fitness for Purpose of Analytical Methods* (2.ª ed.).
- Anscombe, F. J. (1973). Graphs in statistical analysis. *The American Statistician*, 27(1), 17–21.
- Koenker, R. (1981). A note on studentizing a test for heteroscedasticity. *Journal of Econometrics*, 17(1), 107–112.
- R Core Team. *R: A Language and Environment for Statistical Computing*. R Foundation for Statistical Computing.
