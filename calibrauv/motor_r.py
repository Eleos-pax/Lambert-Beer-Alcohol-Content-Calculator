"""Puente entre Python y R: ejecuta r/calibracion.R con Rscript.

Se usa un subproceso con archivos CSV/JSON (en lugar de rpy2) porque funciona
igual en Windows y Linux y no requiere compilar nada.
"""

from __future__ import annotations

import glob
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

SCRIPT_R = Path(__file__).resolve().parent.parent / "r" / "calibracion.R"


class ErrorMotorR(RuntimeError):
    """Error al ejecutar el motor estadístico de R."""


def buscar_rscript() -> str | None:
    """Localiza Rscript en Windows o Linux.

    Orden: variable de entorno CALIBRAUV_RSCRIPT, PATH del sistema y, en
    Windows, las carpetas de instalación estándar de R (C:\\Program Files\\R).
    """
    env = os.environ.get("CALIBRAUV_RSCRIPT")
    if env and Path(env).is_file():
        return env
    encontrado = shutil.which("Rscript")
    if encontrado:
        return encontrado
    if platform.system() == "Windows":
        bases = [os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 os.path.expandvars(r"%LOCALAPPDATA%\Programs\R")]
        candidatos: list[str] = []
        for base in bases:
            candidatos += glob.glob(os.path.join(base, "R", "R-*", "bin", "Rscript.exe"))
            candidatos += glob.glob(os.path.join(base, "R-*", "bin", "Rscript.exe"))
        if candidatos:
            # La versión más reciente (orden por número de versión)
            def clave(p: str):
                ver = Path(p).parent.parent.name.replace("R-", "")
                return [int(t) if t.isdigit() else 0 for t in ver.split(".")]
            return sorted(candidatos, key=clave)[-1]
    else:
        for p in ("/usr/bin/Rscript", "/usr/local/bin/Rscript", "/opt/R/bin/Rscript"):
            if Path(p).is_file():
                return p
    return None


def calcular_r(estandares: pd.DataFrame, muestras: pd.DataFrame | None = None,
               conf: float = 0.95, origen: bool = False, paso_optico: float = 1.0,
               n_grid: int = 100, rscript: str | None = None,
               timeout: int = 60) -> dict:
    """Ejecuta la regresión en R y devuelve el diccionario de resultados."""
    rscript = rscript or buscar_rscript()
    if not rscript:
        raise ErrorMotorR("No se encontró Rscript. Instale R o use el motor Python.")

    with tempfile.TemporaryDirectory(prefix="calibrauv_") as tmp:
        f_std = Path(tmp) / "estandares.csv"
        f_out = Path(tmp) / "resultado.json"
        estandares.iloc[:, :2].set_axis(["x", "y"], axis=1).to_csv(
            f_std, index=False, encoding="utf-8")
        args = [rscript, "--vanilla", str(SCRIPT_R), f"--data={f_std}",
                f"--conf={conf}", f"--origin={int(origen)}",
                f"--path={paso_optico}", f"--grid={n_grid}", f"--out={f_out}"]
        if muestras is not None and len(muestras) > 0:
            f_unk = Path(tmp) / "muestras.csv"
            muestras[["muestra", "absorbancia"]].to_csv(f_unk, index=False, encoding="utf-8")
            args.append(f"--unknowns={f_unk}")

        flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        proc = subprocess.run(args, capture_output=True, timeout=timeout,
                              creationflags=flags)
        salida = f_out.read_text(encoding="utf-8") if f_out.exists() else \
            proc.stdout.decode("utf-8", errors="replace")
        try:
            res = json.loads(salida)
        except json.JSONDecodeError as exc:
            err = proc.stderr.decode("utf-8", errors="replace")
            raise ErrorMotorR(f"R no devolvió resultados válidos.\n{err}") from exc
    if "error" in res:
        raise ErrorMotorR(res["error"])
    return res
