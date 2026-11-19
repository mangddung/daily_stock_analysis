# -*- coding: utf-8 -*-
"""Translate market labels (sector / concept names) into the report language, cached on disk.

Sector names come in the market's own language (A-share 建筑安装业, TOPIX-17 食品, KOSPI 200 금융 ...).
Reports show the translation only (ticker suffix kept). Each name is translated once per language with a single
batched LLM call and cached forever under data/cache/label_translations.json. Fail-open: any
error leaves the names as they are.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "cache" / "label_translations.json"
LANGUAGE_NAMES = {"zh": "Simplified Chinese", "en": "English", "ko": "Korean"}
MAX_LABEL_CHARS = 60
# "食品 (1617)" -> base "食品", suffix " (1617)": ticker suffixes are kept, not translated.
_SUFFIX_RE = re.compile(r"^(?P<base>.*?)(?P<suffix>\s\([A-Za-z0-9.^]+\))?$")

PROMPT = (
    "Translate these stock-market sector / theme names into {language}. Use the standard financial "
    "term for each. If a name is already in {language}, return it unchanged.\n"
    "Return only a JSON object that maps every input name exactly to its translation.\n\n"
    "{names}"
)

_lock = threading.Lock()


def _read(path: Path) -> Dict[str, Dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path: Path, data: Dict[str, Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _parse(reply: str, wanted: Iterable[str]) -> Dict[str, str]:
    match = re.search(r"\{.*\}", reply or "", re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return {}
    wanted = set(wanted)
    return {
        key: value.strip()
        for key, value in (data.items() if isinstance(data, dict) else [])
        if key in wanted and isinstance(value, str) and 0 < len(value.strip()) <= MAX_LABEL_CHARS
    }


def translate_labels(
    names: Iterable[str],
    language: str,
    generate: Callable[[str], Optional[str]],
    cache_path: Path = CACHE_PATH,
) -> Dict[str, str]:
    """Map each base name to its translation in ``language`` (missing on failure)."""
    if language not in LANGUAGE_NAMES:
        return {}
    names = sorted({name for name in names if name})
    with _lock:
        cache = _read(cache_path)
        known = cache.get(language, {})
        missing = [name for name in names if name not in known]
        if missing:
            try:
                reply = generate(PROMPT.format(language=LANGUAGE_NAMES[language],
                                               names=json.dumps(missing, ensure_ascii=False)))
                fresh = _parse(reply or "", missing)
            except Exception as exc:
                logger.warning("[label-translation] %s failed: %s", language, exc)
                fresh = {}
            if fresh:
                known = {**known, **fresh}
                cache[language] = known
                _write(cache_path, cache)
    return {name: known[name] for name in names if name in known}


def localize_rows(rows: List[Dict], language: str, generate: Callable[[str], Optional[str]],
                  cache_path: Path = CACHE_PATH) -> None:
    """Rewrite each row's ``name`` in place to its translation; untranslated names stay as is."""
    parts = {}
    for row in rows:
        name = str(row.get("name") or "")
        match = _SUFFIX_RE.match(name)
        parts[name] = (match.group("base").strip(), match.group("suffix") or "")
    translations = translate_labels((base for base, _ in parts.values()), language, generate, cache_path)
    for row in rows:
        name = str(row.get("name") or "")
        base, suffix = parts.get(name, (name, ""))
        translated = translations.get(base, "")
        if translated:
            row["name"] = f"{translated}{suffix}"


if __name__ == "__main__":
    import tempfile

    rows = [{"name": "食品 (1617)"}, {"name": "銀行 (1631)"}, {"name": "IT (139260)"}]
    replies = iter(['{"食品": "식품", "銀行": "은행", "IT": "IT"}'])
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp) / "t.json"
        localize_rows(rows, "ko", lambda prompt: next(replies), cache)
        assert [r["name"] for r in rows] == ["식품 (1617)", "은행 (1631)", "IT (139260)"], rows
        again = [{"name": "食品 (1617)"}]
        localize_rows(again, "ko", lambda prompt: (_ for _ in ()).throw(AssertionError("cached")), cache)
        assert again[0]["name"] == "식품 (1617)"
    print("ok")
