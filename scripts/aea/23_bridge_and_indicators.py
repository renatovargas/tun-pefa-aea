"""Bridge the air emissions accounts to the inventory, check them and derive indicators.

Why    : the accounts and the inventory measure the same emissions under two principles
         (residence and territory). A bridge table shows how one total becomes the other, as
         the Eurostat manual requires. The emissions that each industry reports must also be
         consistent with the fossil fuels it uses in the energy accounts, and emissions become
         indicators once related to output, value added and household spending.
Inputs : data/intermediate/aea.parquet (script 22), ghg_inventory.parquet (script 20),
         pefa.parquet (script 13), sut.parquet (script 03), crt.parquet (script 02)
Outputs: data/intermediate/aea_bridge.parquet           bridging items by year and gas
         data/intermediate/aea_bunkers_vs_oecd.parquet  inventory bunkers against OECD resident transport
         data/intermediate/implied_factors_crt.parquet  CO2 per TJ by fuel in the inventory
         data/intermediate/implied_factors_pefa.parquet CO2 of combustion per TJ of fossil fuel, by activity
         data/intermediate/aea_indicators.parquet       emissions and intensities by activity
         data/outputs/checks/23_bridge_and_indicators.csv
Method : the bridge starts from the accounts total, subtracts emissions of residents abroad,
         adds those of non-residents on the territory and other adjustments, and must land on
         the inventory total without LULUCF; LULUCF is then added. Implied emission factors
         divide CO2 from fuel combustion (1.A) by the fossil energy that each activity uses in
         the energy accounts, and should stay within the range of factors in the inventory.
Run    : uv run python scripts/aea/23_bridge_and_indicators.py

Passage des comptes AEA à l'inventaire, contrôles et indicateurs. Le tableau de passage part
du total des comptes, retire les résidents à l'étranger, ajoute les non-résidents sur le
territoire et doit retrouver le total de l'inventaire hors UTCATF. Les facteurs d'émission
implicites rapportent le CO2 de la combustion à l'énergie fossile des comptes PEFA.
"""

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import HOUSEHOLDS, PSEUDO_ACTIVITIES, Checks, read_intermediate, read_lookup, write_intermediate  # noqa: E402

SCRIPT = "23_bridge_and_indicators"
ITEMS = ["NRA-AIR", "NRA-WATER", "NRT-AIR", "NRT-WATER", "OTHER"]
FOSSIL = ["Coal", "Peat and peat products", "Oil shale / oil sands", "Natural gas", "Oil"]
END_USE = "End-use of energy products by SIEC class:"


