"""Compile the air emissions accounts (AEA) for greenhouse gases, 2015 to 2022.

Why    : this is the core of the emissions accounts. The IMF tool (function I2A) allocates
         the inventory to activities with the conversion matrix and moves from the territory
         principle of the inventory to the residence principle of the national accounts with
         OECD estimates for air and maritime transport. The script re-implements every rule of
         I2A in polars and calls the tool itself as a reference: both must agree to 1e-9 kt.
Inputs : data/intermediate/ghg_inventory.parquet (script 20), conversion_matrix.parquet (script 21)
         imf-tools/i2a/I2A.xlsm, I2A.py and I2A_Data/DSD_*_TUN.csv (OECD transport emissions)
         data/lookups/activities.csv
Outputs: data/intermediate/aea.parquet         year, gas, source, activity, kt_co2_eq
         data/intermediate/aea_layers.parquet  agreement between the tool and the explicit layer, by run
         data/outputs/checks/22_compile_aea_tables.csv
Method : (1) the inventory is laid out as the tool's Inventory range; (2) OECD emissions of
         resident air carriers abroad and of all resident vessels are read; (3) inventory and
         OECD emissions are multiplied by the factors of the matrix; (4) the residence
         adjustments compare OECD and inventory figures for domestic aviation and navigation
         and record the differences as bridging items (residents abroad, non-residents on the
         territory); (5) totals and the sum of greenhouse gases are added. The tool is run with
         its default matrix (with and without OECD data) and with the Tunisian matrix.
Run    : uv run python scripts/aea/22_compile_aea_tables.py

Compilation des comptes des émissions atmosphériques (AEA). Le script reprend en polars
chaque règle de la fonction I2A de l'outil du FMI (Achille Pegoue) : attribution par la
matrice de conversion, ajustements de résidence à partir des données de l'OCDE sur les
transports aérien et maritime, totaux. Il appelle l'outil comme référence.
"""

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import imf_tools  # noqa: E402
from common import PSEUDO_ACTIVITIES, Checks, log, read_intermediate, read_lookup, write_intermediate  # noqa: E402

SCRIPT = "22_compile_aea_tables"
KEYS = ["POLLUTANT", "Source_Code", "Activity", "year"]
TOLERANCE_KT = 1e-9
TOOL_GASES = ["CH4", "CO2", "N2O", "F-gases"]
INVENTORY_HEADER = ["Info", "Data_Source", "IPCC_annex", "CountryRegion", "REF_AREA", "CountryName",
                    "POLLUTANT", "Source_Code", "Source_Description", "FossilType"]
RESIDENTS_ABROAD = ["RES_DOM_OUT", "RES_INT_FROM", "RES_INT_TO", "RES_INT_OUT"]

RANGES = imf_tools.i2a_ranges()
DESCRIPTIONS = {r[1]: r[2] for r in RANGES["CRT"][1:]}
AIR_CODE = next(r[1] for r in RANGES["CRT"][1:] if r[11] == "Domestic Aviation")
SEA_CODE = next(r[1] for r in RANGES["CRT"][1:] if r[11] == "Domestic Navigation")


# ---------------------------------------------------------------------------
# (1) The inventory as the Inventory range of the tool.
# (1) L'inventaire sous la forme de la plage Inventory de l'outil.
# ---------------------------------------------------------------------------

def inventory_range(inventory: pl.DataFrame, years: list[int]) -> list[list]:
    """Inventory_2 range: one row per gas and tool code, one column per year (kt CO2 eq)."""
    wide = (inventory.filter(pl.col("year").is_in(years))
            .group_by("gas", "tool_code", "year").agg(pl.col("kt_co2_eq").sum())
            .pivot("year", index=["gas", "tool_code"], values="kt_co2_eq").sort("gas", "tool_code"))
    rows = [INVENTORY_HEADER + list(years)]
    for r in wide.iter_rows(named=True):
        rows.append(["Most detailed Component", "UNFCCC", "Non-Annex_I", "Africa", "TUN", "Tunisia", r["gas"], r["tool_code"],
                     DESCRIPTIONS.get(r["tool_code"]), "fossil"] + [float(r.get(str(a)) or 0.0) for a in years])
    return rows


def inventory_long(block: list[list]) -> pl.DataFrame:
    """Most detailed, fossil rows in long format (lines 87 to 118 and 237 to 261 of I2A.py)."""
    table = imf_tools.range_to_table(block)
    years = [c for c in table.columns if c not in INVENTORY_HEADER]
    return (table.filter(pl.col("Info") == "Most detailed Component", (pl.col("FossilType") == "fossil") | pl.col("FossilType").is_null())
            .unpivot(index=["POLLUTANT", "Source_Code"], on=years, variable_name="year", value_name="value")
            .with_columns(pl.col("year").cast(pl.Int16), pl.col("value").cast(pl.Float64), source=pl.lit("INV")))


