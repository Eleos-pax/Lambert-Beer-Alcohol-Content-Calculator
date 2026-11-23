"""Python-to-R bridge: runs r/calibration.R through Rscript.

A subprocess with CSV/JSON files is used (instead of rpy2) because it works the
same on Windows and Linux and needs nothing to be compiled.
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

R_SCRIPT = Path(__file__).resolve().parent.parent / "r" / "calibration.R"


class REngineError(RuntimeError):
    """Error while running the R statistical engine."""


def find_rscript() -> str | None:
    """Locate Rscript on Windows or Linux.

    Order: CALIBRAUV_RSCRIPT environment variable, system PATH and, on Windows,
    the standard R installation folders (C:\\Program Files\\R).
    """
    env = os.environ.get("CALIBRAUV_RSCRIPT")
    if env and Path(env).is_file():
        return env
    found = shutil.which("Rscript")
    if found:
        return found
    if platform.system() == "Windows":
        bases = [os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 os.path.expandvars(r"%LOCALAPPDATA%\Programs\R")]
        candidates: list[str] = []
        for base in bases:
            candidates += glob.glob(os.path.join(base, "R", "R-*", "bin", "Rscript.exe"))
            candidates += glob.glob(os.path.join(base, "R-*", "bin", "Rscript.exe"))
        if candidates:
            # Most recent version (sorted by version number)
            def key(p: str):
                ver = Path(p).parent.parent.name.replace("R-", "")
                return [int(t) if t.isdigit() else 0 for t in ver.split(".")]
            return sorted(candidates, key=key)[-1]
    else:
        for p in ("/usr/bin/Rscript", "/usr/local/bin/Rscript", "/opt/R/bin/Rscript"):
            if Path(p).is_file():
                return p
    return None


def compute_r(standards: pd.DataFrame, samples: pd.DataFrame | None = None,
              conf: float = 0.95, origin: bool = False, path_length: float = 1.0,
              n_grid: int = 100, rscript: str | None = None,
              timeout: int = 60) -> dict:
    """Run the regression in R and return the results dictionary."""
    rscript = rscript or find_rscript()
    if not rscript:
        raise REngineError("Rscript was not found. Install R or use the Python engine.")

    with tempfile.TemporaryDirectory(prefix="calibrauv_") as tmp:
        f_std = Path(tmp) / "standards.csv"
        f_out = Path(tmp) / "result.json"
        standards.iloc[:, :2].set_axis(["x", "y"], axis=1).to_csv(
            f_std, index=False, encoding="utf-8")
        args = [rscript, "--vanilla", str(R_SCRIPT), f"--data={f_std}",
                f"--conf={conf}", f"--origin={int(origin)}",
                f"--path={path_length}", f"--grid={n_grid}", f"--out={f_out}"]
        if samples is not None and len(samples) > 0:
            f_unk = Path(tmp) / "samples.csv"
            samples[["sample", "absorbance"]].to_csv(f_unk, index=False, encoding="utf-8")
            args.append(f"--unknowns={f_unk}")

        flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        proc = subprocess.run(args, capture_output=True, timeout=timeout,
                              creationflags=flags)
        output = f_out.read_text(encoding="utf-8") if f_out.exists() else \
            proc.stdout.decode("utf-8", errors="replace")
        try:
            res = json.loads(output)
        except json.JSONDecodeError as exc:
            err = proc.stderr.decode("utf-8", errors="replace")
            raise REngineError(f"R did not return valid results.\n{err}") from exc
    if "error" in res:
        raise REngineError(res["error"])
    return res
