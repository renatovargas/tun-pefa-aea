"""Check the energy accounts and derive their indicators.

Why    : supply must equal use for every category and product, the energy that each
         industry uses must be consistent with what it buys in the national accounts, and
         the accounts become useful once related to output and value added.
Inputs : data/intermediate/pefa.parquet (script 13), balance_iea.parquet (script 10),
         sut.parquet (script 03)
         data/lookups/activities.csv, balance_products.csv
Outputs: data/intermediate/pefa_balance_categories.parquet  supply and use by year and category
         data/intermediate/pefa_balance_products.parquet    supply and use by year and energy product
         data/intermediate/pefa_plausibility.parquet        energy used and energy purchased, by industry
         data/intermediate/pefa_indicators.parquet          energy aggregates and intensities by activity
         data/outputs/checks/14_check_pefa_and_indicators.csv
Method : natural inputs and residuals must balance exactly, because the converter creates
         both sides of each flow. Energy products balance up to the rounding of the published
         balance and its statistical difference. Plausibility compares, for each industry,
         the energy used (TJ) with its purchases of crude oil and gas (06), refined products
         (19) and electricity and gas (35) in the supply and use tables, which gives an
         implied price. Indicators follow the Indicator sheet of the IMF tool and key indicator 6
         of the Eurostat PEFA manual (net domestic energy use), and relate end use to output
         and value added at current prices.
Run    : uv run python scripts/pefa/14_check_pefa_and_indicators.py

Contrôles et indicateurs des comptes de l'énergie. Le script vérifie l'égalité des ressources
et des emplois, compare l'énergie utilisée par chaque branche à ses achats d'énergie dans le
TRE (prix implicite), et calcule l'utilisation intérieure nette d'énergie et les intensités
énergétiques par branche.
"""

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import HOUSEHOLDS, KTOE_TO_TJ, PSEUDO_ACTIVITIES, Checks, read_intermediate, read_lookup, write_intermediate  # noqa: E402

SCRIPT = "14_check_pefa_and_indicators"
END_USE = "End-use of energy products by SIEC class:"
NON_ENERGY = "End-use of energy products for non-energy purposes"


def supply_use(table: pl.DataFrame, by: list[str]) -> pl.DataFrame:
    return (table.group_by(by)
            .agg(pl.col("tj").filter(pl.col("quadrant") == "Supply").sum().alias("supply_tj"),
                 pl.col("tj").filter(pl.col("quadrant") == "Use").sum().alias("use_tj"))
            .with_columns(gap_ktoe=(pl.col("supply_tj") - pl.col("use_tj")) / KTOE_TO_TJ)
            .sort(by))


