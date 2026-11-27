"""Compile the physical supply and use tables for energy (PEFA), 2015 to 2022.

Why    : this is the core of the energy accounts. The PEFA Converter (function EB2PEFA)
         turns a balance and a concordance matrix into supply and use tables. The script
         re-implements every rule of EB2PEFA in polars, so that each rule can be read and
         changed, and calls the tool itself as a reference: both must agree to 1e-9 PJ.
Inputs : data/intermediate/balance_iea.parquet (script 10), concordance_matrix.parquet (script 12)
         imf-tools/pefa-converter/PEFA_Converter.xlsm and PEFA_Converter.py
Outputs: data/intermediate/pefa.parquet           year, quadrant, level1, level2, product, activity, tj
         data/intermediate/pefa_isic.parquet      the same with the default matrix (ISIC sections), for comparison
         data/intermediate/pefa_layers.parquet    agreement between the tool and the explicit layer, by run
         data/outputs/checks/13_compile_pefa_tables.csv
Method : (1) the template flows receive two levels (supply, transformation, own use, final
         consumption...) by their position, as EB2PEFA does; (2) the memo line of chemical
         non-energy use is subtracted, exports and stock changes change sign; (3) the matrix is
         cleaned and its factors normalised; (4) rules for natural inputs, transfers and the
         statistical difference are added; (5) the balance is joined to the matrix and each
         value multiplied by its factor; (6) downstream flows receive their signs, and every
         use of energy generates the matching energy residual, which flows to the environment.
         The tool is run on its own example, on Tunisia with the default matrix and on Tunisia
         with the Tunisian matrix.
Run    : uv run python scripts/pefa/13_compile_pefa_tables.py

Compilation des tableaux physiques des ressources et des emplois d'énergie (PEFA). Le script
reprend en polars chaque règle de la fonction EB2PEFA de l'outil du FMI (Achille Pegoue), et
appelle l'outil lui-même comme référence : les deux doivent concorder à 1e-9 PJ près.
"""

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import imf_tools  # noqa: E402
from common import KTOE_TO_TJ, Checks, log, read_intermediate, write_intermediate  # noqa: E402

SCRIPT = "13_compile_pefa_tables"
KEYS = ["PEFA_Target_Product_Level1", "PEFA_Target_Product_Level2", "PEFA_Target_Product", "PEFA_Target_Activity", "PEFA_Quadrant"]
FLOW_KEYS = ["EB_Flow_Level1", "EB_Flow_Level2", "EB_Flow", "EB_Product"]
TOLERANCE_PJ = 1e-9

# ---------------------------------------------------------------------------
# (1) Levels of the template flows. EB2PEFA reads the balance from top to bottom and
# gives each flow the level of the last heading above it.
# (1) Niveaux des flux du modèle. EB2PEFA lit le bilan de haut en bas et donne à chaque
# flux le niveau du dernier titre placé au-dessus de lui.
# ---------------------------------------------------------------------------

HEADINGS = {
    "Transformation processes": ("Transformation processes", None),
    "Energy industry own use": ("Energy industry own use", None),
    "Industry": ("Total final consumption", "Industry"),
    "Transport": ("Total final consumption", "Transport"),
    "Other": ("Total final consumption", "Other"),
    "Non-energy use": ("Total final consumption", "Non-energy use"),
    "Electricity output (GWh)": ("Electricity output (GWh)", None),
}


def flow_levels(flows: list[str]) -> pl.DataFrame:
    """Levels 1 and 2 of each template flow, by the position rules of EB2PEFA."""
    rows, state = [], ("Total primary energy supply", None)
    for f in flows:
        if f == "Total primary energy supply":
            rows.append((f, None, None))
            state = ("Other flows", None)
        elif f in HEADINGS or f in ("Total final consumption", "Heat output"):
            rows.append((f, None, None))
            state = HEADINGS.get(f, (None, None))
        elif f == "Losses":
            rows.append((f, "Losses", None))
        else:
            rows.append((f, *state))
    return pl.DataFrame(rows, schema=["EB_Flow", "EB_Flow_Level1", "EB_Flow_Level2"], orient="row")


LEVELS = flow_levels(imf_tools.template_flows())

# ---------------------------------------------------------------------------
# (2) and (3) Preparing the balance and the matrix.
# (2) et (3) Préparation du bilan et de la matrice.
# ---------------------------------------------------------------------------

MEMO = "   Memo: Non-energy use chemical/petrochemical"
NON_ENERGY_INDUSTRY = "Non-energy use industry/transformation/energy"


