"""Extraction des tableaux CRT de l'inventaire des gaz à effet de serre, 2015 à 2022.

Empile la feuille `Data` de chaque classeur CRT (déjà en format long), ajoute
l'année, convertit les valeurs en nombres, retire les lignes en double et écrit
data/intermediaires/crt.parquet.

La page fr/traitement/02-extraction-crt/ explique chaque étape.

Usage : uv run python scripts/extraire_crt.py
"""

import re
from pathlib import Path

import polars as pl

SOURCES = Path("data/sources/inventaire-ges/crt")
SORTIE = Path("data/intermediaires/crt.parquet")

# Noms des colonnes de la feuille Data et leur nom dans le tableau intermédiaire
COLONNES = {
    "Record_Key": "cle",
    "CRT": "crt",
    "Parameter": "parametre",
    "Type": "type",
    "Fuel": "combustible",
    "Gas": "gaz",
    "Unit": "unite",
    "Value": "valeur",
}

# Potentiels de réchauffement global à 100 ans du cinquième rapport du GIEC (AR5),
# utilisés par l'inventaire tunisien. Ils servent ici au contrôle avec Summary2.
PRG_AR5 = {"CO2": 1, "CH4": 28, "N2O": 265}


def fichiers_crt() -> dict[int, Path]:
    """Associe chaque année au classeur CRT correspondant."""
    return {
        int(re.match(r"(\d{4})", f.name).group(1)): f
        for f in sorted(SOURCES.glob("*_Tables_CRT_*.xlsm"))
    }


def lire_data(chemin: Path, annee: int) -> tuple[pl.DataFrame, int]:
    """Lit la feuille Data d'un classeur. Renvoie le tableau et le nombre de doublons retirés."""
    brut = pl.read_excel(chemin, sheet_name="Data", engine="calamine", infer_schema_length=0)
    brut = brut.select(list(COLONNES)).rename(COLONNES)
    unique = brut.unique(maintain_order=True)
    tableau = unique.with_columns(
        annee=pl.lit(annee, pl.Int16),
        valeur=pl.col("valeur").cast(pl.Float64),
    ).select("annee", *[c for c in COLONNES.values()])
    return tableau, brut.height - unique.height


def extraire() -> tuple[pl.DataFrame, dict[int, int]]:
    """Empile toutes les années. Renvoie aussi les doublons retirés par année."""
    tables, doublons = [], {}
    for annee, chemin in fichiers_crt().items():
        tableau, n = lire_data(chemin, annee)
        tables.append(tableau)
        doublons[annee] = n
    return pl.concat(tables), doublons


def lire_summary2(chemin: Path) -> pl.DataFrame:
    """Lit les émissions de CO2, CH4 et N2O par catégorie publiées dans Summary2 (kt éq. CO2)."""
    brut = pl.read_excel(chemin, sheet_name="Summary2", engine="calamine", has_header=False, infer_schema_length=0)
    ligne_gaz = brut.with_row_index().filter(pl.col("column_0").str.starts_with("GREENHOUSE GAS SOURCE"))["index"][0]
    gaz = {j: (brut[ligne_gaz, j] or "").strip() for j in range(1, brut.width)}
    colonnes = {f"column_{j}": nom for j, nom in gaz.items() if nom in PRG_AR5}
    lignes = (
        brut[ligne_gaz + 2 :]
        .select(pl.col("column_0").alias("categorie"), *[pl.col(c).alias(n) for c, n in colonnes.items()])
        .with_columns(crt=pl.col("categorie").str.extract(r"^\s*(\d(?:\.[A-Z0-9]+)*)\.?\s"))
        .filter(pl.col("crt").is_not_null())
    )
    return lignes.unpivot(index=["categorie", "crt"], variable_name="gaz", value_name="summary2").with_columns(
        pl.col("summary2").cast(pl.Float64, strict=False).fill_null(0)
    )


def comparer_summary2(crt: pl.DataFrame, annee: int) -> pl.DataFrame:
    """Compare les émissions de Data, sommées par catégorie, aux totaux de Summary2."""
    reference = lire_summary2(fichiers_crt()[annee])
    emissions = crt.filter(
        (pl.col("annee") == annee)
        & (pl.col("parametre") == "emission")
        & (pl.col("unite") == "kt")
        & pl.col("gaz").is_in(list(PRG_AR5))
    )
    # Les éléments pour mémoire (1.D, soutes internationales) ne font pas partie
    # du total de l'énergie ; ils sont exclus des sommes des catégories parentes.
    def somme(categorie: str, gaz: str) -> float:
        lignes = emissions.filter(pl.col("gaz") == gaz, pl.col("crt").str.starts_with(categorie + "."))
        if not categorie.startswith("1.D"):
            lignes = lignes.filter(~pl.col("crt").str.starts_with("1.D"))
        return lignes["valeur"].sum() * PRG_AR5[gaz]

    sommes = [somme(c, g) for c, g in zip(reference["crt"], reference["gaz"])]
    return reference.with_columns(data=pl.Series(sommes)).with_columns(ecart=pl.col("summary2") - pl.col("data"))


def main() -> None:
    crt, doublons = extraire()
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    crt.write_parquet(SORTIE, compression="zstd")
    print(f"{SORTIE} : {crt.height} lignes, années {crt['annee'].min()} à {crt['annee'].max()}")
    print(f"Doublons exacts retirés : {doublons}")
    for annee in sorted(doublons):
        ecarts = comparer_summary2(crt, annee)
        print(f"{annee} : écart maximal avec Summary2 {ecarts['ecart'].abs().max():.4f} kt éq. CO2")


if __name__ == "__main__":
    main()
