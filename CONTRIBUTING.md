# Cómo contribuir a CalibraUV

¡Gracias por su interés! Algunas pautas:

1. **Abra un issue** antes de cambios grandes para discutir la idea.
2. **Cálculos:** cualquier cambio estadístico debe implementarse **en ambos motores**
   (`r/calibracion.R` y `calibrauv/motor_python.py`), con la misma clave en el JSON de
   salida, una prueba en `tests/` y la fórmula con su referencia en `docs/TEORIA.md`.
3. **Compatibilidad:** el script de R debe seguir usando solo R base + `stats`. El código
   debe funcionar en Windows y Linux (use `pathlib`, no rutas fijas).
4. **Pruebas:** `python -m pytest -v` debe pasar (incluye la comparación R vs Python).
5. **Uso de IA:** está permitido; declárelo en el pull request y asegúrese de entender
   cada línea. Ver [POLITICA_USO_RESPONSABLE_IA.md](POLITICA_USO_RESPONSABLE_IA.md).
6. **Idioma:** la interfaz y la documentación están en español.

Ideas pendientes: regresión ponderada (1/x, 1/x²), prueba de Mandel para linealidad,
adición estándar, LOD a partir de blancos, importación directa de archivos de
espectrofotómetros y traducción al inglés.