def prepare_balance(balance: pl.DataFrame) -> pl.DataFrame:
    """Long balance (EB_Flow, EB_Product, Energy in TJ) with levels, memo subtracted and the signs of the tool."""
    long = balance.group_by("EB_Flow", "EB_Product").agg(pl.col("Energy").sum()).filter(pl.col("Energy") != 0)
    memo = long.filter(pl.col("EB_Flow") == MEMO).select("EB_Product", pl.col("Energy").alias("memo"))
    long = (
        long.join(memo, on="EB_Product", how="left")
        .with_columns(Energy=pl.when(pl.col("EB_Flow") == NON_ENERGY_INDUSTRY)
                      .then(pl.col("Energy") - pl.col("memo").fill_null(0)).otherwise("Energy"))
        .drop("memo")
        .with_columns(Energy=pl.when(pl.col("EB_Flow").is_in(["Exports", "Stock changes"])).then(-pl.col("Energy")).otherwise("Energy"))
    )
    return long.join(LEVELS, on="EB_Flow").filter(pl.col("EB_Flow_Level1").is_not_null())


def prepare_matrix(matrix: pl.DataFrame) -> pl.DataFrame:
    """Matrix without zero factors or duplicates, factors normalised by flow, product, target product and quadrant."""
    group = FLOW_KEYS + ["PEFA_Target_Product", "PEFA_Target_Product_Level1", "PEFA_Target_Product_Level2", "PEFA_Quadrant"]
    return (matrix.filter(pl.col("Allocation Factor") != 0)
            .group_by(group + ["EB_Category", "PEFA_Target_Activity"]).agg(pl.col("Allocation Factor").sum())
            .with_columns(pl.col("Allocation Factor") / pl.col("Allocation Factor").sum().over(group)))


# ---------------------------------------------------------------------------
# (4) Natural inputs, transfers and the statistical difference.
# (4) Ressources naturelles, transferts et écart statistique.
# ---------------------------------------------------------------------------

def upstream_rules(cm: pl.DataFrame, renewables: list[str], waste: list[str]) -> pl.DataFrame:
    """Add to the matrix the rows for natural inputs, transfers and the statistical difference."""
    tpes = pl.col("EB_Flow_Level1") == "Total primary energy supply"

    # Primary production is supplied by the environment and used by the extracting industry
    # as a natural input; waste comes from accumulation instead.
    # La production primaire est fournie par l'environnement et utilisée par la branche qui
    # l'extrait comme ressource naturelle ; les déchets viennent de l'accumulation.
    production = cm.filter(tpes & (pl.col("EB_Flow") == "Production")).with_columns(
        pl.when(pl.col("PEFA_Target_Activity") == "Acc").then(-pl.col("Allocation Factor")).otherwise(pl.col("Allocation Factor"))
        .alias("Allocation Factor"))
    natural = production.filter(~pl.col("PEFA_Target_Activity").is_in(["Acc", "RoW"])).with_columns(
        PEFA_Quadrant=pl.lit("Use"),
        PEFA_Target_Product_Level1=pl.when(pl.col("EB_Product").is_in(waste)).then(pl.lit("Other residual flows:"))
        .otherwise(pl.lit("Energy from natural inputs:")),
        PEFA_Target_Product_Level2=pl.lit(None, pl.String),
        PEFA_Target_Product=pl.when(pl.col("EB_Product").is_in(waste)).then(pl.lit("Energy from solid waste"))
        .when(pl.col("EB_Product").is_in(renewables)).then(pl.lit("Inputs of energy from renewable sources"))
        .otherwise(pl.lit("Natural resource inputs")))
    environment = natural.with_columns(
        PEFA_Quadrant=pl.lit("Supply"),
        PEFA_Target_Activity=pl.when(pl.col("EB_Product").is_in(waste)).then(pl.lit("Acc")).otherwise(pl.lit("Env")))

    # Transfers are recorded as solid waste moving through accumulation.
    # Les transferts sont enregistrés comme des déchets solides qui passent par l'accumulation.
    transfers = cm.filter((pl.col("EB_Flow_Level1") == "Other flows") & (pl.col("EB_Flow") == "Transfers"))
    residuals = transfers.with_columns(
        PEFA_Target_Product_Level1=pl.lit("Other residual flows:"), PEFA_Target_Product_Level2=pl.lit(None, pl.String),
        PEFA_Target_Product=pl.lit("Energy from solid waste"), PEFA_Quadrant=pl.lit("Use"))
    accumulation = residuals.with_columns(PEFA_Quadrant=pl.lit("Supply"), PEFA_Target_Activity=pl.lit("Acc"))

    # The statistical difference changes sign; when it goes to an industry it also creates a residual
    # (lines 606 to 621 of PEFA_Converter.py).
    # L'écart statistique change de signe ; s'il va à une branche il crée aussi un résidu
    # (lignes 606 à 621 de PEFA_Converter.py).
    statdiff = cm.filter((pl.col("EB_Flow_Level1") == "Other flows") & (pl.col("EB_Flow") == "Statistical differences"))
    statdiff = statdiff.with_columns(-(pl.col("Allocation Factor") / pl.col("Allocation Factor").sum().over(FLOW_KEYS)).alias("Allocation Factor"))
    statdiff_industries = statdiff.filter(~pl.col("PEFA_Target_Activity").is_in(["Acc", "RoW"]))
    statdiff_residuals = statdiff_industries.with_columns(
        PEFA_Target_Product_Level1=pl.lit("Energy residuals:"), PEFA_Target_Product_Level2=pl.lit(None, pl.String),
        PEFA_Target_Product=pl.lit("Energy residuals from end-use"), PEFA_Quadrant=pl.lit("Supply"))
    statdiff_environment = statdiff_residuals.with_columns(PEFA_Quadrant=pl.lit("Use"), PEFA_Target_Activity=pl.lit("Env"))

    rest = cm.filter(~(tpes & (pl.col("EB_Flow") == "Production"))
                     & ~((pl.col("EB_Flow_Level1") == "Other flows") & (pl.col("EB_Flow") == "Statistical differences")))
    return pl.concat([rest, production, natural, environment, residuals, accumulation, statdiff, statdiff_residuals,
                      statdiff_environment], how="vertical_relaxed")


