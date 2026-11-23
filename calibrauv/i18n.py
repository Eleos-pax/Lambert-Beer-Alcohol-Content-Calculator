"""Interface language (English / Spanish).

Usage:  from calibrauv.i18n import t, field
        t("Slope b")                     -> "Pendiente b" when the language is Spanish
        t("{n} outliers", n=3)           -> formatted text
        field(method, "name")            -> method["name_es"] if Spanish and available

English text is the key; missing translations fall back to English.
The Spanish dictionary lives in calibrauv/lang_es.py.
"""

from __future__ import annotations

from .lang_es import ES

LANGUAGES = {"en": "English", "es": "Español"}
_lang = "en"


def set_lang(lang: str) -> None:
    global _lang
    _lang = lang if lang in LANGUAGES else "en"


def get_lang() -> str:
    return _lang


def t(text: str, **kwargs) -> str:
    out = ES.get(text, text) if _lang == "es" else text
    return out.format(**kwargs) if kwargs else out


def field(obj: dict | None, key: str, default=None):
    if not obj:
        return default
    if _lang == "es" and obj.get(f"{key}_es") is not None:
        return obj[f"{key}_es"]
    return obj.get(key, default)
