"""Map the Tunisian energy balance to the IEA template read by the PEFA Converter.

Why    : the PEFA Converter reads an energy balance laid out like the balances of the
         International Energy Agency (IEA): 95 flows in a fixed order, 63 products, values in
         terajoules and IEA sign conventions. The ONEM balance has its own flows, products,
         units and signs.
Inputs : data/intermediate/energy_balances.parquet (script 01)
         data/lookups/balance_flows.csv, balance_products.csv (default correspondence and sign)
         data/lookups/balance_template_exceptions.csv (cells that leave the default correspondence)
         imf-tools/pefa-converter/PEFA_Converter.xlsm (sheet Energy_Balance_Template)
Outputs: data/intermediate/balance_iea.parquet  year, flow, product, iea_flow, iea_product, tj
         data/outputs/checks/10_map_balance_to_iea_template.csv
Method : every elementary cell (flow and product that are not totals) receives the IEA flow
         and product of its row and column, unless an exception names another destination.
         Values are multiplied by the IEA sign of the flow (exports, bunkers, transformation
         inputs and own use are negative). Totals are left out, since the tool rebuilds them.
Run    : uv run python scripts/pefa/10_map_balance_to_iea_template.py

Transposition du bilan tunisien dans le modèle de l'AIE lu par le PEFA Converter. Chaque
cellule élémentaire reçoit le flux et le produit du modèle de sa ligne et de sa colonne, sauf
exception documentée, et prend le signe de l'AIE. Les totaux sont laissés de côté.
"""

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import imf_tools  # noqa: E402
from common import KTOE_TO_TJ, Checks, read_intermediate, read_lookup, write_intermediate  # noqa: E402

SCRIPT = "10_map_balance_to_iea_template"


def to_template(balances: pl.DataFrame, flows: pl.DataFrame, products: pl.DataFrame, exceptions: pl.DataFrame) -> pl.DataFrame:
    """Move the long ONEM balance to the flows and products of the IEA template (TJ, IEA signs)."""
    # Default correspondence: only elementary cells have both an IEA flow and an IEA product.
    # Correspondance par défaut : seules les cellules élémentaires ont un flux et un produit de l'AIE.
    default = (
        balances.join(flows.select(pl.col("code").alias("flow"), "iea_flow", "iea_sign"), on="flow")
        .join(products.select(pl.col("code").alias("product"), "iea_product"), on="product")
        .filter(pl.col("iea_flow").is_not_null() & pl.col("iea_product").is_not_null())
    )
    # Exceptions replace the flow, the product or the sign of specific cells.
    # Les exceptions remplacent le flux, le produit ou le signe de cellules précises.
    rules = exceptions.select("flow", "product", pl.col("iea_flow").alias("flow_x"),
                              pl.col("iea_product").alias("product_x"), pl.col("iea_sign").cast(pl.Int64).alias("sign_x"))
    return (
        default.join(rules, on=["flow", "product"], how="left")
        .with_columns(iea_flow=pl.coalesce("flow_x", "iea_flow"), iea_product=pl.coalesce("product_x", "iea_product"),
                      iea_sign=pl.coalesce("sign_x", "iea_sign"))
        .with_columns(tj=pl.col("tj") * pl.col("iea_sign"))
        .select("year", "flow", "product", "iea_flow", "iea_product", "tj")
    )


def main() -> pl.DataFrame:
    balances = read_intermediate("energy_balances")
    flows, products = read_lookup("balance_flows"), read_lookup("balance_products")
    exceptions = read_lookup("balance_template_exceptions")
    template_flows, template_products = imf_tools.template_flows(), imf_tools.template_products()

    # Map and make sure that every label exists in the template.
    # Transposer et vérifier que chaque libellé existe dans le modèle.
    iea = to_template(balances, flows, products, exceptions)
    unknown = (set(iea["iea_flow"]) - set(template_flows)) | (set(iea["iea_product"]) - set(template_products))
    assert not unknown, f"Labels missing from the template: {unknown}"
    write_intermediate(iea, "balance_iea")

    # Conservation: the absolute energy of elementary cells is the same before and after.
    # Conservation : l'énergie en valeur absolue des cellules élémentaires est la même avant et après.
    elementary = balances.filter(
        pl.col("flow").is_in(flows.filter(pl.col("iea_flow").is_not_null())["code"].implode()),
        pl.col("product").is_in(products.filter(pl.col("iea_product").is_not_null())["code"].implode()))
    before = elementary.group_by("year").agg((pl.col("ktoe").abs().sum() * KTOE_TO_TJ).alias("before"))
    after = iea.group_by("year").agg(pl.col("tj").abs().sum().alias("after"))
    conservation = before.join(after, on="year").with_columns(gap=pl.col("before") - pl.col("after"))

    # IEA identity by product: supply net of transformation, own use and losses equals final consumption.
    # Identité de l'AIE par produit : les ressources nettes de transformation, d'autoconsommation et de pertes égalent la consommation finale.
    final = flows.filter(pl.col("code").str.contains(r"^(IND|TRA|OTH|NEU)_"))["code"].to_list()
    identity = (iea.with_columns(final=pl.col("flow").is_in(final))
                .group_by("year", "product")
                .agg(pl.col("tj").filter(~pl.col("final")).sum().alias("net_supply"),
                     pl.col("tj").filter(pl.col("final")).sum().alias("final_consumption"))
                .with_columns(gap=pl.col("net_supply") - pl.col("final_consumption")))

    checks = Checks(SCRIPT)
    checks.add("conservation", conservation["gap"].abs().max(), 1e-6, "TJ", "Energy of elementary cells before and after the mapping")
    checks.add("iea_identity", identity["gap"].abs().max() / KTOE_TO_TJ, 3.5, "ktoe",
               "Largest gap between net supply and final consumption by product (rounding of the published balance)")
    checks.save()
    return iea


if __name__ == "__main__":
    main()
