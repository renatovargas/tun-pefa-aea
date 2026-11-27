"""Extract the supply and use tables (SUT) of the national accounts, 2015 to 2023.

Why    : the supply and use tables give the 24 industries that the accounts use, the keys
         that split some energy flows between industries, and the output and value added
         that turn the accounts into indicators.
Inputs : data/sources/national-accounts/TRE 2015-2023 SD.xlsx (current prices, million TND,
         one sheet per year)
         data/lookups/sut_columns.csv, sut_products.csv
Outputs: data/intermediate/sut.parquet  year, block, row, column, aggregate, value
         data/outputs/checks/03_extract_supply_use_tables.csv
Method : column widths differ between 2015-2018 and 2019-2023, so every block is found by the
         text of its header. Columns of the intermediate consumption matrix are recognised by
         their activity code. The script checks that supply equals use for every product and
         that output equals intermediate consumption plus value added for every industry.
Run    : uv run python scripts/extract/03_extract_supply_use_tables.py

Extraction des tableaux des ressources et des emplois (TRE), 2015 à 2023. Chaque bloc est
repéré par le texte de son en-tête et non par sa position. Le script vérifie l'égalité des
ressources et des emplois par produit, et l'égalité production = consommation intermédiaire
+ valeur ajoutée par branche.
"""

import re
import sys
from pathlib import Path

import fastexcel
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import SOURCES, Checks, read_lookup, write_intermediate  # noqa: E402

SCRIPT = "03_extract_supply_use_tables"
SOURCE = SOURCES / "national-accounts" / "TRE 2015-2023 SD.xlsx"


def clean(text: str | None) -> str:
    """Remove extra spaces, including non-breaking spaces."""
    return " ".join((text or "").split())


def sheets() -> dict[int, str]:
    """Map each year to its sheet ("2015 C" ... "2023 C")."""
    return {int(m.group(1)): n for n in fastexcel.read_excel(SOURCE).sheet_names if (m := re.match(r"(\d{4}) C$", n))}


def read_sheet(year: int, sheet: str) -> pl.DataFrame:
    """Read one sheet and return a long table: block, row, column, value."""
    raw = pl.read_excel(SOURCE, sheet_name=sheet, engine="calamine", has_header=False, infer_schema_length=0)
    columns = read_lookup("sut_columns")
    product_codes = set(read_lookup("sut_products")["code"])

    # The header row is the one whose first cell starts with "Unité".
    # La ligne d'en-tête est celle dont la première cellule commence par « Unité ».
    header = raw.with_row_index().filter(pl.col("column_0").str.strip_chars().str.starts_with("Unité"))["index"][0]
    names = [clean(x) for x in raw.row(header)]

    # Named columns (supply and final uses) come from sut_columns.csv; the columns of the
    # intermediate consumption matrix carry an activity code as header.
    # Les colonnes nommées (ressources et emplois finals) viennent de sut_columns.csv ; les
    # colonnes de la matrice de consommation intermédiaire ont un code d'activité pour en-tête.
    by_label = {r["source_label"]: (r["code"], r["block"])
                for r in columns.filter(pl.col("block") != "value_added").iter_rows(named=True)}
    named = {j: by_label[n] for j, n in enumerate(names) if n in by_label}
    activities = {j: n for j, n in enumerate(names) if n in product_codes}
    unknown = [n for j, n in enumerate(names) if n and j > 0 and j not in named and j not in activities and not n.startswith("Unité")]
    if unknown:
        raise ValueError(f"{sheet}: unknown headers {unknown}")

    records = []
    # Product rows (and the "Totaux" row).
    # Lignes de produits (et la ligne « Totaux »).
    for i in range(header + 1, raw.height):
        code = clean(raw[i, 0])
        if code in product_codes or code == "Totaux":
            row = "TOTAL" if code == "Totaux" else code
            for j, (col, block) in named.items():
                records.append((block, row, col, raw[i, j]))
            for j, act in activities.items():
                records.append(("use", row, act, raw[i, j]))

    # Value added rows sit below the matrix, labelled in the column before the first activity.
    # Les lignes de valeur ajoutée sont sous la matrice, libellées dans la colonne qui précède la première activité.
    value_added = {r["source_label"]: r["code"] for r in columns.filter(pl.col("block") == "value_added").iter_rows(named=True)}
    label_column = min(activities) - 1
    for i in range(header + 1, raw.height):
        label = clean(raw[i, label_column])
        if label in value_added:
            for j, act in activities.items():
                records.append(("value_added", value_added[label], act, raw[i, j]))

    long = pl.DataFrame(records, schema=["block", "row", "column", "text"], orient="row")
    long = long.with_columns(value=pl.col("text").str.strip_chars().cast(pl.Float64, strict=False))
    unreadable = long.filter(pl.col("value").is_null() & (pl.col("text").str.strip_chars() != ""))
    if unreadable.height:
        raise ValueError(f"{sheet}: non-numeric values {unreadable['text'].unique().to_list()}")
    aggregates = set(columns.filter(pl.col("aggregate") == "yes")["code"])
    return (long.filter(pl.col("value").is_not_null() & (pl.col("value") != 0))
            .with_columns(year=pl.lit(year, pl.Int16),
                          aggregate=pl.col("column").is_in(list(aggregates)) | (pl.col("row") == "TOTAL"))
            .select("year", "block", "row", "column", "aggregate", "value"))


