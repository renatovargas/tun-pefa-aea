"""Extraction des bilans énergétiques de l'ONEM, 2015 à 2022.

Lit les classeurs de data/sources/bilan-energetique/, les met en format long,
attribue à chaque ligne un code de flux et un code de produit stables à partir
des nomenclatures de data/nomenclatures/, convertit les ktep en TJ et écrit
data/intermediaires/bilans_energetiques.parquet.

La page fr/traitement/01-extraction-bilans/ explique chaque étape.

Usage : uv run python scripts/extraire_bilans.py
"""

import re
from pathlib import Path

import polars as pl

SOURCES = Path("data/sources/bilan-energetique")
NOMENCLATURES = Path("data/nomenclatures")
SORTIE = Path("data/intermediaires/bilans_energetiques.parquet")

# 1 tep = 41,868 GJ, donc 1 ktep = 41,868 TJ
KTEP_EN_TJ = 41.868

# Les titres de bloc changent le contexte des libellés qui se répètent
# (« Raffineries » en entrée et en sortie, « Chimie » non énergétique et industrielle).
TITRES_BLOCS = {
    "Entrées en transformation": "entrees",
    "Sortie de transformation": "sorties",
    "Echanges, transfer, restitutions": "echanges",
    "Consommation finale non énergétique": "non_energetique",
    "Consommation finale énergétique": "energetique",
}


def normaliser(texte: str | None) -> str | None:
    """Retire les espaces superflus et les retours à la ligne d'un libellé."""
    if texte is None:
        return None
    texte = " ".join(texte.split())
    return texte or None


def fichiers_bilans() -> dict[int, Path]:
    """Associe chaque année au classeur du bilan correspondant."""
    return {
        int(re.search(r"(\d{4})", f.name).group(1)): f
        for f in sorted(SOURCES.glob("balance*.xl*"))
    }


def lire_bilan(chemin: Path, annee: int) -> pl.DataFrame:
    """Lit un bilan et renvoie un tableau long avec les libellés d'origine."""
    brut = pl.read_excel(chemin, has_header=False, engine="calamine", infer_schema_length=0)
    lignes = brut.with_row_index()
    entete = lignes.filter(pl.col("column_0").str.starts_with("en 1000 tep"))["index"][0]
    produits = [
        normaliser(" ".join(x for x in (brut[entete, j], brut[entete + 1, j]) if x))
        for j in range(1, brut.width)
    ]
    debut = lignes.filter(pl.col("column_0").str.strip_chars() == "Production primaire")["index"][0]
    corps = brut[debut:].rename(
        {"column_0": "flux_source"} | {f"column_{j}": produits[j - 1] for j in range(1, brut.width)}
    )
    corps = corps.with_columns(pl.col("flux_source").map_elements(normaliser, return_dtype=pl.String))
    corps = corps.filter(pl.col("flux_source").is_not_null())

    blocs, courant = [], "approvisionnement"
    for libelle in corps["flux_source"]:
        courant = TITRES_BLOCS.get(libelle, courant)
        blocs.append(courant)
    corps = corps.with_columns(
        pl.Series("bloc", blocs), pl.Series("ordre_source", range(1, corps.height + 1))
    )

    long = corps.unpivot(
        index=["ordre_source", "bloc", "flux_source"],
        variable_name="produit_source",
        value_name="valeur",
    )
    # Une cellule de 2015 porte un renvoi « 0 * » : l'astérisque est retiré.
    texte = long["valeur"].str.replace(r"\s*\*$", "").str.strip_chars()
    valeurs = texte.cast(pl.Float64, strict=False)
    illisibles = long.filter(valeurs.is_null() & texte.ne(""))
    if illisibles.height:
        raise ValueError(f"{annee} : valeurs non numériques {illisibles['valeur'].unique().to_list()}")
    return (
        long.with_columns(ktep=valeurs, annee=pl.lit(annee, pl.Int16))
        .filter(pl.col("ktep").is_not_null() & (pl.col("ktep") != 0))
        .drop("valeur")
    )


def coder(long: pl.DataFrame) -> pl.DataFrame:
    """Attribue les codes de flux et de produit ; s'arrête sur tout libellé inconnu."""
    flux = pl.read_csv(NOMENCLATURES / "bilan_flux_sources.csv")
    produits = pl.read_csv(NOMENCLATURES / "bilan_produits_sources.csv")
    code = long.join(
        flux.rename({"libelle_source": "flux_source", "code": "code_flux"}),
        on=["bloc", "flux_source"],
        how="left",
    ).join(
        produits.rename({"libelle_source": "produit_source", "code": "code_produit"}),
        on="produit_source",
        how="left",
    )
    manquants = code.filter(pl.col("code_flux").is_null() | pl.col("code_produit").is_null())
    if manquants.height:
        raise ValueError(
            "Libellés sans code : "
            + str(manquants.select("annee", "bloc", "flux_source", "produit_source").unique().rows())
        )
    return code


