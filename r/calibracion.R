#!/usr/bin/env Rscript
# =============================================================================
#  CalibraUV - Motor estadístico en R
#  Curva de calibración por espectroscopía UV-Vis (ley de Lambert-Beer)
#
#  Solo usa R base + el paquete 'stats' (incluido en toda instalación de R),
#  así funciona igual en Windows y en Linux sin instalar paquetes adicionales.
#
#  Uso desde la terminal:
#    Rscript calibracion.R --data=estandares.csv [--unknowns=muestras.csv]
#            [--conf=0.95] [--origin=0] [--path=1] [--grid=100] [--out=res.json]
#
#  estandares.csv : las dos primeras columnas numéricas = concentración, absorbancia
#  muestras.csv   : columnas 'muestra' y 'absorbancia' (réplicas = filas repetidas)
#
#  Licencia: MIT. Diseñado en su mayoría con apoyo de Claude (Anthropic),
#  revisado por humanos. Ver POLITICA_USO_RESPONSABLE_IA.md
# =============================================================================

suppressWarnings(suppressMessages(library(stats)))

# ---------------------------------------------------------------- argumentos --
parse_args <- function(args) {
  opts <- list()
  for (a in args) {
    pos <- regexpr("=", a, fixed = TRUE)
    if (pos > 0) {
      key <- sub("^--", "", substr(a, 1, pos - 1))
      opts[[key]] <- substr(a, pos + 1, nchar(a))
    } else {
      opts[[sub("^--", "", a)]] <- "1"
    }
  }
  opts
}

opt <- function(opts, key, default) if (is.null(opts[[key]])) default else opts[[key]]

# ------------------------------------------------- serializador JSON (ASCII) --
# Escapamos todo carácter no ASCII como \uXXXX para que la salida sea idéntica
# en Windows (codificación nativa CP-1252) y en Linux (UTF-8).
json_str <- function(s) {
  vapply(enc2utf8(as.character(s)), function(one) {
    if (is.na(one)) return("null")
    cps <- utf8ToInt(one)
    out <- character(length(cps))
    for (i in seq_along(cps)) {
      cp <- cps[i]
      ch <- intToUtf8(cp)
      out[i] <- if (cp == 34) "\\\"" else if (cp == 92) "\\\\" else
        if (cp == 10) "\\n" else if (cp == 13) "\\r" else if (cp == 9) "\\t" else
        if (cp < 32) sprintf("\\u%04x", cp) else if (cp < 128) ch else
        if (cp < 65536) sprintf("\\u%04x", cp) else {
          v <- cp - 65536
          sprintf("\\u%04x\\u%04x", 55296 + v %/% 1024, 56320 + v %% 1024)
        }
    }
    paste0("\"", paste(out, collapse = ""), "\"")
  }, "", USE.NAMES = FALSE)
}

arr <- function(v) structure(v, json_array = TRUE)  # fuerza arreglo JSON

to_json <- function(x) {
  if (is.null(x)) return("null")
  if (is.list(x)) {
    nms <- names(x)
    if (!is.null(nms) && length(x) > 0 && all(nms != "")) {
      items <- vapply(seq_along(x), function(i)
        paste0(json_str(nms[i]), ":", to_json(x[[i]])), "")
      return(paste0("{", paste(items, collapse = ","), "}"))
    }
    return(paste0("[", paste(vapply(x, to_json, ""), collapse = ","), "]"))
  }
  is_arr <- isTRUE(attr(x, "json_array"))
  if (is.character(x)) {
    v <- json_str(x)
  } else if (is.logical(x)) {
    v <- ifelse(is.na(x), "null", ifelse(x, "true", "false"))
  } else {
    x <- as.numeric(x)
    v <- ifelse(is.finite(x), formatC(x, digits = 15, format = "g"), "null")
    v <- gsub(" ", "", v)
  }
  if (length(x) == 1 && !is_arr) v else paste0("[", paste(v, collapse = ","), "]")
}

fail <- function(msg) {
  cat(to_json(list(error = msg)), "\n")
  quit(status = 2, save = "no")
}