# ---------------------------------------------------------------------------
# (6) Downstream uses, outputs and residuals.
# (6) Emplois, productions et résidus en aval.
# ---------------------------------------------------------------------------

DOWNSTREAM = ["Transformation processes", "Energy industry own use", "Losses", "Total final consumption",
              "Electricity output (GWh)", "Heat output"]
BUNKERS = ["International marine bunkers", "International aviation bunkers"]


def downstream_rules(pefa: pl.DataFrame) -> pl.DataFrame:
    """Signs of the downstream flows and the energy residuals they generate."""
    level1, flow, energy = pl.col("EB_Flow_Level1"), pl.col("EB_Flow"), pl.col("PEFA_Energy")
    tpes = level1 == "Total primary energy supply"
    is_downstream = level1.is_in(DOWNSTREAM) | (tpes & flow.is_in(BUNKERS))
    upstream, downstream = pefa.filter(~is_downstream), pefa.filter(is_downstream)

    # A positive value in transformation is an output (supply); own use and losses change sign.
    # Une valeur positive en transformation est une production (ressource) ; l'autoconsommation et les pertes changent de signe.
    transformation = level1 == "Transformation processes"
    signed = downstream.with_columns(
        PEFA_Quadrant=pl.when((energy > 0) & (transformation | tpes)).then(pl.lit("Supply")).otherwise("PEFA_Quadrant"),
        PEFA_Target_Product_Level2=pl.when((energy > 0) & transformation)
        .then(pl.lit("Production of energy products by SIEC class:")).otherwise("PEFA_Target_Product_Level2"),
        PEFA_Energy=pl.when(transformation | tpes).then(energy.abs())
        .when(level1.is_in(["Energy industry own use", "Losses"])).then(-energy)
        .otherwise(energy))

    # Every use of energy generates an energy residual supplied by the user and absorbed by the
    # environment; non-energy use ends in accumulation (products such as bitumen or plastics).
    # Tout emploi d'énergie génère un résidu fourni par l'utilisateur et absorbé par
    # l'environnement ; les usages non énergétiques vont à l'accumulation (bitume, plastiques).
    non_energy = (level1 == "Total final consumption") & (pl.col("EB_Flow_Level2") == "Non-energy use")
    end_use = ((level1.is_in(["Energy industry own use", "Losses", "Total final consumption"]) & (flow != "Losses"))
               | (tpes & flow.is_in(BUNKERS)))
    residuals = downstream.with_columns(
        PEFA_Energy=pl.when(level1.is_in(["Transformation processes", "Energy industry own use", "Losses"])).then(-energy)
        .when(tpes).then(energy.abs()).otherwise(energy),
        PEFA_Target_Product_Level1=pl.when(non_energy).then(pl.lit("Other residual flows:")).otherwise(pl.lit("Energy residuals:")),
        PEFA_Target_Product_Level2=pl.lit(None, pl.String),
        PEFA_Target_Product=pl.when(non_energy).then(pl.lit("Residuals from end-use for non-energy purposes"))
        .when(end_use).then(pl.lit("Energy residuals from end-use")).otherwise(pl.lit("Energy residuals from losses")),
        PEFA_Quadrant=pl.lit("Supply"))
    absorption = residuals.with_columns(
        PEFA_Quadrant=pl.lit("Use"),
        PEFA_Target_Activity=pl.when(non_energy).then(pl.lit("Acc")).otherwise(pl.lit("Env")))
    return pl.concat([upstream, signed, residuals, absorption])