# ---------------------------------------------------------------------------
# (2) OECD transport emissions and (3) the matrix.
# (2) Émissions du transport de l'OCDE et (3) la matrice.
# ---------------------------------------------------------------------------

def oecd_long(oecd: dict, years: list[int]) -> pl.DataFrame:
    """OECD emissions in kt (lines 144 to 232): residents abroad (air) and all vessels (sea)."""
    air = imf_tools.range_to_table(oecd["OECD_Air"]).select(
        "POLLUTANT", "TIME_PERIOD", "OBS_VALUE",
        source=pl.col("EMISSIONS_SOURCE").replace(dict.fromkeys(RESIDENTS_ABROAD, "RES_ABROAD")), Source_Code=pl.lit(AIR_CODE))
    sea = imf_tools.range_to_table(oecd["OECD_Sea"]).select(
        "POLLUTANT", "TIME_PERIOD", "OBS_VALUE", source=pl.col("VESSEL"), Source_Code=pl.lit(SEA_CODE))
    return (pl.concat([air, sea])
            .with_columns(year=pl.col("TIME_PERIOD").cast(pl.Int16), value=pl.col("OBS_VALUE").cast(pl.Float64).fill_null(0) / 1000)
            .filter(pl.col("year").is_in(years))
            .select("POLLUTANT", "Source_Code", "year", "value", "source"))


def matrix_long(block: list[list]) -> pl.DataFrame:
    """Factors normalised to one by gas and code (lines 271 to 293); an empty gas applies to all gases."""
    table = imf_tools.range_to_table(block).drop("Level", strict=False).with_columns(pl.col("POLLUTANT").cast(pl.String))
    columns = [c for c in table.columns if c not in ("POLLUTANT", "Source_Code", "Source_Description", "Check")]
    long = (table.unpivot(index=["POLLUTANT", "Source_Code"], on=columns, variable_name="Activity", value_name="factor")
            .with_columns(pl.col("factor").cast(pl.Float64).fill_null(0))
            .with_columns(total=pl.col("factor").sum().over("POLLUTANT", "Source_Code"))
            .with_columns(factor=pl.when(pl.col("total") == 0).then(0.0).otherwise(pl.col("factor") / pl.col("total"))))
    empty = long.filter(pl.col("POLLUTANT").is_null() | (pl.col("POLLUTANT") == ""))
    if empty.height:
        long = pl.concat([long.filter(pl.col("POLLUTANT").is_not_null() & (pl.col("POLLUTANT") != "")),
                          *[empty.with_columns(POLLUTANT=pl.lit(g)) for g in TOOL_GASES]])
    return long.select("POLLUTANT", "Source_Code", "Activity", "factor")


# ---------------------------------------------------------------------------
# (4) Residence adjustments.
# (4) Ajustements de résidence.
# ---------------------------------------------------------------------------

