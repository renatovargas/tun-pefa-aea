"""Prepare the greenhouse gas inventory for the air emissions accounts.

Why    : the air emissions accounts start from the national inventory, which records
         emissions by process (CRT category) and gas. This step builds one clean table of
         emissions by year, category and gas, in kilotonnes and in CO2 equivalent, marks what
         lies inside and outside the scope of the inventory total, and gives each category
         the code under which the IMF tool knows it.
Inputs : data/intermediate/crt.parquet (script 02)
         data/sources/ghg-inventory/crt/*.xlsm (sheet Summary2, for fluorinated gases and totals)
         data/sources/ghg-inventory/Tunisia_UNFCCC.xlsx (file prepared for the IMF tool, compared only)
         imf-tools/i2a/I2A.xlsm (sheets Conversion_Matrix_CRT_Def and CRT_Def)
Outputs: data/intermediate/ghg_inventory.parquet  year, crt, gas, kt, kt_co2_eq, scope, tool_code
         data/intermediate/unfccc_file_check.parquet  the prepared file against the CRT tables
         data/outputs/checks/20_prepare_ghg_inventory.csv
Method : CO2, CH4 and N2O come from the Data sheet and are weighted by AR5 global warming
         potentials. Fluorinated gases are reported by species in Data but in CO2 equivalent
         only by industrial category in Summary2, so they are read from Summary2. CO2 from
         biomass and the international bunkers (1.D) are memo items; LULUCF (sector 4) is kept
         apart, since the accounts exclude it. The inventory total is checked against the net
         total of Summary2.
Run    : uv run python scripts/aea/20_prepare_ghg_inventory.py

Préparation de l'inventaire des gaz à effet de serre pour les comptes des émissions. Le CO2,
le CH4 et le N2O viennent de la feuille Data, pondérés par les PRG de l'AR5 ; les gaz fluorés
viennent de Summary2. Le CO2 de la biomasse et les soutes (1.D) sont des éléments pour
mémoire ; l'UTCATF (secteur 4) est mis à part. Chaque catégorie reçoit le code de l'outil I2A.
"""

import sys
from pathlib import Path

import openpyxl
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import imf_tools  # noqa: E402
from common import GWP_AR5, SOURCES, Checks, read_intermediate, write_intermediate  # noqa: E402

SCRIPT = "20_prepare_ghg_inventory"
CRT_FOLDER = SOURCES / "ghg-inventory" / "crt"
F_GASES = ["HFCs", "PFCs", "Unspecified mix of HFCs and PFCs", "SF6", "NF3"]
AIR_POLLUTANTS = ["CO", "NOx", "NMVOC", "SO2"]


def crt_file(year: int) -> Path:
    return next(CRT_FOLDER.glob(f"{year}_Tables_CRT_*.xlsm"))


def summary2(year: int) -> pl.DataFrame:
    return pl.read_excel(crt_file(year), sheet_name="Summary2", engine="calamine", has_header=False, infer_schema_length=0)


def fix_code(column: str) -> pl.Expr:
    """CRT code with the capital letter of the classification (1.b.2.c... becomes 1.B.2.c...)."""
    return pl.col(column).str.replace(r"^1\.b\.", "1.B.")


def f_gases(year: int, species: pl.DataFrame) -> pl.DataFrame:
    """Fluorinated gases in kt CO2 eq by industrial category (2.A to 2.H), sheet Summary2."""
    raw = summary2(year)
    row = raw.with_row_index().filter(pl.col("column_0").str.starts_with("GREENHOUSE GAS SOURCE"))["index"][0]
    headers = {f"column_{j}": " ".join((raw[row, j] or "").split()) for j in range(1, raw.width)}
    columns = [c for c, name in headers.items() if name in F_GASES]
    table = (raw[row + 2:]
             .with_columns(category=pl.col("column_0").str.extract(r"^\s*(2\.[A-H])\.?\s"))
             .filter(pl.col("category").is_not_null())
             .select("category", kt_co2_eq=pl.sum_horizontal(pl.col(columns).cast(pl.Float64, strict=False).fill_null(0)))
             .filter(pl.col("kt_co2_eq") != 0)
             .with_columns(year=pl.lit(year, dtype=pl.Int16)))
    # Each Summary2 category must have a single detailed source in Data, which receives its total.
    # Chaque catégorie de Summary2 doit avoir une seule source détaillée dans Data, qui reçoit son total.
    table = table.join(species, on=["year", "category"], how="left")
    assert (table["crt"].list.len() == 1).all(), "A Summary2 category has several sources of fluorinated gases"
    return table.with_columns(pl.col("crt").list.first(), gas=pl.lit("F-gases"), kt=pl.lit(None, dtype=pl.Float64))


