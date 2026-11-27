"""Build the Tunisian concordance matrix of the PEFA Converter, one per year.

Why    : the concordance matrix tells the PEFA Converter, for each flow and product of the
         balance, which PEFA product, activity and quadrant (supply or use) receive the
         energy, and in what share. The default matrix shipped with the tool allocates flows
         to sections of the International Standard Industrial Classification (ISIC). The
         Tunisian matrix allocates them to the industries of the supply and use tables.
Inputs : data/intermediate/activity_keys.parquet (script 11), balance_iea.parquet (script 10),
         crt.parquet (script 02)
         imf-tools/pefa-converter/PEFA_Converter.xlsm (sheets Concordance_Matrix, Bridging_Items)
         data/lookups/activities.csv, balance_to_activities.csv
Outputs: data/intermediate/concordance_matrix.parquet   the Tunisian matrix, with a year column
         data/intermediate/concordance_changes.parquet  where the Tunisian matrix leaves the default ISIC sections
         data/intermediate/bunkers_check.parquet        bunkers in the balance and in the inventory
         data/outputs/checks/12_build_concordance_matrix.csv
Method : rows of the default matrix for the flows covered by the Tunisian rules are replaced:
         each row is repeated for every activity of the rule, with the activity code and the
         factor of the key. Other rows stay as they are. The script then compares the
         international bunkers of the balance with the memo items of the inventory and
         confirms that the bridging items sheet of the tool is empty.
Run    : uv run python scripts/pefa/12_build_concordance_matrix.py

Construction de la matrice de concordance tunisienne, une par année. Les lignes de la
matrice par défaut des flux couverts par les règles tunisiennes sont remplacées par une ligne
par activité, avec le facteur de la clé. Le script compare aussi les soutes du bilan à celles
de l'inventaire et vérifie que la feuille des éléments de passage de l'outil est vide.
"""

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import imf_tools  # noqa: E402
from common import Checks, read_intermediate, read_lookup, write_intermediate  # noqa: E402

SCRIPT = "12_build_concordance_matrix"


def default_matrix() -> tuple[pl.DataFrame, list[str]]:
    """The default concordance matrix as a polars table. Non-numeric factors are 0, as in the tool."""
    block = imf_tools.pefa_ranges()["CM"]
    table = imf_tools.range_to_table(block).with_columns(pl.col("Allocation Factor").cast(pl.Float64, strict=False).fill_null(0))
    return table, [str(c) for c in block[0]]


def tunisian_matrix(default: pl.DataFrame, keys: pl.DataFrame) -> pl.DataFrame:
    """Replace the activity and the factor of the flows covered by the Tunisian keys of one year."""
    covered = keys["iea_flow"].unique()
    specific = keys.filter(pl.col("iea_product").is_not_null())
    general = keys.filter(pl.col("iea_product").is_null()).drop("iea_product")

    # One row per flow, product and quadrant serves as template; the other columns are identical.
    # Une ligne par flux, produit et quadrant sert de gabarit ; les autres colonnes sont identiques.
    to_replace = default.filter(pl.col("EB_Flow").is_in(covered.implode()))
    template = to_replace.unique(subset=["EB_Flow", "EB_Product", "PEFA_Quadrant"], keep="first", maintain_order=True)

    # Rules that name a product take precedence over the general rule of the flow.
    # Les règles qui nomment un produit l'emportent sur la règle générale du flux.
    with_product = template.join(
        specific.select(pl.col("iea_flow").alias("EB_Flow"), pl.col("iea_product").alias("EB_Product"), "activity", "factor"),
        on=["EB_Flow", "EB_Product"])
    without_product = template.join(
        specific.select(pl.col("iea_flow").alias("EB_Flow"), pl.col("iea_product").alias("EB_Product")).unique(),
        on=["EB_Flow", "EB_Product"], how="anti",
    ).join(general.select(pl.col("iea_flow").alias("EB_Flow"), "activity", "factor"), on="EB_Flow")
    replaced = pl.concat([with_product, without_product]).with_columns(
        pl.col("activity").alias("PEFA_Target_Activity"), pl.col("factor").alias("Allocation Factor")
    ).select(default.columns)
    kept = default.filter(~pl.col("EB_Flow").is_in(covered.implode()))
    return pl.concat([kept, replaced])


