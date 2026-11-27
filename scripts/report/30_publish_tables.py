"""Publish the tables and labels that the documents, presentations and data explorer read.

Why    : the documents only describe and display results. They never compute them, so a
         change of wording never requires running the pipeline again. Everything they show
         comes from the tidy tables written here, which are the reference version of the
         results, and every label they print comes from the label tables written here.
Inputs : data/intermediate/*.parquet (scripts 01 to 23), data/outputs/checks/*.csv,
         data/lookups/*.csv
Outputs: data/outputs/tables/<name>.parquet and .csv  tidy tables with codes, no labels
         data/outputs/labels/<dimension>.csv           code, en, fr, ar for every dimension
         data/outputs/labels/all_labels.csv            the same in one long table
Method : intermediate tables are copied under stable names, two flow tables are derived for
         the Sankey diagrams (energy by origin, product and use; emissions by inventory sector
         and activity), and the checks of all scripts are gathered in one table.
Run    : uv run python scripts/report/30_publish_tables.py

Publication des tableaux et des libellés lus par les documents, les présentations et
l'explorateur de données. Les documents ne calculent rien : tout ce qu'ils montrent vient de
ces tableaux, et tous leurs libellés viennent des tables de libellés publiées ici.
"""

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import (CHECKS, HOUSEHOLDS, LABELS, LOOKUPS, read_intermediate, read_lookup, write_output_table, log)  # noqa: E402

# Intermediate tables published as they are, under the name the documents use.
# Tableaux intermédiaires publiés tels quels, sous le nom qu'utilisent les documents.
PUBLISHED = {
    "energy_balances": "energy_balance",
    "balance_iea": "energy_balance_iea",
    "activity_keys": "pefa_activity_keys",
    "concordance_changes": "pefa_concordance_changes",
    "bunkers_check": "pefa_bunkers_check",
    "pefa": "pefa_supply_use",
    "pefa_isic": "pefa_supply_use_default_matrix",
    "pefa_layers": "pefa_tool_agreement",
    "pefa_balance_categories": "pefa_balance_categories",
    "pefa_balance_products": "pefa_balance_products",
    "pefa_plausibility": "pefa_plausibility",
    "pefa_indicators": "pefa_indicators",
    "ghg_inventory": "ghg_inventory",
    "unfccc_file_check": "ghg_prepared_file_check",
    "categories_without_factor": "aea_categories_without_factor",
    "conversion_matrix": "aea_conversion_matrix",
    "conversion_changes": "aea_conversion_changes",
    "aea": "aea_emissions",
    "aea_layers": "aea_tool_agreement",
    "aea_bridge": "aea_bridge",
    "aea_bunkers_vs_oecd": "aea_bunkers_vs_oecd",
    "implied_factors_crt": "aea_implied_factors_inventory",
    "implied_factors_pefa": "aea_implied_factors_accounts",
    "aea_indicators": "aea_indicators",
}

# Lookups published as label tables (code column, then languages).
# Nomenclatures publiées comme tables de libellés (colonne de code, puis langues).
LABEL_TABLES = {
    "activities": "code", "imf_sections": "code", "balance_flows": "code", "balance_products": "code",
    "pefa_rows": "key", "gases": "code", "aea_bridge": "code", "sut_products": "code", "sut_columns": "code",
    "crt_categories": "code", "terms": "key",
}


def energy_sankey(pefa: pl.DataFrame, sections: dict[str, str]) -> pl.DataFrame:
    """Energy flows by origin, product and use, for Sankey diagrams (TJ).

    Left: domestic production or imports of each energy product. Right: what each product is
    used for: transformation into other energy products, end use by ISIC section or by
    households, exports and bunkers, stock changes and the statistical difference.
    """
    products = pefa.filter(pl.col("level1") == "Energy products:").with_columns(
        product=pl.when(pl.col("product") == "End-use of energy products for non-energy purposes").then(pl.lit("Oil")).otherwise("product"))
    supply = (products.filter(pl.col("quadrant") == "Supply")
              .with_columns(source=pl.when(pl.col("activity") == "ROW").then(pl.lit("IMP")).otherwise(pl.lit("PROD")), target=pl.col("product")))
    use = (products.filter(pl.col("quadrant") == "Use")
           .with_columns(source=pl.col("product"),
                         target=pl.when(pl.col("level2") == "Transformation of energy products by SIEC class:").then(pl.lit("TRANSF"))
                         .when(pl.col("activity") == "ROW").then(pl.lit("EXP"))
                         .when(pl.col("activity") == "ACC").then(pl.lit("STOCK"))
                         .when(pl.col("activity") == "STATDIFF").then(pl.lit("STATDIFF"))
                         .otherwise(pl.col("activity").replace_strict(sections))))
    flows = pl.concat([supply.with_columns(stage=pl.lit("supply")), use.with_columns(stage=pl.lit("use"))])
    return (flows.group_by("year", "stage", "source", "target").agg(pl.col("tj").sum())
            .filter(pl.col("tj").abs() > 0.5).sort("year", "stage", "source", "target"))