def summary2_total(year: int) -> float:
    """Net total emissions (kt CO2 eq), last column of the row "Total (net emissions)"."""
    row = summary2(year).filter(pl.col("column_0").str.starts_with("Total (net emissions)")).row(0)
    return float([x for x in row if x not in (None, "")][-1])


def tool_codes() -> set[str]:
    """Codes that appear both in the default conversion matrix and in the CRT table of I2A."""
    ranges = imf_tools.i2a_ranges()
    return {r[2] for r in ranges["Conversion_Matrix"][1:]} & {r[1] for r in ranges["CRT"][1:]}


def unfccc_file_check(emissions: pl.DataFrame, years: list[int]) -> pl.DataFrame:
    """Compare the file prepared for the tool with the CRT tables, by sector and gas, for the last year."""
    workbook = openpyxl.load_workbook(SOURCES / "ghg-inventory" / "Tunisia_UNFCCC.xlsx", read_only=True, data_only=True)
    rows = list(workbook.worksheets[0].iter_rows(values_only=True))
    workbook.close()
    file = (pl.DataFrame(rows[1:], schema=[str(c) for c in rows[0]], orient="row", infer_schema_length=None)
            .unpivot(index=["POLLUTANT", "IPCC", "IPCCDesc"], on=[str(a) for a in years], variable_name="year", value_name="file_kt")
            .with_columns(pl.col("year").cast(pl.Int16), code=pl.col("IPCC").cast(pl.String), file_kt=pl.col("file_kt").cast(pl.Float64)))
    year = max(years)
    file = (file.filter(pl.col("year") == year, pl.col("code").is_in(["1", "2", "3", "5"]), pl.col("POLLUTANT").is_in(["CO2", "CH4", "N20"]))
            .with_columns(gas=pl.col("POLLUTANT").replace({"N20": "N2O"})).sort("code", "gas"))

    def crt_sum(code: str, gas: str, column: str) -> float:
        rows = emissions.filter(pl.col("year") == year, pl.col("gas") == gas, (pl.col("crt") + ".").str.starts_with(code + "."),
                                ~pl.col("crt").str.starts_with("1.D"))
        return rows[column].sum()

    return file.with_columns(
        crt_kt=pl.Series([crt_sum(c, g, "kt") for c, g in zip(file["code"], file["gas"])]),
        crt_kt_co2_eq=pl.Series([crt_sum(c, g, "kt_co2_eq") for c, g in zip(file["code"], file["gas"])]),
    ).select("year", "code", "IPCCDesc", "POLLUTANT", "gas", "file_kt", "crt_kt", "crt_kt_co2_eq")