def main() -> None:
    pefa = read_intermediate("pefa")
    iea = read_intermediate("balance_iea")
    sut = read_intermediate("sut")
    activities = read_lookup("activities")
    industries = activities.filter(~pl.col("code").is_in(PSEUDO_ACTIVITIES + [HOUSEHOLDS]))["code"].to_list()
    years = sorted(pefa["year"].unique().to_list())
    checks = Checks(SCRIPT)

    # Supply and use by category: natural inputs and residuals balance exactly.
    # Ressources et emplois par catégorie : ressources naturelles et résidus s'équilibrent exactement.
    categories = supply_use(pefa, ["year", "level1"])
    write_intermediate(categories, "pefa_balance_categories")
    checks.add("natural_inputs_and_residuals_balance",
               categories.filter(pl.col("level1") != "Energy products:")["gap_ktoe"].abs().max(), 1e-6, "ktoe",
               "Supply minus use of natural inputs and residuals")

    # Supply and use by energy product. Non-energy use is recorded under its own product in the
    # use table, so it is counted with oil, the only product used for non-energy purposes in Tunisia.
    # Ressources et emplois par produit. Les usages non énergétiques ont leur propre ligne dans le
    # tableau des emplois ; ils sont comptés avec le pétrole, seul produit concerné en Tunisie.
    non_energy = iea.filter(pl.col("iea_flow").str.starts_with("Non-energy use"))
    oil_products = read_lookup("balance_products").filter(pl.col("parent") == "OILPROD")["code"]
    assert non_energy["product"].is_in(oil_products.implode()).all(), "Non-energy use of a product other than oil"
    products = supply_use(
        pefa.filter(pl.col("level1") == "Energy products:")
        .with_columns(product=pl.when(pl.col("product") == NON_ENERGY).then(pl.lit("Oil")).otherwise("product")),
        ["year", "product"])
    write_intermediate(products, "pefa_balance_products")
    checks.add("energy_products_balance", products["gap_ktoe"].abs().max(), 5, "ktoe",
               "Supply minus use by energy product (rounding and statistical difference of the balance)")

    # Plausibility: energy used by each industry against its purchases of energy products in the SUT.
    # Vraisemblance : énergie utilisée par chaque branche et ses achats de produits énergétiques dans le TRE.
    end_use = (pefa.filter(pl.col("quadrant") == "Use", pl.col("level1") == "Energy products:", pl.col("level2") == END_USE,
                           pl.col("activity").is_in(industries + [HOUSEHOLDS]))
               .group_by("year", "activity").agg(pl.col("tj").sum().alias("energy_tj")))
    purchases = (sut.filter(pl.col("block") == "use", pl.col("row").is_in(["06", "19", "35"]), ~pl.col("aggregate"),
                            pl.col("year").is_in(years))
                 .with_columns(activity=pl.when(pl.col("column") == "P3_HH").then(pl.lit(HOUSEHOLDS)).otherwise(pl.col("column")))
                 .filter(pl.col("activity").is_in(industries + [HOUSEHOLDS]))
                 .group_by("year", "activity").agg(pl.col("value").sum().alias("purchases_mtnd")))
    plausibility = (end_use.join(purchases, on=["year", "activity"], how="full", coalesce=True)
                    .with_columns(pl.col("energy_tj", "purchases_mtnd").fill_null(0))
                    .with_columns(implied_price_tnd_per_gj=pl.when(pl.col("energy_tj") > 0)
                                  .then(pl.col("purchases_mtnd") * 1e6 / (pl.col("energy_tj") * 1e3)))
                    .with_columns(flag=pl.when((pl.col("energy_tj") > 0) & (pl.col("purchases_mtnd") <= 0)).then(pl.lit("energy_without_purchases"))
                                  .when((pl.col("energy_tj") <= 0) & (pl.col("purchases_mtnd") > 0)).then(pl.lit("purchases_without_energy")))
                    .sort("year", "activity"))
    write_intermediate(plausibility, "pefa_plausibility")

    # Aggregates by activity, following the Indicator sheet of the PEFA Converter.
    # Agrégats par activité, d'après la feuille Indicator du PEFA Converter.
    def by_activity(name: str, condition: pl.Expr) -> pl.DataFrame:
        return pefa.filter(condition).group_by("year", "activity").agg(pl.col("tj").sum().alias("tj")).with_columns(indicator=pl.lit(name))

    use, supply = pl.col("quadrant") == "Use", pl.col("quadrant") == "Supply"
    aggregates = pl.concat([
        by_activity("natural_inputs", use & (pl.col("level1") == "Energy from natural inputs:")),
        by_activity("production", supply & (pl.col("level2") == "Production of energy products by SIEC class:")),
        by_activity("transformation_input", use & (pl.col("level2") == "Transformation of energy products by SIEC class:")),
        by_activity("end_use_energy", use & (pl.col("level2") == END_USE) & (pl.col("product") != NON_ENERGY)),
        by_activity("end_use_non_energy", use & (pl.col("product") == NON_ENERGY)),
        by_activity("residuals", supply & (pl.col("level1") == "Energy residuals:")),
    ]).pivot("indicator", index=["year", "activity"], values="tj").fill_null(0)
    # Net domestic energy use follows key indicator 6 of the Eurostat PEFA manual (2014, paragraphs 101 to 105):
    # energy residuals supplied by each activity plus energy kept in products used for non-energy purposes.
    # It avoids the double counting of energy that is transformed before its end use.
    # L'utilisation intérieure nette d'énergie suit l'indicateur clé 6 du manuel PEFA d'Eurostat (2014, §101 à 105) :
    # résidus d'énergie fournis par chaque activité plus énergie incorporée dans les produits à usage non énergétique.
    aggregates = aggregates.with_columns(net_domestic_energy_use=pl.col("residuals") + pl.col("end_use_non_energy"))

    # Intensities: end use for energy purposes per million TND of output and of value added (current prices).
    # Intensités : utilisation finale à des fins énergétiques par million de TND de production et de valeur ajoutée (prix courants).
    accounts = (sut.filter(pl.col("block") == "value_added", pl.col("row").is_in(["P1", "B1G"]))
                .pivot("row", index=["year", "column"], values="value")
                .rename({"column": "activity", "P1": "output_mtnd", "B1G": "value_added_mtnd"}))
    household_spending = (sut.filter(pl.col("block") == "use", pl.col("column") == "P3_HH", ~pl.col("aggregate"))
                          .group_by("year").agg(household_consumption_mtnd=pl.col("value").sum())
                          .with_columns(activity=pl.lit(HOUSEHOLDS)))
    indicators = (aggregates.filter(pl.col("activity").is_in(industries + [HOUSEHOLDS]))
                  .join(accounts, on=["year", "activity"], how="left")
                  .join(household_spending, on=["year", "activity"], how="left")
                  .with_columns(intensity_output=pl.col("end_use_energy") / pl.col("output_mtnd"),
                                intensity_value_added=pl.col("end_use_energy") / pl.col("value_added_mtnd"),
                                intensity_household=pl.col("end_use_energy") / pl.col("household_consumption_mtnd"))
                  .sort("year", "activity"))
    write_intermediate(indicators, "pefa_indicators")
    checks.save()


if __name__ == "__main__":
    main()