# ---------------------------------------------------------------------------
# (5) Assembly, and comparison with the tool.
# (5) Assemblage et comparaison avec l'outil.
# ---------------------------------------------------------------------------

def explicit_pefa(balance: pl.DataFrame, matrix: pl.DataFrame, classification: pl.DataFrame) -> pl.DataFrame:
    """Explicit version of EB2PEFA. balance: EB_Flow, EB_Product, Energy (TJ). Result in PJ, as in the tool."""
    renewables = classification.filter(pl.col("Group") == "Renewable")["EB_Product"].to_list()
    waste = classification.filter(pl.col("Group") == "Waste")["EB_Product"].to_list()
    cm = upstream_rules(prepare_matrix(matrix), renewables, waste)
    eb = prepare_balance(balance)
    joined = eb.join(cm, on=FLOW_KEYS, nulls_equal=True).with_columns(PEFA_Energy=pl.col("Energy") * pl.col("Allocation Factor") / 1000)
    pefa = downstream_rules(joined)
    statdiff = pefa.filter(pl.col("EB_Flow") == "Statistical differences").with_columns(PEFA_Target_Activity=pl.lit("Statistical differences"))
    main_part = pefa.filter(pl.col("EB_Flow") != "Statistical differences")
    return pl.concat([t.group_by(KEYS).agg(pl.col("PEFA_Energy").sum()) for t in (main_part, statdiff)])


def compare(tool: pl.DataFrame, explicit: pl.DataFrame) -> pl.DataFrame:
    """Cell-by-cell gaps between the tool and the explicit layer (PJ)."""
    a = tool.group_by(KEYS).agg(pl.col("PEFA_Energy").sum().alias("tool"))
    b = explicit.group_by(KEYS).agg(pl.col("PEFA_Energy").sum().alias("explicit"))
    return (a.join(b, on=KEYS, how="full", coalesce=True, nulls_equal=True)
            .with_columns(pl.col("tool", "explicit").fill_null(0))
            .with_columns(gap=pl.col("tool") - pl.col("explicit")))


def totals(pefa: pl.DataFrame) -> dict:
    """Total supply and total use (PJ)."""
    return {q: pefa.filter(pl.col("PEFA_Quadrant") == q)["PEFA_Energy"].sum() for q in ["Supply", "Use"]}


def range_to_long(block: list[list]) -> pl.DataFrame:
    """An Energy_Balance range in long format; text cells ("x") count as 0, as in the tool."""
    products = block[0][1:]
    rows = [(r[0], p, v if isinstance(v, float) else 0.0) for r in block[1:] if r[0] is not None for p, v in zip(products, r[1:])]
    return pl.DataFrame(rows, schema=["EB_Flow", "EB_Product", "Energy"], orient="row")


def to_output(pefa: pl.DataFrame, year: int) -> pl.DataFrame:
    """Rename the tool columns, convert PJ to TJ and drop empty cells."""
    return (pefa.with_columns(tj=pl.col("PEFA_Energy") * 1000, year=pl.lit(year, pl.Int16))
            .rename({"PEFA_Target_Product_Level1": "level1", "PEFA_Target_Product_Level2": "level2",
                     "PEFA_Target_Product": "product", "PEFA_Target_Activity": "activity", "PEFA_Quadrant": "quadrant"})
            .with_columns(pl.col("activity").replace(TOOL_PSEUDO_CODES))
            .filter(pl.col("tj") != 0)
            .select("year", "quadrant", "level1", "level2", "product", "activity", "tj"))


