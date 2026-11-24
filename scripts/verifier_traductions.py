"""Vérifie la cohérence des trois versions linguistiques du site.

1. Chaque fichier .qmd de fr/ existe au même chemin dans en/ et ar/, et
   inversement. Le sélecteur de langue du site repose sur ces chemins miroirs.
2. Les blocs de code Python d'une page traduite sont identiques à ceux de la
   page française, qui est la seule à exécuter le code.

Usage : uv run python scripts/verifier_traductions.py
Le script s'arrête avec un code d'erreur si une vérification échoue.
"""

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
LANGUES = ["fr", "en", "ar"]
BLOC_PYTHON = re.compile(r"^```\{python\}.*?^```$", flags=re.S | re.M)


def pages(langue: str) -> set[Path]:
    dossier = RACINE / langue
    return {p.relative_to(dossier) for p in dossier.rglob("*.qmd")}


def main() -> int:
    erreurs = []
    reference = pages("fr")
    for langue in LANGUES[1:]:
        traduites = pages(langue)
        for manque in sorted(reference - traduites):
            erreurs.append(f"{langue}/{manque} manque (existe en fr/)")
        for orphelin in sorted(traduites - reference):
            erreurs.append(f"{langue}/{orphelin} n'a pas d'original en fr/")
        for page in sorted(reference & traduites):
            code_fr = BLOC_PYTHON.findall((RACINE / "fr" / page).read_text(encoding="utf-8"))
            code_tr = BLOC_PYTHON.findall((RACINE / langue / page).read_text(encoding="utf-8"))
            if code_fr != code_tr:
                erreurs.append(f"{langue}/{page} : le code diffère de fr/{page}")
    for e in erreurs:
        print(e)
    print("OK" if not erreurs else f"{len(erreurs)} problème(s)")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