def main() -> None:
    aea = read_intermediate("aea")
    inventory = read_intermediate("ghg_inventory")
    pefa = read_intermediate("pefa")
    sut = read_intermediate("sut")
    activities = read_lookup("activities")
    accounts_activities = [c for c in activities["code"] if c not in PSEUDO_ACTIVITIES]
    checks = Checks(SCRIPT)

    # Bridge table by gas: accounts, bridging items, inventory without and with LULUCF.
    # Tableau de passage par gaz : comptes, éléments de passage, inventaire hors et avec UTCATF.
    def by_gas(table: pl.DataFrame, item: str) -> pl.DataFrame:
        return table.group_by("year", "gas").agg(kt=pl.col("kt_co2_eq").sum()).with_columns(item=pl.lit(item))

    detail = aea.filter(pl.col("gas") != "GHG")
    items = pl.concat([
        by_gas(detail.filter(pl.col("activity") == "AEA-TOTAL"), "AEA"),
        *[by_gas(detail.filter(pl.col("activity") == e), e) for e in ["NRA-AIR", "NRT-AIR", "NRT-WATER", "OTHER", "LULUCF"]],
        # The positive gap of vessels is added to activities by the tool without a bridging item (open question).
        # L'écart positif des navires est ajouté aux activités par l'outil sans élément de passage (question ouverte).
        by_gas(detail.filter(pl.col("source") == "ALL_VESSELS", pl.col("activity").is_in(accounts_activities)), "NRA-WATER"),
        by_gas(inventory.filter(pl.col("scope") == "inventory"), "INV"),
    ])
    items = pl.concat([items, items.group_by("year", "item").agg(pl.col("kt").sum()).with_columns(gas=pl.lit("GHG")).select(items.columns)])
    bridge = (items.pivot("item", index=["year", "gas"], values="kt").fill_null(0)
              .with_columns(pl.lit(0.0).alias(c) for c in ITEMS if c not in items["item"])
              .with_columns(computed=pl.col("AEA") - pl.col("NRA-AIR") - pl.col("NRA-WATER") + pl.col("NRT-AIR") + pl.col("NRT-WATER") + pl.col("OTHER"))
              .with_columns(gap=pl.col("computed") - pl.col("INV"), **{"INV-TOTAL": pl.col("INV") + pl.col("LULUCF")})
              .sort("year", "gas"))
    tool_total = aea.filter(pl.col("gas") == "GHG", pl.col("activity") == "INV-TOTAL").select("year", tool_inv_total="kt_co2_eq")
    bridge = bridge.join(tool_total.with_columns(gas=pl.lit("GHG")), on=["year", "gas"], how="left")
    write_intermediate(bridge, "aea_bridge")
    checks.add("bridge_closes", bridge["gap"].abs().max(), 1e-6, "kt CO2 eq", "Accounts plus bridging items minus the inventory without LULUCF")

    # Resident carriers abroad (OECD) against international bunkers (memo items 1.D of the inventory).
    # Transporteurs résidents à l'étranger (OCDE) et soutes internationales (éléments pour mémoire 1.D).
    bunkers = (inventory.filter(pl.col("crt").is_in(["1.D.1.a", "1.D.1.b"]), pl.col("gas") == "CO2")
               .pivot("crt", index="year", values="kt", aggregate_function="sum")
               .rename({"1.D.1.a": "aviation_bunkers_kt", "1.D.1.b": "marine_bunkers_kt"}))
    write_intermediate(
        bridge.filter(pl.col("gas") == "CO2").select("year", oecd_air_residents_kt="NRA-AIR", oecd_sea_residents_kt="NRA-WATER")
        .join(bunkers, on="year").sort("year"), "aea_bunkers_vs_oecd")

    # Implied CO2 factors of the inventory by fuel, for fuel combustion (1.A).
    # Facteurs de CO2 implicites de l'inventaire par combustible, pour la combustion (1.A).
    crt = read_intermediate("crt").filter(pl.col("crt").str.starts_with("1.A."))
    energy = crt.filter(pl.col("parameter") == "activity", pl.col("unit") == "TJ").group_by("year", "fuel").agg(tj=pl.col("value").sum())
    co2 = crt.filter(pl.col("parameter") == "emission", pl.col("gas") == "CO2").group_by("year", "fuel").agg(co2_kt=pl.col("value").sum())
    crt_factors = (energy.join(co2, on=["year", "fuel"]).filter(pl.col("tj") > 0, pl.col("fuel") != "biomass")
                   .with_columns(t_co2_per_tj=1000 * pl.col("co2_kt") / pl.col("tj")).sort("year", "t_co2_per_tj"))
    write_intermediate(crt_factors, "implied_factors_crt")

    # Implied factors by activity: CO2 of combustion in the accounts over fossil end use in the energy accounts.
    # Facteurs implicites par activité : CO2 de la combustion des comptes AEA sur l'utilisation finale d'énergie fossile des comptes PEFA.
    fossil = (pefa.filter(pl.col("quadrant") == "Use", pl.col("level2") == END_USE, pl.col("product").is_in(FOSSIL),
                          pl.col("activity").is_in(accounts_activities))
              .group_by("year", "activity").agg(fossil_tj=pl.col("tj").sum()))
    combustion = (aea.filter(pl.col("gas") == "CO2", pl.col("source").str.starts_with("1.A."), pl.col("activity").is_in(accounts_activities))
                  .group_by("year", "activity").agg(co2_kt=pl.col("kt_co2_eq").sum()))
    pefa_factors = (combustion.join(fossil, on=["year", "activity"], how="full", coalesce=True)
                    .with_columns(pl.col("co2_kt", "fossil_tj").fill_null(0))
                    .with_columns(t_co2_per_tj=pl.when(pl.col("fossil_tj") > 0).then(1000 * pl.col("co2_kt") / pl.col("fossil_tj")))
                    .sort("year", "activity"))
    write_intermediate(pefa_factors, "implied_factors_pefa")

    # Emission intensities: GHG per million TND of output, of value added and, for households, of consumption.
    # Intensités d'émission : GES par million de TND de production, de valeur ajoutée et, pour les ménages, de consommation.
    production_accounts = (sut.filter(pl.col("block") == "value_added", pl.col("row").is_in(["P1", "B1G"]))
                           .pivot("row", index=["year", "column"], values="value")
                           .rename({"column": "activity", "P1": "output_mtnd", "B1G": "value_added_mtnd"}))
    household_spending = (sut.filter(pl.col("block") == "use", pl.col("column") == "P3_HH", ~pl.col("aggregate"))
                          .group_by("year").agg(household_consumption_mtnd=pl.col("value").sum()).with_columns(activity=pl.lit(HOUSEHOLDS)))
    by_gas_wide = (aea.filter(pl.col("activity").is_in(accounts_activities))
                   .group_by("year", "activity", "gas").agg(pl.col("kt_co2_eq").sum())
                   .pivot("gas", index=["year", "activity"], values="kt_co2_eq").fill_null(0)
                   .rename({"CO2": "co2_kt", "CH4": "ch4_kt_co2_eq", "N2O": "n2o_kt_co2_eq", "F-gases": "fgases_kt_co2_eq", "GHG": "ghg_kt"}))
    indicators = (by_gas_wide.join(production_accounts, on=["year", "activity"], how="left")
                  .join(household_spending, on=["year", "activity"], how="left")
                  .with_columns(ghg_intensity_output=1000 * pl.col("ghg_kt") / pl.col("output_mtnd"),
                                ghg_intensity_value_added=1000 * pl.col("ghg_kt") / pl.col("value_added_mtnd"),
                                ghg_intensity_household=1000 * pl.col("ghg_kt") / pl.col("household_consumption_mtnd"))
                  .sort("year", "activity"))
    write_intermediate(indicators, "aea_indicators")
    checks.save()


if __name__ == "__main__":
    main()
