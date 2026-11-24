"""Appel des outils du FMI sans Excel (couche de référence).

Le PEFA Converter du FMI (auteur : Achille Pegoue, Département des statistiques)
est un classeur Excel qui appelle la fonction Python `EB2PEFA` par xlwings. Ce
module charge cette fonction sans la modifier, remplace xlwings par un module
minimal, et lui passe des plages construites comme Excel le fait (listes de
listes, nombres en flottants, cellules vides à None).

Les pages qui utilisent ce module le citent avec un lien vers ce fichier :
https://github.com/renatovargas/tun-pefa-aea/blob/main/scripts/outils_fmi.py
"""

import importlib.util
import sys
import types
import warnings
from pathlib import Path

import openpyxl
import pandas as pd
import polars as pl

DOSSIER_PEFA = Path("outils-fmi/pefa-converter")
CLASSEUR_PEFA = DOSSIER_PEFA / "PEFA_Converter.xlsm"

# Filtre par défaut de la cellule PEFA!B1 du classeur (avec deux espaces au début)
FILTRE_DEFAUT = "  ALL (Statistical difference exclusive)"

COLONNES_SORTIE = [
    "PEFA_Target_Product_Level1",
    "PEFA_Target_Product_Level2",
    "PEFA_Target_Product",
    "PEFA_Target_Activity",
    "PEFA_Quadrant",
    "PEFA_Energy",
]


def _xlwings_minimal() -> None:
    """Installe un module `xlwings` dont le décorateur `func` rend la fonction inchangée."""
    if "xlwings" not in sys.modules or not hasattr(sys.modules["xlwings"], "func"):
        module = types.ModuleType("xlwings")
        module.func = lambda f: f
        sys.modules["xlwings"] = module


def charger_pefa_converter() -> types.ModuleType:
    """Importe outils-fmi/pefa-converter/PEFA_Converter.py tel quel."""
    _xlwings_minimal()
    spec = importlib.util.spec_from_file_location("PEFA_Converter", DOSSIER_PEFA / "PEFA_Converter.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valeur_excel(x):
    """Rend une valeur de cellule comme xlwings : les nombres en flottants."""
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, (int, float)):
        return float(x)
    return x


def _counta(lignes: list[tuple], colonne: int | None = None, ligne: int | None = None) -> int:
    """Équivalent de COUNTA sur une colonne entière ou une ligne entière (indices à partir de 0)."""
    if colonne is not None:
        return sum(1 for r in lignes if len(r) > colonne and r[colonne] not in (None, ""))
    return sum(1 for x in lignes[ligne] if x not in (None, ""))


def _offset(lignes: list[tuple], ligne: int, colonne: int, hauteur: int, largeur: int) -> list[list]:
    """Équivalent d'OFFSET(ancre,,,hauteur,largeur) : une plage en liste de listes."""
    plage = []
    for r in lignes[ligne : ligne + hauteur]:
        r = list(r) + [None] * (colonne + largeur - len(r))
        plage.append([_valeur_excel(x) for x in r[colonne : colonne + largeur]])
    return plage


def plages_classeur(chemin: Path = CLASSEUR_PEFA, feuille_bilan: str = "Energy_Balance") -> dict:
    """Reconstruit les plages nommées du classeur, selon leurs définitions OFFSET/COUNTA.

    Energy_Balance      OFFSET(Energy_Balance!$A$2,,,COUNTA($A:$A),COUNTA($2:$2))
    Concordance_Matrix  OFFSET(Concordance_Matrix!$B$1,,,COUNTA($B:$B),COUNTA($1:$1))
    EB_Bridging_Items   OFFSET(Bridging_Items!$A$2,,,COUNTA($A:$A)+1,COUNTA($2:$2))
    EB_Product          OFFSET(Classification!$U$1,,,COUNTA($U:$U),3)
    """
    classeur = openpyxl.load_workbook(chemin, data_only=True, read_only=True)
    feuilles = {
        nom: list(classeur[nom].iter_rows(values_only=True))
        for nom in [feuille_bilan, "Concordance_Matrix", "Bridging_Items", "Classification", "PEFA"]
    }
    bilan = feuilles[feuille_bilan]
    cm = feuilles["Concordance_Matrix"]
    ponts = feuilles["Bridging_Items"]
    classification = feuilles["Classification"]
    plages = {
        "EB": _offset(bilan, 1, 0, _counta(bilan, colonne=0), _counta(bilan, ligne=1)),
        "CM": _offset(cm, 0, 1, _counta(cm, colonne=1), _counta(cm, ligne=0)),
        "EB_Bridging_Items": _offset(ponts, 1, 0, _counta(ponts, colonne=0) + 1, _counta(ponts, ligne=1)),
        "EB_Product": _offset(classification, 0, 20, _counta(classification, colonne=20), 3),
        "Filter": feuilles["PEFA"][0][1],
    }
    classeur.close()
    return plages


def eb2pefa(eb: list[list], cm: list[list], ponts: list[list], produits: list[list], filtre: str = FILTRE_DEFAUT) -> pl.DataFrame:
    """Appelle EB2PEFA et renvoie le résultat en polars (énergie en PJ, comme l'outil)."""
    module = charger_pefa_converter()
    # Le code de l'outil émet des avertissements pandas (SettingWithCopy, FutureWarning) sans effet sur le résultat.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        resultat = pd.DataFrame(module.EB2PEFA(eb, cm, ponts, produits, filtre))
    colonnes = {
        c: [x if isinstance(x, str) else None for x in resultat[c]] for c in COLONNES_SORTIE[:-1]
    }
    colonnes["PEFA_Energy"] = [float(x) for x in resultat["PEFA_Energy"]]
    return pl.DataFrame(colonnes)


def lignes_flux_modele(chemin: Path = CLASSEUR_PEFA) -> list[str]:
    """Liste ordonnée des flux du modèle de bilan (feuille Energy_Balance_Template, colonne A)."""
    plages = plages_classeur(chemin, "Energy_Balance_Template")
    return [r[0] for r in plages["EB"][1:]]


def produits_modele(chemin: Path = CLASSEUR_PEFA) -> list[str]:
    """Liste ordonnée des produits du modèle de bilan (ligne d'en-tête de Energy_Balance_Template)."""
    plages = plages_classeur(chemin, "Energy_Balance_Template")
    return [p for p in plages["EB"][0][1:]]


def bilan_vers_plage(bilan: pl.DataFrame, flux: list[str], produits: list[str]) -> list[list]:
    """Construit la plage Energy_Balance à partir d'un bilan long (flux_modele, produit_modele, tj).

    Toutes les lignes du modèle sont présentes, dans l'ordre du modèle, car EB2PEFA
    repère les blocs du bilan par la position des titres. Les cellules sans valeur
    valent 0, comme dans le modèle.
    """
    somme = bilan.group_by("flux_modele", "produit_modele").agg(pl.col("tj").sum())
    valeurs = {(f, p): v for f, p, v in somme.iter_rows()}
    entete = [None] + list(produits)
    return [entete] + [[f] + [float(valeurs.get((f, p), 0.0)) for p in produits] for f in flux]
