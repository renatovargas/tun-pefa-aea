"""Extraction des tableaux des ressources et des emplois (TRE), 2015 à 2023.

Lit une feuille par année du classeur de l'INS (prix courants, millions de
dinars), repère les blocs par le texte des en-têtes et non par leur position,
met le tout en format long et écrit data/intermediaires/tre.parquet.

La page fr/traitement/03-extraction-tre/ explique chaque étape.

Usage : uv run python scripts/extraire_tre.py
"""

import re
from pathlib import Path

import polars as pl

SOURCE = Path("data/sources/comptes-nationaux/TRE 2015-2023 SD.xlsx")
NOMENCLATURES = Path("data/nomenclatures")
SORTIE = Path("data/intermediaires/tre.parquet")


def normaliser(texte: str | None) -> str:
    """Retire les espaces superflus, y compris les espaces insécables."""
    return " ".join((texte or "").split())


def feuilles() -> dict[int, str]:
    """Associe chaque année à sa feuille (« 2015 C » ... « 2023 C »)."""
    import fastexcel

    noms = fastexcel.read_excel(SOURCE).sheet_names
    return {int(m.group(1)): n for n in noms if (m := re.match(r"(\d{4}) C$", n))}


def lire_feuille(annee: int, feuille: str) -> pl.DataFrame:
    """Lit une feuille et renvoie un tableau long : bloc, ligne, colonne, valeur."""
    brut = pl.read_excel(SOURCE, sheet_name=feuille, engine="calamine", has_header=False, infer_schema_length=0)
    colonnes = pl.read_csv(NOMENCLATURES / "tre_colonnes.csv")
    produits = pl.read_csv(NOMENCLATURES / "tre_produits.csv", schema_overrides={"code": pl.String})
    codes_produits = set(produits["code"])

    # Ligne d'en-tête : celle dont la première cellule commence par « Unité »
    entete = brut.with_row_index().filter(pl.col("column_0").str.strip_chars().str.starts_with("Unité"))["index"][0]
    libelles = [normaliser(x) for x in brut.row(entete)]

    # Colonnes nommées (ressources et emplois finals) d'après tre_colonnes.csv
    par_libelle = {
        r["libelle_source"]: (r["code"], r["bloc"])
        for r in colonnes.filter(pl.col("bloc") != "valeur_ajoutee").iter_rows(named=True)
    }
    reperes = {j: par_libelle[l] for j, l in enumerate(libelles) if l in par_libelle}
    # Colonnes de la matrice de consommation intermédiaire : en-tête = code d'activité
    activites = {j: l for j, l in enumerate(libelles) if l in codes_produits}
    inconnues = [l for j, l in enumerate(libelles) if l and j > 0 and j not in reperes and j not in activites and not l.startswith("Unité")]
    if inconnues:
        raise ValueError(f"{feuille} : en-têtes inconnus {inconnues}")

    enregistrements = []
    # Lignes de produits (et la ligne « Totaux »)
    for i in range(entete + 1, brut.height):
        code = normaliser(brut[i, 0])
        if code in codes_produits or code == "Totaux":
            ligne = "TOTAL" if code == "Totaux" else code
            for j, (col, bloc) in reperes.items():
                enregistrements.append((bloc, ligne, col, brut[i, j]))
            for j, act in activites.items():
                enregistrements.append(("emplois", ligne, act, brut[i, j]))

    # Lignes de valeur ajoutée sous la matrice : libellé dans la colonne qui précède la première activité
    va = {r["libelle_source"]: r["code"] for r in colonnes.filter(pl.col("bloc") == "valeur_ajoutee").iter_rows(named=True)}
    col_libelle = min(activites) - 1
    for i in range(entete + 1, brut.height):
        libelle = normaliser(brut[i, col_libelle])
        if libelle in va:
            for j, act in activites.items():
                enregistrements.append(("valeur_ajoutee", va[libelle], act, brut[i, j]))

    long = pl.DataFrame(enregistrements, schema=["bloc", "ligne", "colonne", "texte"], orient="row")
    long = long.with_columns(valeur=pl.col("texte").str.strip_chars().cast(pl.Float64, strict=False))
    illisibles = long.filter(pl.col("valeur").is_null() & (pl.col("texte").str.strip_chars() != ""))
    if illisibles.height:
        raise ValueError(f"{feuille} : valeurs non numériques {illisibles['texte'].unique().to_list()}")
    agregats = set(colonnes.filter(pl.col("agregat") == "oui")["code"])
    return (
        long.filter(pl.col("valeur").is_not_null() & (pl.col("valeur") != 0))
        .with_columns(
            annee=pl.lit(annee, pl.Int16),
            agregat=pl.col("colonne").is_in(list(agregats)) | (pl.col("ligne") == "TOTAL"),
        )
        .select("annee", "bloc", "ligne", "colonne", "agregat", "valeur")
    )