def section_changes(default: pl.DataFrame, mapping: pl.DataFrame, activities: pl.DataFrame, iea: pl.DataFrame) -> pl.DataFrame:
    """Compare the ISIC sections of the default matrix with those of the Tunisian rules."""
    present = iea.select("iea_flow", "iea_product").unique()
    default_tn = default.join(present, left_on=["EB_Flow", "EB_Product"], right_on=["iea_flow", "iea_product"]).with_columns(
        pl.col("PEFA_Target_Activity").replace({"RoW": "ROW", "Acc": "ACC", "Env": "ENV"}))
    by_product = default_tn.group_by("EB_Flow", "EB_Product").agg(
        pl.col("PEFA_Target_Activity").unique().sort().str.join(", ").alias("default_product"))
    # For the general rule of a flow, products with a rule of their own are left out.
    # Pour la règle générale d'un flux, les produits qui ont une règle propre sont exclus.
    own = mapping.filter(pl.col("iea_product").is_not_null()).select(
        pl.col("iea_flow").alias("EB_Flow"), pl.col("iea_product").alias("EB_Product"))
    by_flow = default_tn.join(own, on=["EB_Flow", "EB_Product"], how="anti").group_by("EB_Flow").agg(
        pl.col("PEFA_Target_Activity").unique().sort().str.join(", ").alias("default_flow"))
    sections = dict(zip(activities["code"], activities["imf_section"]))
    tunisia = (mapping.with_columns(section=pl.col("activity").replace_strict(sections))
               .group_by("iea_flow", "iea_product", "rationale_en", maintain_order=True)
               .agg(pl.col("activity").str.join(", ").alias("activities"),
                    pl.col("section").unique().sort().str.join(", ").alias("sections")))
    return (tunisia.join(by_flow, left_on="iea_flow", right_on="EB_Flow", how="left")
            .join(by_product, left_on=["iea_flow", "iea_product"], right_on=["EB_Flow", "EB_Product"], how="left")
            .with_columns(default_sections=pl.coalesce("default_product", "default_flow"))
            .with_columns(changed=pl.col("default_sections") != pl.col("sections"))
            .select("iea_flow", "iea_product", "default_sections", "sections", "changed", "activities", "rationale_en"))


def bunkers(iea: pl.DataFrame, crt: pl.DataFrame) -> pl.DataFrame:
    """International bunkers in the balance and in the memo items (1.D.1) of the inventory, in TJ."""
    inventory = (
        crt.filter(pl.col("crt").str.starts_with("1.D.1"), pl.col("parameter") == "activity", pl.col("unit") == "TJ")
        .with_columns(iea_flow=pl.when(pl.col("crt") == "1.D.1.a").then(pl.lit("International aviation bunkers"))
                      .otherwise(pl.lit("International marine bunkers")))
        .group_by("year", "iea_flow").agg(pl.col("value").sum().alias("inventory_tj")))
    balance = (iea.filter(pl.col("iea_flow").str.starts_with("International"))
               .group_by("year", "iea_flow").agg((-pl.col("tj").sum()).alias("balance_tj")))
    return (balance.join(inventory, on=["year", "iea_flow"], how="full", coalesce=True)
            .with_columns(gap_pct=(pl.col("balance_tj") / pl.col("inventory_tj") - 1) * 100)
            .sort("iea_flow", "year"))


def main() -> pl.DataFrame:
    keys = read_intermediate("activity_keys")
    iea = read_intermediate("balance_iea")
    crt = read_intermediate("crt")
    activities, mapping = read_lookup("activities"), read_lookup("balance_to_activities")
    default, _ = default_matrix()

    # One Tunisian matrix per year, because the keys change every year.
    # Une matrice tunisienne par année, car les clés changent chaque année.
    years = sorted(keys["year"].unique().to_list())
    matrix = pl.concat([
        tunisian_matrix(default, keys.filter(pl.col("year") == y).drop("year", "method")).with_columns(year=pl.lit(y, pl.Int16))
        for y in years])
    write_intermediate(matrix, "concordance_matrix")
    write_intermediate(section_changes(default, mapping, activities, iea), "concordance_changes")
    bunker_table = bunkers(iea, crt)
    write_intermediate(bunker_table, "bunkers_check")

    # Factors of the covered flows add up to one by flow, product, target product and quadrant.
    # Les facteurs des flux couverts somment à un par flux, produit, produit cible et quadrant.
    covered = matrix.filter(pl.col("EB_Flow").is_in(mapping["iea_flow"].unique().implode()))
    sums = covered.group_by("year", "EB_Flow", "EB_Product", "PEFA_Target_Product", "PEFA_Quadrant").agg(pl.col("Allocation Factor").sum())

    # The bridging items sheet of the tool holds no quantity: residence adjustments are not in the balance.
    # La feuille des éléments de passage de l'outil ne contient aucune quantité.
    bridge = imf_tools.pefa_ranges()["EB_Bridging_Items"]
    filled = [x for row in bridge[1:] for x in row[2:12] if isinstance(x, float) and x != 0]

    checks = Checks(SCRIPT)
    checks.add("factors_sum_to_one", (sums["Allocation Factor"] - 1).abs().max(), 1e-9, "share", "Factors of covered flows add up to one")
    checks.add("aviation_bunkers_vs_inventory",
               bunker_table.filter(pl.col("iea_flow") == "International aviation bunkers")["gap_pct"].abs().max(), 1, "percent",
               "Aviation bunkers in the balance against memo item 1.D.1.a of the inventory")
    checks.add("bridging_items_empty", len(filled), 0, "cells", "Filled cells in the Bridging_Items sheet of the tool")
    checks.save()
    return matrix


if __name__ == "__main__":
    main()
