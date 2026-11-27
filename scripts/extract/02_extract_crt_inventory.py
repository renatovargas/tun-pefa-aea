"""Extract the Common Reporting Tables (CRT) of the greenhouse gas inventory, 2015 to 2022.

Why    : the inventory is the source of the air emissions accounts. The `Data` sheet of each
         CRT workbook already holds every reported value in long format.
Inputs : data/sources/ghg-inventory/crt/20XX_Tables_CRT_AR5.xlsm
Outputs: data/intermediate/crt.parquet  year, record key, CRT code, parameter, type, fuel, gas, unit, value
         data/outputs/checks/02_extract_crt_inventory.csv
Method : the `Data` sheets are stacked with their year, values are cast to numbers and exact
         duplicate rows are removed. The emissions of CO2, CH4 and N2O are then added up by
         category and compared with the published totals of sheet `Summary2`.
Run    : uv run python scripts/extract/02_extract_crt_inventory.py

Extraction des tableaux CRT de l'inventaire des gaz à effet de serre, 2015 à 2022. Les
feuilles `Data` sont empilées avec leur année, les valeurs converties en nombres et les
doublons exacts retirés. Les émissions sont ensuite comparées aux totaux publiés dans la
feuille `Summary2`.
"""

import re
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import GWP_AR5, SOURCES, Checks, log, write_intermediate  # noqa: E402

SCRIPT = "02_extract_crt_inventory"
FOLDER = SOURCES / "ghg-inventory" / "crt"

# Columns of the Data sheet and their names in the intermediate table.
# Colonnes de la feuille Data et leur nom dans le tableau intermédiaire.
COLUMNS = {"Record_Key": "record_key", "CRT": "crt", "Parameter": "parameter", "Type": "type",
           "Fuel": "fuel", "Gas": "gas", "Unit": "unit", "Value": "value"}


def crt_files() -> dict[int, Path]:
    return {int(re.match(r"(\d{4})", f.name).group(1)): f for f in sorted(FOLDER.glob("*_Tables_CRT_*.xlsm"))}


def read_data_sheet(path: Path, year: int) -> tuple[pl.DataFrame, int]:
    """Read the Data sheet of one workbook. Return the table and the number of duplicates removed."""
    raw = pl.read_excel(path, sheet_name="Data", engine="calamine", infer_schema_length=0)
    raw = raw.select(list(COLUMNS)).rename(COLUMNS)
    unique = raw.unique(maintain_order=True)
    table = unique.with_columns(year=pl.lit(year, pl.Int16), value=pl.col("value").cast(pl.Float64))
    return table.select("year", *COLUMNS.values()), raw.height - unique.height


def read_summary2(path: Path) -> pl.DataFrame:
    """CO2, CH4 and N2O emissions by category published in sheet Summary2 (kt CO2 eq)."""
    raw = pl.read_excel(path, sheet_name="Summary2", engine="calamine", has_header=False, infer_schema_length=0)
    gas_row = raw.with_row_index().filter(pl.col("column_0").str.starts_with("GREENHOUSE GAS SOURCE"))["index"][0]
    gases = {j: (raw[gas_row, j] or "").strip() for j in range(1, raw.width)}
    columns = {f"column_{j}": name for j, name in gases.items() if name in GWP_AR5}
    rows = (raw[gas_row + 2:]
            .select(pl.col("column_0").alias("category"), *[pl.col(c).alias(n) for c, n in columns.items()])
            .with_columns(crt=pl.col("category").str.extract(r"^\s*(\d(?:\.[A-Z0-9]+)*)\.?\s"))
            .filter(pl.col("crt").is_not_null()))
    return rows.unpivot(index=["category", "crt"], variable_name="gas", value_name="summary2").with_columns(
        pl.col("summary2").cast(pl.Float64, strict=False).fill_null(0))


def compare_with_summary2(crt: pl.DataFrame, year: int, path: Path) -> pl.DataFrame:
    """Compare the emissions of the Data sheet, summed by category, with the totals of Summary2."""
    reference = read_summary2(path)
    emissions = crt.filter((pl.col("year") == year) & (pl.col("parameter") == "emission")
                           & (pl.col("unit") == "kt") & pl.col("gas").is_in(list(GWP_AR5)))

    # Memo items (1.D, international bunkers) are not part of the energy total, so they are
    # left out of the sums of their parent categories.
    # Les éléments pour mémoire (1.D, soutes internationales) ne font pas partie du total de
    # l'énergie ; ils sont exclus des sommes des catégories parentes.
    def total(category: str, gas: str) -> float:
        rows = emissions.filter(pl.col("gas") == gas, pl.col("crt").str.starts_with(category + "."))
        if not category.startswith("1.D"):
            rows = rows.filter(~pl.col("crt").str.starts_with("1.D"))
        return rows["value"].sum() * GWP_AR5[gas]

    sums = [total(c, g) for c, g in zip(reference["crt"], reference["gas"])]
    return reference.with_columns(data=pl.Series(sums), year=pl.lit(year, pl.Int16)).with_columns(
        gap=pl.col("summary2") - pl.col("data"))


def main() -> pl.DataFrame:
    # Stack the Data sheets of all years.
    # Empiler les feuilles Data de toutes les années.
    tables, duplicates = [], {}
    for year, path in crt_files().items():
        table, n = read_data_sheet(path, year)
        tables.append(table)
        duplicates[year] = n
    crt = pl.concat(tables)
    write_intermediate(crt, "crt")
    log(f"exact duplicates removed by year: {duplicates}")

    # Compare with Summary2. N2O of category 1.B.2.b.ii appears in Data from 2019 but is not
    # counted in Summary2 (open question), so that cell is checked separately.
    # Comparer avec Summary2. Le N2O de la catégorie 1.B.2.b.ii figure dans Data à partir de
    # 2019 mais n'est pas compté dans Summary2 (question ouverte) ; il est contrôlé à part.
    gaps = pl.concat([compare_with_summary2(crt, y, p) for y, p in crt_files().items()])
    n2o = (gaps["gas"] == "N2O") & pl.Series([c in ("1", "1.B", "1.B.2") for c in gaps["crt"]])
    checks = Checks(SCRIPT)
    checks.add("summary2_categories", gaps.filter(~n2o)["gap"].abs().max(), 0.01, "kt CO2 eq",
               "Largest gap between Data and Summary2 by category and gas, except N2O of 1.B.2")
    checks.add("summary2_n2o_1B2", gaps.filter(n2o)["gap"].abs().max(), 1, "kt CO2 eq",
               "Largest gap for N2O of 1.B.2 (1.B.2.b.ii is in Data from 2019 but not in Summary2)")
    checks.save()
    return crt


if __name__ == "__main__":
    main()
