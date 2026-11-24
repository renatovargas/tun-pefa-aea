#!/usr/bin/env bash
# Rendu complet du site dans les trois langues.
# Le français se rend en premier : c'est la seule langue qui exécute le code.
# L'anglais et l'arabe se rendent ensuite dans le même docs/, chacun avec son
# profil (langue, menus, direction du texte). --no-clean est indispensable :
# un rendu complet d'un profil vide docs/ et effacerait les autres langues.
set -euo pipefail
cd "$(dirname "$0")/.."

uv run quarto render --profile fr
uv run quarto render en --profile en --no-clean
uv run quarto render ar --profile ar --no-clean