# --------------------------------------------------------------------- datos --
opts   <- parse_args(commandArgs(trailingOnly = TRUE))
f_data <- opt(opts, "data", NULL)
if (is.null(f_data)) fail("Falta el argumento --data=archivo.csv")
conf   <- as.numeric(opt(opts, "conf", "0.95"))
origin <- opt(opts, "origin", "0") %in% c("1", "TRUE", "true", "si")
path_l <- as.numeric(opt(opts, "path", "1"))
n_grid <- as.integer(opt(opts, "grid", "100"))

df <- tryCatch(read.csv(f_data, fileEncoding = "UTF-8", check.names = FALSE),
               error = function(e) fail(paste("No se pudo leer el CSV:", conditionMessage(e))))
num_cols <- which(vapply(df, is.numeric, TRUE))
if (length(num_cols) < 2) fail("El CSV necesita al menos dos columnas numéricas (concentración, absorbancia)")
x <- df[[num_cols[1]]]
y <- df[[num_cols[2]]]
ok <- is.finite(x) & is.finite(y)
x <- x[ok]; y <- y[ok]
n <- length(x)
if (n < 3) fail("Se necesitan al menos 3 estándares válidos")
if (length(unique(x)) < 2) fail("Se necesitan al menos 2 concentraciones distintas")

# ----------------------------------------------------------------- regresión --
fit <- if (origin) lm(y ~ 0 + x) else lm(y ~ x)
sm  <- summary(fit)
co  <- coef(sm)
ci  <- confint(fit, level = conf)
p   <- length(coef(fit))
df_res <- n - p
if (df_res < 1) fail("Grados de libertad insuficientes: agregue más estándares")

coef_row <- function(name) list(
  estimate = co[name, 1], se = co[name, 2], t = co[name, 3], p = co[name, 4],
  ci_low = ci[name, 1], ci_high = ci[name, 2])

b <- unname(coef(fit)["x"])
a <- if (origin) 0 else unname(coef(fit)["(Intercept)"])
s_yx <- sm$sigma
x_mean <- mean(x); y_mean <- mean(y)
sxx <- sum((x - x_mean)^2)

an <- anova(fit)
anova_out <- list(
  df_reg = an$Df[1], ss_reg = an$`Sum Sq`[1], ms_reg = an$`Mean Sq`[1],
  df_res = an$Df[2], ss_res = an$`Sum Sq`[2], ms_res = an$`Mean Sq`[2],
  f = an$`F value`[1], p = an$`Pr(>F)`[1])

# --------------------------------------------------------------- diagnóstico --
e <- residuals(fit)
shap <- tryCatch(shapiro.test(e), error = function(err) NULL)
dw <- sum(diff(e)^2) / sum(e^2)

# Breusch-Pagan studentizado (Koenker): n * R^2 de e^2 ~ x
bp <- tryCatch({
  aux <- summary(lm(I(e^2) ~ x))
  stat <- n * aux$r.squared
  list(stat = stat, p = pchisq(stat, df = 1, lower.tail = FALSE))
}, error = function(err) list(stat = NA, p = NA))

# Falta de ajuste (requiere réplicas)
lof <- NULL
groups <- split(y, x)
k <- length(groups)
df_pe <- n - k
df_lof <- k - p
if (df_pe > 0 && df_lof > 0) {
  ss_pe  <- sum(vapply(groups, function(g) sum((g - mean(g))^2), 0))
  ss_lof <- anova_out$ss_res - ss_pe
  f_lof  <- (ss_lof / df_lof) / (ss_pe / df_pe)
  lof <- list(ss_lof = ss_lof, df_lof = df_lof, ss_pe = ss_pe, df_pe = df_pe,
              f = f_lof, p = pf(f_lof, df_lof, df_pe, lower.tail = FALSE))
}

# ------------------------------------------------------------ bandas (grid) --
gx <- seq(min(0, min(x)), max(x) * 1.05, length.out = n_grid)
pc <- predict(fit, newdata = data.frame(x = gx), interval = "confidence", level = conf)
pp <- predict(fit, newdata = data.frame(x = gx), interval = "prediction", level = conf)