def agreger(code: pl.DataFrame) -> pl.DataFrame:
    """Additionne les lignes qui reçoivent le même code (cas de 2015) et convertit en TJ."""
    ordre = pl.read_csv(NOMENCLATURES / "bilan_flux.csv").with_row_index("ordre")
    return (
        code.group_by("annee", "code_flux", "code_produit")
        .agg(
            pl.col("flux_source").unique(maintain_order=True).str.join(" + "),
            pl.col("produit_source").first(),
            pl.col("ktep").sum(),
        )
        .join(ordre.select("code", "ordre").rename({"code": "code_flux"}), on="code_flux")
        .with_columns(tj=pl.col("ktep") * KTEP_EN_TJ, ordre=pl.col("ordre").cast(pl.Int16))
        .sort("annee", "ordre", "code_produit")
        .select("annee", "ordre", "code_flux", "code_produit", "flux_source", "produit_source", "ktep", "tj")
    )


def extraire() -> pl.DataFrame:
    """Lit, code et agrège tous les bilans disponibles."""
    tables = [lire_bilan(chemin, annee) for annee, chemin in fichiers_bilans().items()]
    return agreger(coder(pl.concat(tables)))


def ecarts_hierarchie(bilans: pl.DataFrame, dimension: str) -> pl.DataFrame:
    """Compare chaque agrégat à la somme signée de ses composantes.

    `dimension` vaut "flux" ou "produit". Renvoie un écart par année, agrégat
    et élément de l'autre dimension.
    """
    nomenclature = pl.read_csv(NOMENCLATURES / {"flux": "bilan_flux.csv", "produit": "bilan_produits.csv"}[dimension])
    if "signe" not in nomenclature.columns:
        nomenclature = nomenclature.with_columns(signe=pl.lit(1))
    cle, autre = f"code_{dimension}", "code_produit" if dimension == "flux" else "code_flux"
    enfants = nomenclature.filter(pl.col("parent").is_not_null()).select(
        pl.col("code").alias(cle), "parent", "signe"
    )
    somme = (
        bilans.join(enfants, on=cle)
        .group_by("annee", "parent", autre)
        .agg((pl.col("ktep") * pl.col("signe")).sum().alias("somme"))
    )
    publie = bilans.filter(pl.col(cle).is_in(enfants["parent"].unique().implode())).select(
        "annee", pl.col(cle).alias("parent"), autre, pl.col("ktep").alias("publie")
    )
    return (
        publie.join(somme, on=["annee", "parent", autre], how="full", coalesce=True)
        .with_columns(pl.col("publie", "somme").fill_null(0))
        .with_columns(ecart=pl.col("publie") - pl.col("somme"))
    )


def ecarts_identites(bilans: pl.DataFrame) -> pl.DataFrame:
    """Vérifie l'identité du disponible pour la consommation finale, par produit.

    Disponible = consommation intérieure brute - entrées en transformation
    + sorties de transformation + échanges - branche énergie - pertes.
    """
    signes = {"CIB": 1, "TRE": -1, "TRS": 1, "ECH": 1, "BRENERG": -1, "PERTES": -1}
    calcule = (
        bilans.filter(pl.col("code_flux").is_in(list(signes)))
        .with_columns(pl.col("code_flux").replace_strict(signes, return_dtype=pl.Int8).alias("signe"))
        .group_by("annee", "code_produit")
        .agg((pl.col("ktep") * pl.col("signe")).sum().alias("calcule"))
    )
    publie = bilans.filter(pl.col("code_flux") == "DISPO").select("annee", "code_produit", pl.col("ktep").alias("publie"))
    return (
        publie.join(calcule, on=["annee", "code_produit"], how="full", coalesce=True)
        .with_columns(pl.col("publie", "calcule").fill_null(0))
        .with_columns(ecart=pl.col("publie") - pl.col("calcule"))
    )


def main() -> None:
    bilans = extraire()
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    bilans.write_parquet(SORTIE, compression="zstd")
    print(f"{SORTIE} : {bilans.height} lignes, années {bilans['annee'].min()} à {bilans['annee'].max()}")
    for nom, ecarts in [
        ("flux", ecarts_hierarchie(bilans, "flux")),
        ("produits", ecarts_hierarchie(bilans, "produit")),
        ("disponible", ecarts_identites(bilans)),
    ]:
        print(f"Écart absolu maximal ({nom}) : {ecarts['ecart'].abs().max():.2f} ktep")


if __name__ == "__main__":
    main()
