"""Every t("...") text in the code must have a Spanish translation with the same placeholders."""

import ast
import re
from pathlib import Path

from calibrauv import analysis, i18n, methods
from calibrauv.lang_es import ES
from calibrauv.report import AI_NOTICE

ROOT = Path(__file__).resolve().parent.parent


def translatable_keys():
    keys = set()
    for f in [ROOT / "app.py", *sorted((ROOT / "calibrauv").glob("*.py"))]:
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "t" and node.args
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                keys.add(node.args[0].value)
    acc = methods.acceptance()
    keys |= set(analysis.LOD_BASES) | set(acc["rsd_criteria_pct"]) | set(acc["recovery_criteria_pct"])
    keys |= {acc["recovery_source"], AI_NOTICE}
    return keys


def test_all_texts_translated():
    missing = sorted(translatable_keys() - set(ES))
    assert not missing, f"Missing Spanish translations: {missing}"


def test_placeholders_match():
    ph = lambda s: sorted(set(re.findall(r"\{([a-z]*)\}", s)))  # noqa: E731
    bad = [k for k, v in ES.items() if ph(k) != ph(v)]
    assert not bad, bad


def test_switch_language():
    i18n.set_lang("es")
    try:
        assert i18n.t("Slope b") == "Pendiente b"
        assert i18n.t("Only {n} blank readings; ICH Q2 suggests at least 10.", n=4).startswith("Solo 4")
        m = methods.get("LAB_TPC_FOLIN_NAOH")
        assert i18n.field(m, "name").startswith("Protocolo del laboratorio")
        assert methods.result_unit(m, m["standards"][0]) == "mg EAG/g de extracto"
    finally:
        i18n.set_lang("en")
    assert i18n.t("Slope b") == "Slope b"


def test_spanish_fields_in_methods():
    for m in methods.methods():
        assert m.get("name_es"), m["id"]
        for v in m.get("variants", []):
            assert v.get("name_es"), (m["id"], v["name"])
        if m.get("warnings"):
            assert len(m.get("warnings_es", [])) == len(m["warnings"]), m["id"]