def residence_adjustments(allocated: pl.DataFrame, activity_codes: list[str]) -> pl.DataFrame:
    """Residence adjustments of the tool (lines 395 to 514), by gas, code, activity and year.

    INV is the allocated inventory; the other columns are OECD data allocated with the same factors.
    """
    wide = (allocated.filter(pl.col("Source_Code").is_in([AIR_CODE, SEA_CODE]))
            .pivot("source", index=["POLLUTANT", "Source_Code", "Activity", "year"], values="value", aggregate_function="sum"))
    sources = [c for c in wide.columns if c not in ("POLLUTANT", "Source_Code", "Activity", "year")]
    wide = wide.with_columns(pl.col(sources).fill_null(0))
    if "INV" not in wide.columns:
        wide = wide.with_columns(INV=pl.lit(0.0))
    rows = []

    def add(table: pl.DataFrame, source: pl.Expr, activity: pl.Expr, value: pl.Expr) -> None:
        rows.append(table.select("POLLUTANT", "year", Source_Code=source, Activity=activity, value=value))

    # Maritime: OECD emissions of all resident vessels against domestic navigation in the inventory.
    # Maritime : émissions de l'OCDE de tous les navires résidents et navigation intérieure de l'inventaire.
    if "ALL_VESSELS" in sources:
        sea = wide.filter(pl.col("Source_Code") == SEA_CODE).with_columns(d=pl.col("ALL_VESSELS") - pl.col("INV"))
        positive, negative = sea.filter(pl.col("d") > 0), sea.filter(pl.col("d") < 0)
        # A positive gap is added to the activity, without a bridging item (line 425 of I2A.py).
        # Un écart positif est ajouté à l'activité, sans élément de passage (ligne 425 de I2A.py).
        add(positive, pl.lit("ALL_VESSELS"), pl.col("Activity"), pl.col("d"))
        # A negative gap is removed from the activity and assigned to non-residents on the territory.
        # Un écart négatif est retiré de l'activité et attribué aux non-résidents sur le territoire.
        add(negative, pl.col("Source_Code"), pl.col("Activity"), pl.col("d"))
        if "NRT-WATER" in activity_codes:
            add(negative, pl.col("Source_Code"), pl.lit("NRT-WATER"), -pl.col("d"))

    # Air: OECD emissions of residents on domestic flights against domestic aviation in the inventory.
    # Aérien : émissions de l'OCDE des résidents sur les vols intérieurs et aviation intérieure de l'inventaire.
    if "RES_DOM_IN" in sources:
        air = wide.filter(pl.col("Source_Code") == AIR_CODE).with_columns(d=pl.col("RES_DOM_IN") - pl.col("INV"))
        positive, negative = air.filter(pl.col("d") > 0), air.filter(pl.col("d") < 0)
        add(positive, pl.lit("RES_DOM_IN"), pl.col("Activity"), pl.col("d"))
        if "OTHER" in activity_codes:
            add(positive, pl.lit("RES_DOM_IN"), pl.lit("OTHER"), -pl.col("d"))
        add(negative, pl.col("Source_Code"), pl.col("Activity"), pl.col("d"))
        if "NRT-AIR" in activity_codes:
            add(negative, pl.col("Source_Code"), pl.lit("NRT-AIR"), -pl.col("d"))

    # Air: emissions of resident carriers abroad are added to the activity and recorded as a bridging item.
    # Aérien : les émissions des transporteurs résidents à l'étranger sont ajoutées à l'activité et inscrites en élément de passage.
    if "RES_ABROAD" in sources:
        air = wide.filter(pl.col("Source_Code") == AIR_CODE)
        add(air, pl.lit("RES_ABROAD"), pl.col("Activity"), pl.col("RES_ABROAD"))
        if "NRA-AIR" in activity_codes:
            add(air, pl.lit("RES_ABROAD"), pl.lit("NRA-AIR"), pl.col("RES_ABROAD"))
    return pl.concat(rows) if rows else allocated.head(0).select("POLLUTANT", "year", "Source_Code", "Activity", "value")


# ---------------------------------------------------------------------------
# (5) Assembly and comparison with the tool.
# (5) Assemblage et comparaison avec l'outil.
# ---------------------------------------------------------------------------

def explicit_i2a(inv_block: list[list], matrix_block: list[list], activity_block: list[list], oecd: dict | None = None) -> pl.DataFrame:
    """Explicit version of the I2A function; result in kt CO2 eq."""
    inv = inventory_long(inv_block)
    years = sorted(inv["year"].unique().to_list())
    inputs = pl.concat([inv, oecd_long(oecd, years)]) if oecd else inv
    inputs = inputs.group_by("POLLUTANT", "Source_Code", "year", "source").agg(pl.col("value").sum())

    # Allocation to activities (lines 313 to 335); a code without factors receives nothing.
    # Attribution aux activités (lignes 313 à 335) ; un code sans facteur ne reçoit rien.
    allocated = (inputs.join(matrix_long(matrix_block), on=["POLLUTANT", "Source_Code"], how="inner")
                 .with_columns(value=pl.col("value") * pl.col("factor")).filter(pl.col("value") != 0))
    activity_codes = [r[0] for r in activity_block[1:]]
    if oecd and allocated["source"].n_unique() > 2:
        result = pl.concat([allocated.filter(pl.col("source") == "INV").select("POLLUTANT", "year", "Source_Code", "Activity", "value"),
                            residence_adjustments(allocated, activity_codes)])
    else:
        result = allocated.select("POLLUTANT", "year", "Source_Code", "Activity", "value")
    result = result.filter(pl.col("value") != 0)

    # Totals (lines 528 to 557): activities before AEA-TOTAL, then from AEA-TOTAL to INV-TOTAL.
    # Totaux (lignes 528 à 557) : les activités avant AEA-TOTAL, puis de AEA-TOTAL à INV-TOTAL.
    i_aea, i_inv = activity_codes.index("AEA-TOTAL"), activity_codes.index("INV-TOTAL")
    aea_total = result.filter(pl.col("Activity").is_in(activity_codes[:i_aea])).with_columns(
        Source_Code=pl.lit("Total AEA"), Activity=pl.lit("AEA-TOTAL"))
    result = pl.concat([result, aea_total])
    inv_total = result.filter(pl.col("Activity").is_in(activity_codes[i_aea:i_inv])).with_columns(
        Source_Code=pl.lit("Total Inventories"), Activity=pl.lit("INV-TOTAL"))
    result = pl.concat([result, inv_total]).group_by(KEYS).agg(pl.col("value").sum())

    # Total of greenhouse gases (lines 563 to 571).
    # Total des gaz à effet de serre (lignes 563 à 571).
    ghg = result.group_by("Source_Code", "Activity", "year").agg(pl.col("value").sum()).with_columns(POLLUTANT=pl.lit("GHG"))
    return pl.concat([result, ghg.select(result.columns)])