# Codes of the tool for the rest of the world, accumulation, environment and statistical
# difference, and the codes used in data/lookups/activities.csv.
# Codes de l'outil pour le reste du monde, l'accumulation, l'environnement et l'écart
# statistique, et codes utilisés dans data/lookups/activities.csv.
TOOL_PSEUDO_CODES = {"RoW": "ROW", "Acc": "ACC", "Env": "ENV", "Statistical differences": "STATDIFF"}


def main() -> pl.DataFrame:
    ranges = imf_tools.pefa_ranges()
    flows, products = imf_tools.template_flows(), imf_tools.template_products()
    classification = pl.DataFrame(ranges["EB_Product"][1:], schema=ranges["EB_Product"][0], orient="row")
    cm_columns = [str(c) for c in ranges["CM"][0]]
    default = imf_tools.range_to_table(ranges["CM"]).with_columns(
        pl.col("Allocation Factor").cast(pl.Float64, strict=False).fill_null(0))
    iea = read_intermediate("balance_iea")
    tunisian = read_intermediate("concordance_matrix")
    args = (ranges["EB_Bridging_Items"], ranges["EB_Product"], imf_tools.DEFAULT_FILTER)
    layers = []

    def record(run: str, year: int | None, tool: pl.DataFrame, explicit: pl.DataFrame) -> float:
        gaps = compare(tool, explicit)
        t = totals(explicit)
        layers.append({"run": run, "year": year, "cells": gaps.height, "max_gap_pj": gaps["gap"].abs().max(),
                       "supply_pj": t["Supply"], "use_pj": t["Use"]})
        return gaps["gap"].abs().max()

    # Run 1: the example balance of the workbook, without its Total column (see imf-tools/README.md).
    # Essai 1 : le bilan d'exemple du classeur, sans sa colonne Total (voir imf-tools/README.md).
    example = imf_tools.drop_total_column(ranges["EB"])
    with_total = imf_tools.eb2pefa(ranges["EB"], ranges["CM"], *args)
    t = totals(with_total)
    layers.append({"run": "example_with_total_column", "year": None, "cells": None, "max_gap_pj": None,
                   "supply_pj": t["Supply"], "use_pj": t["Use"]})
    worst = record("example", None, imf_tools.eb2pefa(example, ranges["CM"], *args),
                   explicit_pefa(range_to_long(example), default, classification))
    log(f"example: largest gap {worst:.1e} PJ")

    # Runs 2 and 3: Tunisia with the default matrix (ISIC sections) and with the Tunisian matrix.
    # Essais 2 et 3 : la Tunisie avec la matrice par défaut (sections de la CITI) et avec la matrice tunisienne.
    results = {"default": [], "tunisian": []}
    for year in sorted(iea["year"].unique().to_list()):
        balance_year = iea.filter(pl.col("year") == year)
        eb_range = imf_tools.balance_to_range(balance_year, flows, products)
        eb_long = balance_year.select(pl.col("iea_flow").alias("EB_Flow"), pl.col("iea_product").alias("EB_Product"), pl.col("tj").alias("Energy"))
        for run, matrix in [("default", default), ("tunisian", tunisian.filter(pl.col("year") == year).drop("year"))]:
            tool = imf_tools.eb2pefa(eb_range, imf_tools.matrix_to_range(matrix, cm_columns), *args)
            explicit = explicit_pefa(eb_long, matrix, classification)
            worst = max(worst, record(run, year, tool, explicit))
            results[run].append(to_output(explicit, year))
        log(f"{year}: both layers compared with both matrices")

    pefa = pl.concat(results["tunisian"]).sort("year", "quadrant", "level1", "level2", "product", "activity", nulls_last=True)
    write_intermediate(pefa, "pefa")
    write_intermediate(pl.concat(results["default"]), "pefa_isic")
    layer_table = pl.DataFrame(layers).with_columns(
        supply_minus_use_ktoe=(pl.col("supply_pj") - pl.col("use_pj")) * 1000 / KTOE_TO_TJ)
    write_intermediate(layer_table, "pefa_layers")

    checks = Checks(SCRIPT)
    checks.add("explicit_equals_tool", worst, TOLERANCE_PJ, "PJ", "Largest cell gap between EB2PEFA and the explicit layer, all runs")
    example_row = layer_table.filter(pl.col("run") == "example")
    checks.add("example_balanced", example_row["supply_pj"][0] - example_row["use_pj"][0], 0.01, "PJ",
               "Supply minus use on the tool example without the Total column")
    checks.save()
    return pefa


if __name__ == "__main__":
    main()