def main() -> pl.DataFrame:
    crt = read_intermediate("crt").filter(pl.col("parameter") == "emission")
    years = sorted(crt["year"].unique().to_list())

    # CO2, CH4 and N2O by category, in kt and in kt CO2 eq.
    # CO2, CH4 et N2O par catégorie, en kt et en kt éq. CO2.
    emissions = (crt.filter(pl.col("gas").is_in(list(GWP_AR5)))
                 .with_columns(crt=fix_code("crt"))
                 .group_by("year", "crt", "gas").agg(kt=pl.col("value").sum())
                 .with_columns(kt_co2_eq=pl.col("kt") * pl.col("gas").replace_strict(GWP_AR5, return_dtype=pl.Float64)))

    # Fluorinated gases from Summary2, attached to the detailed category that reports them in Data.
    # Gaz fluorés de Summary2, rattachés à la catégorie détaillée qui les déclare dans Data.
    species = (crt.filter(~pl.col("gas").is_in([*GWP_AR5, *AIR_POLLUTANTS, "CO2bio"]), pl.col("value") != 0)
               .with_columns(category=pl.col("crt").str.slice(0, 3))
               .group_by("year", "category").agg(pl.col("crt").unique().sort()))
    fgas = pl.concat([f_gases(y, species) for y in years])

    # CO2 from biomass is a memo item: reported, but outside the inventory total.
    # Le CO2 de la biomasse est un élément pour mémoire : déclaré, mais hors du total de l'inventaire.
    biomass = (crt.filter(pl.col("gas") == "CO2bio").with_columns(crt=fix_code("crt"))
               .group_by("year", "crt", "gas").agg(kt=pl.col("value").sum()).with_columns(kt_co2_eq=pl.col("kt")))

    inventory = (
        pl.concat([emissions, fgas.select(emissions.columns), biomass.select(emissions.columns)])
        .filter(pl.col("kt_co2_eq") != 0)
        .with_columns(scope=pl.when(pl.col("crt").str.starts_with("1.D") | (pl.col("gas") == "CO2bio")).then(pl.lit("memo"))
                      .when(pl.col("crt").str.starts_with("4.")).then(pl.lit("lulucf"))
                      .otherwise(pl.lit("inventory")))
        .sort("year", "crt", "gas"))

    # Each category takes the most detailed code of the tool list it belongs to; "3" is written "3." in the tool.
    # Chaque catégorie prend le code le plus détaillé de la liste de l'outil dont elle relève ; « 3 » s'écrit « 3. ».
    codes = tool_codes()

    def tool_code(code: str) -> str | None:
        parts = code.split(".")
        for k in range(len(parts), 0, -1):
            candidate = ".".join(parts[:k]) + ("." if k == 1 else "")
            if candidate in codes:
                return candidate
        return None

    inventory = inventory.with_columns(
        tool_code=pl.when(pl.col("scope") != "memo").then(pl.col("crt").map_elements(tool_code, return_dtype=pl.String)))
    write_intermediate(inventory, "ghg_inventory")

    # Inventory total against Summary2. N2O of 1.B.2.b.ii is in Data but not in Summary2 (see script 02).
    # Total de l'inventaire et Summary2. Le N2O de 1.B.2.b.ii est dans Data mais pas dans Summary2 (voir le script 02).
    totals = (inventory.filter(pl.col("scope") != "memo").group_by("year").agg(inventory=pl.col("kt_co2_eq").sum())
              .with_columns(summary2=pl.col("year").map_elements(summary2_total, return_dtype=pl.Float64))
              .join(emissions.filter(pl.col("crt") == "1.B.2.b.ii", pl.col("gas") == "N2O").select("year", n2o="kt_co2_eq"), on="year", how="left")
              .with_columns(pl.col("n2o").fill_null(0), gap=pl.col("inventory") - pl.col("summary2")))
    file_check = unfccc_file_check(emissions, years)
    write_intermediate(file_check, "unfccc_file_check")

    checks = Checks(SCRIPT)
    checks.add("total_vs_summary2", (totals["gap"] - totals["n2o"]).abs().max(), 0.01, "kt CO2 eq",
               "Inventory total (including LULUCF) against the net total of Summary2, after N2O of 1.B.2.b.ii")
    checks.add("all_categories_have_tool_code", inventory.filter(pl.col("scope") != "memo")["tool_code"].null_count(), 0, "categories",
               "Categories outside the memo items without a code of the I2A tool")
    checks.add("prepared_file_sectors", (file_check["file_kt"] - file_check["crt_kt"]).abs().max(), 0.01, "kt",
               "Sector totals of Tunisia_UNFCCC.xlsx against the CRT tables (kt of each gas)")
    checks.save()
    return inventory


if __name__ == "__main__":
    main()
