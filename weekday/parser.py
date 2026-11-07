"""Multilingual date parsing with arbitrary-precision proleptic Gregorian weekdays.

The 400-year Gregorian cycle has 146097 days, exactly 20871 weeks. As a
result, only year modulo 400 is needed even for a year with thousands of digits.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from babel import Locale, localedata
from babel.core import UnknownLocaleError
from babel.dates import get_day_names, get_month_names

MAX_INPUT_LENGTH = 12_000
MAX_YEAR_LENGTH = 10_000
# A full two-digit-year interpretation must be explicit and predictable.
TWO_DIGIT_PIVOT = 69  # 00-68 => 2000-2068; 69-99 => 1969-1999
LANGUAGE_ALIASES = {
    "espanol": "es", "español": "es", "spanish": "es",
    "ingles": "en", "inglés": "en", "english": "en",
    "frances": "fr", "français": "fr", "french": "fr",
    "galego": "gl", "gallego": "gl", "galician": "gl",
    "portugues": "pt", "português": "pt", "portuguese": "pt",
    "deutsch": "de", "german": "de", "alemán": "de",
    "italiano": "it", "italian": "it", "russian": "ru",
}
PREFERRED_LANGUAGES = (
    "es", "en", "gl", "ca", "fr", "pt", "it", "de", "nl", "ru",
    "pl", "uk", "ar", "hi", "ja", "zh", "ko", "tr",
)
NUMERIC_FORMAT = re.compile(r"^\s*\d+\s*(?:[-/.,_]|\s)\s*\d+\s*(?:[-/.,_]|\s)\s*\d+\s*$")
EAST_ASIAN_FORMAT = re.compile(r"^\s*(\d+)\s*[年년]\s*(\d+)\s*[月월]\s*(\d+)\s*[日일]?\s*$")
NUMBER = re.compile(r"\d+")


class DateInputError(ValueError):
    """Input is unsupported, ambiguous without a chosen order, or invalid."""


@dataclass(frozen=True)
class DateResult:
    year: str
    month: int
    day: int
    weekday_index: int
    weekday_name: str
    language: str
    order: str


def _to_ascii_digits(text: str) -> str:
    """Accept Unicode decimal digits (Arabic-Indic, Devanagari, etc.)."""
    return "".join(str(unicodedata.decimal(char)) if char.isdecimal() else char for char in text)


def _fold(text: str) -> str:
    # NFKD folds accented Latin script for 'março' / 'marco', while retaining
    # non-Latin scripts (Arabic, Cyrillic, CJK, Indic, etc.).
    text = unicodedata.normalize("NFKD", text).casefold()
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).strip()


def parse_locale(value: str) -> str:
    """Resolve a CLDR locale such as es, gl, pt_BR or zh_Hans_CN."""
    value = value.strip()
    if not value:
        raise DateInputError("Indique un idioma o utilice la detección automática.")
    normalized = LANGUAGE_ALIASES.get(value.casefold(), value.replace("-", "_"))
    try:
        locale = Locale.parse(normalized)
    except (UnknownLocaleError, ValueError) as exc:
        raise DateInputError(f"Idioma no reconocido: {value!r}. Use un código como es, en, gl o pt_BR.") from exc
    return str(locale)


def _browser_locale(header: str) -> str:
    # Ignore untrusted q values entirely: only locale fallback affects output.
    for part in header.split(",")[:12]:
        candidate = part.split(";", 1)[0].strip()
        if candidate == "*" or not candidate:
            continue
        try:
            return parse_locale(candidate)
        except DateInputError:
            continue
    return "es"


@lru_cache(maxsize=1)
def _month_lexicon() -> dict[str, tuple[tuple[int, str], ...]]:
    """Build month-name aliases from CLDR base locales (hundreds of languages)."""
    found: dict[str, set[tuple[int, str]]] = {}
    locale_codes = sorted(set(
        locale for locale in localedata.locale_identifiers()
        if "_" not in locale and locale != "root"
    ) | set(PREFERRED_LANGUAGES))
    for locale_code in locale_codes:
        for context in ("format", "stand-alone"):
            for width in ("wide", "abbreviated"):
                try:
                    months = get_month_names(width=width, context=context, locale=locale_code)
                except (UnknownLocaleError, KeyError, ValueError):
                    continue
                for month, name in months.items():
                    alias = _fold(str(name))
                    # Month names such as '1' or '1月' should not match a year,
                    # and one-letter abbreviations are too ambiguous.
                    if len(alias) < 2 or not any(ch.isalpha() for ch in alias):
                        continue
                    found.setdefault(alias, set()).add((int(month), locale_code))
    return {alias: tuple(sorted(options)) for alias, options in found.items()}


def _detect_month(text: str, preferences: tuple[str, ...]) -> tuple[int, str] | None:
    words = _fold(text).split()
    matches: list[tuple[int, int, int, str]] = []
    priority_map = {lang: idx for idx, lang in enumerate(dict.fromkeys((*preferences, *PREFERRED_LANGUAGES)))}
    lexicon = _month_lexicon()
    for width in range(1, min(4, len(words)) + 1):
        for start in range(len(words) - width + 1):
            alias = " ".join(words[start:start + width])
            for month, language in lexicon.get(alias, ()):
                # Prefer more specific month names, then user/browser languages.
                language_root = language.split("_", 1)[0]
                priority = priority_map.get(language, priority_map.get(language_root, 1000))
                matches.append((priority, -len(alias), month, language))
    if not matches:
        return None
    matches.sort()
    _, _, month, language = matches[0]
    return month, language


def _year(year: str) -> tuple[str, int]:
    if len(year) > MAX_YEAR_LENGTH:
        raise DateInputError(f"El año no puede superar {MAX_YEAR_LENGTH} cifras.")
    if len(year) == 2:
        number = int(year)
        year = str(2000 + number if number < TWO_DIGIT_PIVOT else 1900 + number)
    else:
        year = year.lstrip("0") or "0"
    if year == "0":
        raise DateInputError("El año 0 no existe en el calendario gregoriano convencional.")
    remainder = 0
    for digit in year:
        remainder = (remainder * 10 + ord(digit) - 48) % 400
    return year, remainder or 400


def _weekday(representative_year: int, month: int, day: int) -> int:
    leap = representative_year % 4 == 0 and (representative_year % 100 != 0 or representative_year % 400 == 0)
    lengths = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if not 1 <= month <= 12:
        raise DateInputError("El mes debe estar entre 1 y 12.")
    if not 1 <= day <= lengths[month - 1]:
        raise DateInputError("Día no válido para ese mes y año (compruebe los años bisiestos).")
    y = representative_year - 1
    days_since_monday = 365 * y + y // 4 - y // 100 + y // 400
    days_since_monday += sum(lengths[:month - 1]) + day - 1
    return days_since_monday % 7


def _day_month_year(raw: str, month_detected: tuple[int, str] | None, order: str, language: str) -> tuple[str, int, int, str]:
    if match := EAST_ASIAN_FORMAT.fullmatch(raw):
        year, month, day = match.groups()
        return year, int(month), int(day), "YMD"

    if month_detected:
        month = month_detected[0]
        numerals = NUMBER.findall(raw)
        if len(numerals) != 2:
            raise DateInputError("Indique un día y un año junto al nombre del mes.")
        a, b = numerals
        if len(a) >= 3 or (int(a) > 31 and int(b) <= 31):
            return a, month, int(b), "YMD"
        return b, month, int(a), "DMY"

    if not NUMERIC_FORMAT.fullmatch(raw):
        raise DateInputError("Formato no reconocido. Ejemplos: 14 de febrero de 2011, 2015-03-14 o 14/3/2015.")
    parts = NUMBER.findall(raw)
    a, b, c = parts
    if len(a) >= 4 or (len(a) >= 3 and len(c) <= 2):
        selected = "YMD"
    elif len(c) >= 3:
        selected = order if order in ("DMY", "MDY") else ("MDY" if language == "en_US" else "DMY")
    else:
        selected = order if order != "auto" else ("MDY" if language == "en_US" else "DMY")
    if order == "YMD":
        selected = "YMD"
    if selected == "YMD":
        year, month, day = a, int(b), int(c)
    elif selected == "MDY":
        year, month, day = c, int(a), int(b)
    else:
        year, month, day = c, int(b), int(a)
    return year, month, day, selected


def parse_date(text: str, *, language: str = "", order: str = "auto", accept_language: str = "") -> DateResult:
    """Parse a date string and translate its weekday using CLDR.

    Numeric dates without a year-first marker use DMY by default, except
    en_US with two-digit years. Pick 'MDY' explicitly for US-style input.
    """
    if not isinstance(text, str) or not text.strip():
        raise DateInputError("Introduzca una fecha.")
    if len(text) > MAX_INPUT_LENGTH:
        raise DateInputError(f"La entrada no puede superar {MAX_INPUT_LENGTH} caracteres.")
    if order not in ("auto", "DMY", "MDY", "YMD"):
        raise DateInputError("Orden de fecha no válido.")
    browser = _browser_locale(accept_language)
    specified = parse_locale(language) if language.strip() else None
    clean = _to_ascii_digits(text.strip())
    # Guard against dates that contain control characters.
    if any(unicodedata.category(ch) == "Cc" for ch in clean):
        raise DateInputError("La fecha contiene caracteres de control.")
    preferences = tuple(filter(None, (specified, browser)))
    matched_month = _detect_month(clean, preferences)
    year, month, day, chosen_order = _day_month_year(clean, matched_month, order, browser if not specified else specified)
    normalized_year, representative = _year(year)
    weekday_index = _weekday(representative, month, day)
    locale = specified or (matched_month[1] if matched_month else browser)
    try:
        weekday_name = str(get_day_names(width="wide", context="format", locale=locale)[weekday_index])
    except (KeyError, ValueError) as exc:
        raise DateInputError("No se encontró el nombre del día en ese idioma.") from exc
    return DateResult(
        year=normalized_year, month=month, day=day, weekday_index=weekday_index,
        weekday_name=weekday_name, language=locale, order=chosen_order,
    )