def emissions_sankey(aea: pl.DataFrame, sections: dict[str, str]) -> pl.DataFrame:
    """Greenhouse gas emissions by inventory category (level 2) and ISIC section of the emitter (kt CO2 eq)."""
    activities = [c for c in sections if c not in ("ROW", "ACC", "ENV", "STATDIFF")]
    data = aea.filter(pl.col("gas") == "GHG", pl.col("activity").is_in(activities))
    return (data.with_columns(
                category=pl.when(pl.col("source").str.contains(r"^\d")).then(pl.col("source").str.extract(r"^(\d(?:\.[A-Z])?)"))
                .otherwise(pl.lit("RES")),
                section=pl.col("activity").replace_strict(sections))
            .group_by("year", "category", "section").agg(kt_co2_eq=pl.col("kt_co2_eq").sum())
            .filter(pl.col("kt_co2_eq").abs() > 0.05).sort("year", "category", "section"))


def main() -> None:
    # Copy the intermediate tables under their published names.
    # Copier les tableaux intermédiaires sous leur nom publié.
    for source, name in PUBLISHED.items():
        write_output_table(read_intermediate(source), name)

    # Derived tables for diagrams, and national accounts aggregates used as denominators.
    # Tableaux dérivés pour les diagrammes, et agrégats des comptes nationaux utilisés comme dénominateurs.
    sections = dict(read_lookup("activities").select("code", "imf_section").iter_rows())
    write_output_table(energy_sankey(read_intermediate("pefa"), sections), "pefa_sankey")
    write_output_table(emissions_sankey(read_intermediate("aea"), sections), "aea_sankey")
    sut = read_intermediate("sut")
    production = (sut.filter(pl.col("block") == "value_added", pl.col("row").is_in(["P1", "B1G"]))
                  .pivot("row", index=["year", "column"], values="value")
                  .rename({"column": "activity", "P1": "output_mtnd", "B1G": "value_added_mtnd"}))
    households = (sut.filter(pl.col("block") == "use", pl.col("column") == "P3_HH", ~pl.col("aggregate"))
                  .group_by("year").agg(output_mtnd=pl.col("value").sum()).with_columns(activity=pl.lit(HOUSEHOLDS), value_added_mtnd=pl.lit(None, pl.Float64)))
    write_output_table(pl.concat([production, households.select(production.columns)]).sort("year", "activity"), "sut_production_accounts")
    energy_purchases = (sut.filter(pl.col("block") == "use", pl.col("row").is_in(["06", "19", "35"]), ~pl.col("aggregate"))
                        .with_columns(activity=pl.when(pl.col("column") == "P3_HH").then(pl.lit(HOUSEHOLDS)).otherwise(pl.col("column")))
                        .select("year", "row", "activity", "value"))
    write_output_table(energy_purchases, "sut_energy_purchases")

    # All checks in one table.
    # Tous les contrôles dans un seul tableau.
    checks = pl.concat([pl.read_csv(f) for f in sorted(CHECKS.glob("*.csv"))])
    write_output_table(checks, "checks")

    # Label tables in three languages.
    # Tables de libellés en trois langues.
    LABELS.mkdir(parents=True, exist_ok=True)
    long = []
    for name, key in LABEL_TABLES.items():
        table = read_lookup(name)
        extra = [c for c in ("order", "level", "parent", "type", "imf_section") if c in table.columns]
        table = table.select(pl.col(key).cast(pl.String).alias("code"), *extra, "en", "fr", "ar")
        table.write_csv(LABELS / f"{name}.csv")
        long.append(table.select(pl.lit(name).alias("dimension"), "code", "en", "fr", "ar"))
    pl.concat(long).write_csv(LABELS / "all_labels.csv")
    log(f"wrote {len(LABEL_TABLES)} label tables to {LABELS.relative_to(LOOKUPS.parents[1])}")


if __name__ == "__main__":
    main()