# --------------------------------------------- límites y absortividad molar --
lod <- 3.3 * s_yx / b
loq <- 10  * s_yx / b
tval <- qt(1 - (1 - conf) / 2, df_res)

# ------------------------------------------------- muestras desconocidas -----
unknowns <- list()
f_unk <- opt(opts, "unknowns", NULL)
if (!is.null(f_unk) && file.exists(f_unk)) {
  du <- read.csv(f_unk, fileEncoding = "UTF-8", check.names = FALSE,
                 stringsAsFactors = FALSE)
  if (nrow(du) > 0) {
    names(du) <- tolower(names(du))
    if (!"muestra" %in% names(du)) du$muestra <- paste0("M", seq_len(nrow(du)))
    ycol <- if ("absorbancia" %in% names(du)) "absorbancia" else
      names(du)[which(vapply(du, is.numeric, TRUE))[1]]
    du <- du[is.finite(du[[ycol]]), ]
    for (nm in unique(du$muestra)) {
      yy <- du[[ycol]][du$muestra == nm]
      m  <- length(yy)
      y0 <- mean(yy)
      x0 <- (y0 - a) / b
      sx0 <- if (origin) {
        (s_yx / abs(b)) * sqrt(1 / m + y0^2 / (b^2 * sum(x^2)))
      } else {
        (s_yx / abs(b)) * sqrt(1 / m + 1 / n + (y0 - y_mean)^2 / (b^2 * sxx))
      }
      unknowns[[length(unknowns) + 1]] <- list(
        sample = as.character(nm), m = m, y_mean = y0,
        y_sd = if (m > 1) sd(yy) else NA,
        x0 = x0, s_x0 = sx0, ci_low = x0 - tval * sx0, ci_high = x0 + tval * sx0,
        rsd_pct = 100 * sx0 / abs(x0),
        extrapolated = (x0 < min(x) || x0 > max(x)),
        below_lod = (x0 < lod), below_loq = (x0 < loq))
    }
  }
}

# ------------------------------------------------------------------- salida --
res <- list(
  engine = paste0("R ", R.version$major, ".", R.version$minor, " (stats::lm)"),
  n = n, p = p, df_resid = df_res, conf_level = conf, origin = origin,
  t_crit = tval,
  coefficients = list(
    slope = coef_row("x"),
    intercept = if (origin) NULL else coef_row("(Intercept)")),
  r = cor(x, y), r_squared = sm$r.squared,
  adj_r_squared = sm$adj.r.squared, s_yx = s_yx,
  f_stat = unname(sm$fstatistic[1]),
  f_p = unname(pf(sm$fstatistic[1], sm$fstatistic[2], sm$fstatistic[3], lower.tail = FALSE)),
  anova = anova_out,
  lod = lod, loq = loq, path_length = path_l, absorptivity = b / path_l,
  slope_rsd_pct = 100 * co["x", 2] / abs(b),
  x_mean = x_mean, y_mean = y_mean, sxx = sxx,
  x_min = min(x), x_max = max(x),
  diagnostics = list(
    shapiro_w = if (is.null(shap)) NA else unname(shap$statistic),
    shapiro_p = if (is.null(shap)) NA else shap$p.value,
    durbin_watson = dw, bp_stat = bp$stat, bp_p = bp$p, lack_of_fit = lof),
  points = list(
    x = arr(x), y = arr(y), fitted = arr(unname(fitted(fit))),
    residuals = arr(unname(e)), std_residuals = arr(unname(rstandard(fit))),
    leverage = arr(unname(hatvalues(fit))), cooks = arr(unname(cooks.distance(fit)))),
  band = list(
    x = arr(gx), fit = arr(unname(pc[, 1])),
    conf_low = arr(unname(pc[, 2])), conf_high = arr(unname(pc[, 3])),
    pred_low = arr(unname(pp[, 2])), pred_high = arr(unname(pp[, 3]))),
  unknowns = unknowns)

json <- to_json(res)
f_out <- opt(opts, "out", NULL)
if (is.null(f_out)) cat(json, "\n") else writeLines(json, f_out, useBytes = TRUE)