def compare(tool: pl.DataFrame, explicit: pl.DataFrame) -> pl.DataFrame:
    a = tool.group_by(KEYS).agg(pl.col("value").sum().alias("tool"))
    b = explicit.group_by(KEYS).agg(pl.col("value").sum().alias("explicit"))
    return (a.join(b, on=KEYS, how="full", coalesce=True).with_columns(pl.col("tool", "explicit").fill_null(0))
            .with_columns(gap=pl.col("tool") - pl.col("explicit")))


def main() -> pl.DataFrame:
    inventory = read_intermediate("ghg_inventory").filter(pl.col("scope") != "memo")
    matrix = read_intermediate("conversion_matrix")
    activities = read_lookup("activities")
    oecd = imf_tools.oecd_ranges()
    years = sorted(inventory["year"].unique().to_list())
    assert set(inventory["tool_code"]) <= set(DESCRIPTIONS), "Inventory code missing from the CRT table of the tool"
    layers, worst = [], 0.0

    # Runs 1 and 2: default matrix of the tool, without and with OECD data, all years at once.
    # Essais 1 et 2 : matrice par défaut de l'outil, sans et avec les données de l'OCDE, toutes les années.
    inv_all = inventory_range(inventory, years)
    for run, options in [("default_without_oecd", None), ("default_with_oecd", oecd)]:
        choice = imf_tools.USE_OECD if options else imf_tools.NO_OECD
        tool = imf_tools.i2a(inv_all, RANGES["Conversion_Matrix"], RANGES["CRT"], RANGES["NFR"], RANGES["Activity"], oecd, choice)
        explicit = explicit_i2a(inv_all, RANGES["Conversion_Matrix"], RANGES["Activity"], options)
        gap = compare(tool, explicit)["gap"].abs().max()
        worst = max(worst, gap)
        layers.append({"run": run, "year": None, "max_gap_kt": gap})
        log(f"{run}: largest gap {gap:.1e} kt")

    # Run 3: the Tunisian matrix of each year, with OECD data.
    # Essai 3 : la matrice tunisienne de chaque année, avec les données de l'OCDE.
    industries = [c for c in activities["code"] if c not in PSEUDO_ACTIVITIES]
    matrix_columns = industries + ["LULUCF"]
    names = dict(activities.select("code", "en").iter_rows())
    header, *default_rows = RANGES["Activity"]
    start = next(i for i, r in enumerate(default_rows) if r[0] == "AEA-TOTAL")
    activity_block = [header] + [[c, names[c]] + [None] * (len(header) - 2) for c in industries] + default_rows[start:]

    results = []
    for year in years:
        wide = (matrix.filter(pl.col("year") == year)
                .pivot("activity", index="tool_code", values="factor", aggregate_function="sum").fill_null(0).sort("tool_code"))
        matrix_block = [["POLLUTANT", "Level", "Source_Code", "Source_Description", "Check"] + matrix_columns]
        for r in wide.iter_rows(named=True):
            matrix_block.append([None, None, r["tool_code"], DESCRIPTIONS.get(r["tool_code"]), 100.0]
                                + [100.0 * float(r.get(c) or 0.0) for c in matrix_columns])
        inv_year = inventory_range(inventory, [year])
        tool = imf_tools.i2a(inv_year, matrix_block, RANGES["CRT"], RANGES["NFR"], activity_block, oecd, imf_tools.USE_OECD)
        explicit = explicit_i2a(inv_year, matrix_block, activity_block, oecd)
        gap = compare(tool, explicit)["gap"].abs().max()
        worst = max(worst, gap)
        layers.append({"run": "tunisian_with_oecd", "year": year, "max_gap_kt": gap})
        results.append(explicit)
    log("Tunisian matrix: both layers compared for every year")

    aea = (pl.concat(results).select("year", gas="POLLUTANT", source="Source_Code", activity="Activity", kt_co2_eq="value")
           .sort("year", "gas", "activity", "source"))
    write_intermediate(aea, "aea")
    write_intermediate(pl.DataFrame(layers, schema={"run": pl.String, "year": pl.Int16, "max_gap_kt": pl.Float64}), "aea_layers")

    checks = Checks(SCRIPT)
    checks.add("explicit_equals_tool", worst, TOLERANCE_KT, "kt CO2 eq", "Largest cell gap between I2A and the explicit layer, all runs")
    checks.save()
    return aea


if __name__ == "__main__":
    main()
