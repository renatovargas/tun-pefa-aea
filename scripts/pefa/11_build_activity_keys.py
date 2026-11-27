"""Assign each flow of the energy balance to the industries of the supply and use tables.

Why    : the balance describes energy use by sector of the energy statistics (industrial
         branches, transport modes, households, "commerce, administration, hotels"), while
         the accounts describe it by the 24 industries of the national accounts and by
         households. Most flows belong to one industry. Two do not: road transport is given
         by mode and not by user, and the tertiary line covers several service industries.
Inputs : data/intermediate/balance_iea.parquet (script 10), sut.parquet (script 03)
         data/lookups/balance_to_activities.csv (one row per flow, product and activity)
Outputs: data/intermediate/activity_keys.parquet  year, iea_flow, iea_product, activity, method, factor
         data/outputs/checks/11_build_activity_keys.csv
Method : a flow with method "direct" goes in full to its activity. A flow with method "key"
         is split in proportion to the use, in the supply and use tables of the same year,
         of the key product by each listed activity: refined petroleum products (19) for road
         transport, electricity and gas (35) for the tertiary sector. The factors of a flow
         add up to one.
Run    : uv run python scripts/pefa/11_build_activity_keys.py

Rattachement de chaque flux du bilan aux branches du TRE. Un flux « direct » va en entier à
sa branche. Un flux « clé » est réparti au prorata des emplois d'un produit dans le TRE de
la même année : produits pétroliers raffinés (19) pour le transport routier, électricité et
gaz (35) pour le tertiaire. Les facteurs d'un flux somment à un.
"""

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import HOUSEHOLDS, Checks, read_intermediate, read_lookup, write_intermediate  # noqa: E402

SCRIPT = "11_build_activity_keys"

# Template flows that are not uses by an activity.
# Flux du modèle qui ne sont pas des emplois d'une activité.
NOT_ACTIVITIES = {"Imports", "Exports", "Stock changes", "Statistical differences"}


def product_use(sut: pl.DataFrame, product: str) -> pl.DataFrame:
    """Use of one SUT product by each industry (intermediate consumption) and by households (million TND)."""
    use = sut.filter(pl.col("block") == "use", pl.col("row") == product, ~pl.col("aggregate"))
    return use.with_columns(
        activity=pl.when(pl.col("column") == "P3_HH").then(pl.lit(HOUSEHOLDS)).otherwise(pl.col("column"))
    ).select("year", "activity", "value")


def build_keys(mapping: pl.DataFrame, sut: pl.DataFrame, years: list[int]) -> pl.DataFrame:
    """Allocation factors by year, flow, product and activity."""
    # Direct flows: factor one, every year.
    # Flux directs : facteur un, chaque année.
    direct = mapping.filter(pl.col("method") == "direct").join(
        pl.DataFrame({"year": years}, schema={"year": pl.Int16}), how="cross").with_columns(factor=pl.lit(1.0))

    # Keyed flows: shares of the key product used by each listed activity.
    # Flux à clé : parts du produit clé utilisées par chaque activité de la liste.
    keyed = mapping.filter(pl.col("method") == "key")
    weights = pl.concat([product_use(sut, p).with_columns(key_product=pl.lit(p)) for p in keyed["key_product"].unique()])
    split = (keyed.join(weights, on=["activity", "key_product"], how="left")
             .filter(pl.col("year").is_in(years))
             .with_columns(pl.col("value").fill_null(0))
             .with_columns(factor=pl.col("value") / pl.col("value").sum().over("year", "iea_flow", "iea_product")))
    columns = ["year", "iea_flow", "iea_product", "activity", "method", "factor"]
    return pl.concat([direct.select(columns), split.select(columns)]).sort(columns[:4], nulls_last=True)


def main() -> pl.DataFrame:
    sut = read_intermediate("sut")
    iea = read_intermediate("balance_iea")
    mapping = read_lookup("balance_to_activities")

    # Every flow of the Tunisian balance must have a rule.
    # Chaque flux du bilan tunisien doit avoir une règle.
    missing = set(iea["iea_flow"]) - set(mapping["iea_flow"]) - NOT_ACTIVITIES
    assert not missing, f"Flows without a rule: {missing}"

    years = sorted(iea["year"].unique().to_list())
    keys = build_keys(mapping, sut, years)
    write_intermediate(keys, "activity_keys")

    sums = keys.group_by("year", "iea_flow", "iea_product").agg(pl.col("factor").sum())
    checks = Checks(SCRIPT)
    checks.add("factors_sum_to_one", (sums["factor"] - 1).abs().max(), 1e-9, "share", "Factors of each flow add up to one")
    checks.save()
    return keys


if __name__ == "__main__":
    main()