def balance_gaps(sut: pl.DataFrame) -> pl.DataFrame:
    """By year and product: published total supply, sum of supply items, sum of detailed uses."""
    products = sut.filter(pl.col("block") != "value_added", pl.col("row") != "TOTAL")
    total = products.filter(pl.col("column") == "TOTAL_SUPPLY").select("year", "row", pl.col("value").alias("total_supply"))
    detail = products.filter(~pl.col("aggregate")).group_by("year", "row").agg(
        pl.col("value").filter(pl.col("block") == "supply").sum().alias("supply"),
        pl.col("value").filter(pl.col("block") == "use").sum().alias("use"))
    return (total.join(detail, on=["year", "row"], how="full", coalesce=True)
            .with_columns(pl.col("total_supply", "supply", "use").fill_null(0))
            .with_columns(supply_gap=pl.col("total_supply") - pl.col("supply"), use_gap=pl.col("total_supply") - pl.col("use")))


def output_gaps(sut: pl.DataFrame) -> pl.DataFrame:
    """By year and industry: output = intermediate consumption + value added."""
    ic = sut.filter(pl.col("block") == "use", ~pl.col("aggregate")).group_by("year", "column").agg(pl.col("value").sum().alias("ic"))
    va = (sut.filter(pl.col("block") == "value_added", pl.col("row").is_in(["P1", "B1G"]))
          .pivot("row", index=["year", "column"], values="value"))
    return (va.join(ic, on=["year", "column"], how="left").with_columns(pl.col("ic", "B1G", "P1").fill_null(0))
            .with_columns(gap=pl.col("P1") - pl.col("ic") - pl.col("B1G")))


def main() -> pl.DataFrame:
    # Read every year.
    # Lire toutes les années.
    sut = pl.concat([read_sheet(y, s) for y, s in sorted(sheets().items())])
    write_intermediate(sut, "sut")

    # Supply equals use, and output equals intermediate consumption plus value added.
    # Ressources = emplois, et production = consommation intermédiaire + valeur ajoutée.
    gaps = balance_gaps(sut)
    checks = Checks(SCRIPT)
    checks.add("supply_total", gaps["supply_gap"].abs().max(), 1, "million TND", "Largest gap between total supply and the sum of supply items")
    checks.add("supply_equals_use", gaps["use_gap"].abs().max(), 1, "million TND", "Largest gap between total supply and the sum of uses, by product")
    checks.add("output_identity", output_gaps(sut)["gap"].abs().max(), 1, "million TND", "Largest gap in output = intermediate consumption + value added")
    checks.save()
    return sut


if __name__ == "__main__":
    main()
