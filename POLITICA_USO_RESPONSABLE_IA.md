# Política de uso responsable de la inteligencia artificial

**Proyecto:** CalibraUV · **Versión de la política:** 1.0 · **Fecha:** noviembre de 2026

## 1. Declaración de transparencia

CalibraUV fue **diseñada y programada en su mayoría con el apoyo de Claude**, un
asistente de inteligencia artificial desarrollado por Anthropic. La IA participó en:

- el diseño de la arquitectura (motor estadístico en R + interfaz en Python),
- la escritura del código fuente, las pruebas automáticas y los instaladores,
- la redacción de la documentación y de esta misma política.

Las personas responsables del proyecto definieron los requisitos, revisaron el
trabajo, lo ejecutaron y son quienes responden por él. Los commits generados con
asistencia de IA lo indican con la línea `Co-Authored-By` correspondiente.

## 2. Principios

1. **Responsabilidad humana.** La IA es una herramienta; la responsabilidad
   científica, técnica y ética de los resultados es siempre de las personas que
   usan, mantienen o contribuyen al software.
2. **Verificabilidad.** Todo cálculo debe poder reproducirse. Por eso:
   - el motor de referencia es `stats::lm` de R, un estándar ampliamente validado;
   - un motor independiente en Python (NumPy/SciPy) repite los mismos cálculos, y
     las pruebas automáticas exigen que **ambos coincidan** (tolerancia relativa 10⁻⁶);
   - las fórmulas están documentadas en [`docs/TEORIA.md`](docs/TEORIA.md) con
     sus referencias bibliográficas.
3. **Transparencia.** La app muestra en su interfaz y en cada reporte que fue
   desarrollada con apoyo de IA. No se debe ocultar ni eliminar este aviso en
   redistribuciones.
4. **Privacidad.** CalibraUV funciona **sin conexión a internet** y **no envía
   datos a ningún servicio de IA** ni a terceros. Sus datos de laboratorio se
   procesan solo en su computadora. (Streamlit se configura con
   `gatherUsageStats = false`).
5. **Honestidad sobre las limitaciones.** El código generado por IA puede contener
   errores sutiles. Los criterios de interpretación incluidos (p. ej. R² ≥ 0.995)
   son orientativos y no reemplazan los criterios de aceptación de su método
   validado ni la normativa aplicable (ICH Q2(R2), ISO/IEC 17025, farmacopeas, etc.).

## 3. Uso responsable por parte de las personas usuarias

- **Verifique** los resultados críticos con un segundo método (hoja de cálculo
  validada, otro software o cálculo manual) antes de usarlos en decisiones
  regulatorias, clínicas, ambientales, legales o comerciales.
- **No elimine** puntos de la curva solo porque el software los marque como
  atípicos: hágalo únicamente con una causa experimental justificada y documentada.
- **No presente** los reportes como si hubieran sido generados por un sistema
  validado si su organización no lo ha validado formalmente.
- **En contextos educativos**, use la herramienta para comprender la estadística
  de la calibración, no para sustituir el aprendizaje: revise las fórmulas,
  compárelas con su propio cálculo y cite el software si lo utiliza en un trabajo.

## 4. Contribuciones asistidas por IA

Se aceptan contribuciones escritas con ayuda de herramientas de IA, siempre que:

1. la persona que contribuye **entienda y pueda explicar** cada cambio;
2. se declare el uso de IA en la descripción del *pull request*;
3. los cambios en cálculos incluyan pruebas y, cuando aplique, la referencia
   bibliográfica de la fórmula;
4. las pruebas automáticas pasen en Windows y Linux;
5. no se incluya código, datos o textos con derechos de terceros sin licencia compatible.

## 5. Reporte de problemas

Si encuentra un error de cálculo, un resultado dudoso o un uso indebido de la
herramienta, abra un *issue* en el repositorio indicando: datos de entrada (si
puede compartirlos), resultado esperado, resultado obtenido, sistema operativo y
versiones de R y Python. Los errores de cálculo tienen máxima prioridad.

## 6. Revisión de esta política

Esta política se revisará cuando cambien de forma significativa las herramientas
de IA utilizadas o el alcance del proyecto. Las sugerencias son bienvenidas.
