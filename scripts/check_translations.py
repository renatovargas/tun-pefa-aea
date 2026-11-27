"""Check that the three language versions of the site mirror each other.

1. Every .qmd file of en/ exists at the same path in fr/ and ar/, and the reverse. The
   language menu of the site relies on these mirrored paths.
2. Every inline Python expression of a page (the numbers quoted in the text) also appears in
   its translations, so that no translated page quotes a number typed by hand.

Usage: uv run python scripts/check_translations.py
The script exits with an error code if a check fails.

Vérifie que les trois versions linguistiques du site sont des miroirs : mêmes chemins, et
mêmes expressions Python en ligne (les nombres cités dans le texte) dans chaque traduction.
"""

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = ["en", "fr", "ar"]
INLINE = re.compile(r"`\{python\} ([^`]+)`")


def pages(lang: str) -> set[Path]:
    return {p.relative_to(ROOT / lang) for p in (ROOT / lang).rglob("*.qmd")}


def main() -> int:
    errors = []
    reference = pages("en")
    for lang in LANGUAGES[1:]:
        translated = pages(lang)
        errors += [f"missing in {lang}/: {p}" for p in sorted(reference - translated)]
        errors += [f"only in {lang}/: {p}" for p in sorted(translated - reference)]
        for page in sorted(reference & translated):
            source = Counter(INLINE.findall((ROOT / "en" / page).read_text()))
            target = Counter(INLINE.findall((ROOT / lang / page).read_text()))
            missing = source - target
            if missing:
                errors.append(f"{lang}/{page}: inline expressions missing or changed: {sorted(missing)[:3]}")
    for e in errors:
        print(e)
    print("OK" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
