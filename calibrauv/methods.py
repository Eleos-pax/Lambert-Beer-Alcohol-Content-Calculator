"""Method presets (calibrauv/methods.json) for UV-Vis assays."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

METHODS_FILE = Path(__file__).resolve().parent / "methods.json"


@lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(METHODS_FILE.read_text(encoding="utf-8"))


def methods() -> list[dict]:
    return load()["methods"]


def get(method_id: str) -> dict:
    for m in methods():
        if m["id"] == method_id:
            return m
    raise KeyError(method_id)


def acceptance() -> dict:
    return load()["acceptance"]


def reference_text(key: str) -> str:
    ref = load()["references"].get(key)
    if ref is None:
        return key
    link = ref.get("url") or (f"https://doi.org/{ref['doi']}" if ref.get("doi") else None) \
        or (f"https://pubmed.ncbi.nlm.nih.gov/{ref['pmid']}/" if ref.get("pmid") else None)
    return f"{ref['citation']}" + (f" {link}" if link else "")


def reference_markdown(key: str) -> str:
    ref = load()["references"].get(key)
    if ref is None:
        return key
    if ref.get("doi"):
        return f"{ref['citation']} [doi:{ref['doi']}](https://doi.org/{ref['doi']})"
    if ref.get("pmid"):
        return f"{ref['citation']} [PMID {ref['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{ref['pmid']}/)"
    if ref.get("url"):
        return f"[{ref['citation']}]({ref['url']})"
    return ref["citation"]


def result_unit(method: dict, standard: dict | None) -> str:
    label = method.get("result_unit_label") or ""
    if standard and "{abbr}" in label:
        return label.replace("{abbr}", standard["abbr"])
    return label