def extraire() -> pl.DataFrame:
    """Lit toutes les années."""
    return pl.concat([lire_feuille(a, f) for a, f in sorted(feuilles().items())])


def ecarts_equilibre(tre: pl.DataFrame) -> pl.DataFrame:
    """Par année et produit : total des ressources publié, somme des ressources,
    somme des emplois détaillés. Les deux écarts doivent être proches de zéro."""
    produits = tre.filter(pl.col("bloc") != "valeur_ajoutee", pl.col("ligne") != "TOTAL")
    total = produits.filter(pl.col("colonne") == "TRES").select("annee", "ligne", pl.col("valeur").alias("total_ressources"))
    detail = produits.filter(~pl.col("agregat")).group_by("annee", "ligne").agg(
        pl.col("valeur").filter(pl.col("bloc") == "ressources").sum().alias("ressources"),
        pl.col("valeur").filter(pl.col("bloc") == "emplois").sum().alias("emplois"),
    )
    return (
        total.join(detail, on=["annee", "ligne"], how="full", coalesce=True)
        .with_columns(pl.col("total_ressources", "ressources", "emplois").fill_null(0))
        .with_columns(
            ecart_ressources=pl.col("total_ressources") - pl.col("ressources"),
            ecart_emplois=pl.col("total_ressources") - pl.col("emplois"),
        )
        .sort("annee", "ligne")
    )


def ecarts_production(tre: pl.DataFrame) -> pl.DataFrame:
    """Par année et activité : production = consommation intermédiaire + valeur ajoutée."""
    ci = tre.filter(pl.col("bloc") == "emplois", ~pl.col("agregat")).group_by("annee", "colonne").agg(pl.col("valeur").sum().alias("ci"))
    va = (
        tre.filter(pl.col("bloc") == "valeur_ajoutee", pl.col("ligne").is_in(["P1", "B1G"]))
        .pivot("ligne", index=["annee", "colonne"], values="valeur")
    )
    return (
        va.join(ci, on=["annee", "colonne"], how="left")
        .with_columns(pl.col("ci", "B1G", "P1").fill_null(0))
        .with_columns(ecart=pl.col("P1") - pl.col("ci") - pl.col("B1G"))
        .sort("annee", "colonne")
    )


def main() -> None:
    tre = extraire()
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    tre.write_parquet(SORTIE, compression="zstd")
    print(f"{SORTIE} : {tre.height} lignes, années {tre['annee'].min()} à {tre['annee'].max()}")
    eq = ecarts_equilibre(tre)
    print(f"Écart maximal ressources : {eq['ecart_ressources'].abs().max():.3f} MDT")
    print(f"Écart maximal emplois : {eq['ecart_emplois'].abs().max():.3f} MDT")
    print(f"Écart maximal production : {ecarts_production(tre)['ecart'].abs().max():.3f} MDT")


if __name__ == "__main__":
    main()
