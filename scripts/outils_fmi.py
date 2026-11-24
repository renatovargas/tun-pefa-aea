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


# ---------------------------------------------------------------------------
# I2A (outil des comptes des émissions atmosphériques, Achille Pegoue, FMI)
# ---------------------------------------------------------------------------

DOSSIER_I2A = Path("outils-fmi/i2a")
CLASSEUR_I2A = DOSSIER_I2A / "I2A.xlsm"

# Valeurs des cellules de paramètres de la feuille Output_Source_Activity
OECD_UTILISER = "Use OECD International Transport Emissions"
OECD_NE_PAS_UTILISER = "Do Not Use OECD International Transport Emissions"
UNITE_KT = "Thousand tonnes CO2Eq"


def charger_i2a() -> types.ModuleType:
    """Importe outils-fmi/i2a/I2A.py tel quel."""
    _xlwings_minimal()
    spec = importlib.util.spec_from_file_location("I2A", DOSSIER_I2A / "I2A.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plages_i2a(chemin: Path = CLASSEUR_I2A) -> dict:
    """Reconstruit les plages de l'outil I2A pour l'inventaire CRT, selon les définitions OFFSET/COUNTA.

    Les feuilles « _Def » contiennent les tables par défaut de l'outil ; les feuilles
    actives du classeur d'exemple portent des facteurs de démonstration. Les plages
    sont construites sur les feuilles « _Def » avec les mêmes définitions que les
    plages nommées :
    Conversion_Matrix_CRT  OFFSET($A$1,,,COUNTA($C:$C),COUNTA($1:$1))
    Activity               OFFSET($A$1,,,COUNTA($A:$A),COUNTA($1:$1))
    CRT                    OFFSET($A$1,,,COUNTA($A:$A),COUNTA($1:$1))
    """
    classeur = openpyxl.load_workbook(chemin, data_only=True, read_only=True)
    feuilles = {
        nom: list(classeur[nom].iter_rows(values_only=True))
        for nom in ["Conversion_Matrix_CRT_Def", "Activity_Def", "CRT_Def", "NFR"]
    }
    classeur.close()
    cm, act, crt, nfr = (feuilles[n] for n in ["Conversion_Matrix_CRT_Def", "Activity_Def", "CRT_Def", "NFR"])
    return {
        "Conversion_Matrix": _offset(cm, 0, 0, _counta(cm, colonne=2), _counta(cm, ligne=0)),
        "Activity": _offset(act, 0, 0, _counta(act, colonne=0), _counta(act, ligne=0)),
        "CRT": _offset(crt, 0, 0, _counta(crt, colonne=0), _counta(crt, ligne=0)),
        "NFR": _offset(nfr, 0, 0, _counta(nfr, colonne=0), _counta(nfr, ligne=0)),
    }


def oecd_i2a(pays: str = "TUN") -> dict:
    """Données de l'OCDE sur le transport aérien et maritime, filtrées comme le fait Read_OECD.

    Les fichiers de outils-fmi/i2a/I2A_Data/ sont les lignes du pays extraites des
    fichiers DSD_AIR_TRANSPORT.csv et DSD_MARITIME_TRANSPORT.csv livrés avec l'outil
    (valeurs en tonnes). Read_OECD garde les données annuelles, tous vols confondus,
    pour les émissions des résidents ; et tous les navires pour le maritime.
    """
    air = pd.read_csv(DOSSIER_I2A / "I2A_Data" / f"DSD_AIR_TRANSPORT_{pays}.csv")
    air = air[
        (air["REF_AREA"] == pays) & (air["FREQ"] == "A") & (air["FLIGHT_TYPE"] == "_T")
        & air["EMISSIONS_SOURCE"].isin(["RES_DOM_IN", "RES_DOM_OUT", "RES_INT_FROM", "RES_INT_TO", "RES_INT_OUT"])
    ]
    mer = pd.read_csv(DOSSIER_I2A / "I2A_Data" / f"DSD_MARITIME_TRANSPORT_{pays}.csv")
    mer = mer[(mer["REF_AREA"] == pays) & (mer["FREQ"] == "A") & (mer["VESSEL"] == "ALL_VESSELS")]

    def plage(d: pd.DataFrame) -> list[list]:
        d = d.astype(object).where(d.notna(), None)
        return [list(d.columns)] + d.values.tolist()

    return {"OECD_Air": plage(air), "OECD_Sea": plage(mer)}


def i2a(inventaire: list[list], matrice: list[list], crt: list[list], nfr: list[list], activite: list[list],
        oecd: dict | None = None, utiliser_oecd: str = OECD_NE_PAS_UTILISER, unite: str = UNITE_KT) -> pl.DataFrame:
    """Appelle I2A comme la formule de Output_Source_Activity!B3 et renvoie un tableau long (polars).

    Arguments dans l'ordre de la formule : Inventory_2, Conversion_Matrix, CRT, NFR,
    Activity, type d'inventaire (« UNFCCC »), niveaux CRT et activité (cellules vides),
    OECD_Air, OECD_Sea, choix OCDE et unité.
    """
    module = charger_i2a()
    oecd = oecd or {"OECD_Air": [], "OECD_Sea": []}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sortie = module.I2A(inventaire, matrice, crt, nfr, activite, "UNFCCC", None, None,
                            oecd["OECD_Air"], oecd["OECD_Sea"], utiliser_oecd, unite)
    cles = ["POLLUTANT", "Source_Code", "Source_Description", "Activity", "Description"]
    annees = [c for c in sortie.columns if c not in cles + ["REF_AREA", "CountryName"]]
    longue = sortie.melt(id_vars=cles, value_vars=annees, var_name="annee", value_name="valeur")
    longue = longue[longue["valeur"].notna()]
    return pl.DataFrame({
        **{c: [x if isinstance(x, str) else None for x in longue[c]] for c in cles},
        "annee": [int(a) for a in longue["annee"]],
        "valeur": [float(v) for v in longue["valeur"]],
    })
