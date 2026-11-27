"""Write the energy accounts to Excel in English, French and Arabic.

Why    : the workbooks are the product that users download. They hold the same numbers in
         the three languages; only labels change.
Inputs : data/intermediate/pefa.parquet (script 13), pefa_indicators.parquet (script 14)
         data/lookups/activities.csv, imf_sections.csv, pefa_rows.csv, terms.csv
Outputs: data/outputs/accounts/<language>/pefa_accounts.xlsx with sheets:
           Notes; Data (all years, long format); Supply <year> and Use <year> (products in
           rows, industries in columns, as in the PEFA sheet of the IMF tool); ISIC sections
           (all years, by section, as in the tool); Indicators.
Method : tables are pivoted from the long accounts with the row order of the IMF tool
         (data/lookups/pefa_rows.csv); headers and labels come from the lookups.
Run    : uv run python scripts/pefa/15_export_pefa.py

Export des comptes de l'énergie en Excel, en anglais, en français et en arabe. Les trois
classeurs contiennent les mêmes chiffres ; seuls les libellés changent.
"""

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ACCOUNTS, LANGUAGES, labels, read_intermediate, read_lookup, terms, write_workbook  # noqa: E402

NAME = "pefa_accounts"


def row_order() -> dict[str, dict[str, int]]:
    rows = read_lookup("pefa_rows")
    return {t: dict(rows.filter(pl.col("type") == t).select("key", "order").iter_rows()) for t in ("level1", "level2", "product")}


def ordered(table: pl.DataFrame) -> pl.DataFrame:
    """Add sort keys that follow the row order of the PEFA tables of the IMF tool."""
    o = row_order()
    return table.with_columns(
        o1=pl.col("level1").replace_strict(o["level1"]),
        o2=pl.col("level2").replace_strict(o["level2"], default=0),
        o3=pl.col("product").replace_strict(o["product"]))


def matrix(pefa: pl.DataFrame, year: int, quadrant: str, column: str, codes: list[str], lang: str) -> pl.DataFrame:
    """Supply or use table of one year: products in rows, activities (or sections) in columns."""
    t, rows, names = terms(lang), labels("pefa_rows", lang, key="key"), labels("activities", lang) | labels("imf_sections", lang)
    data = pefa.filter(pl.col("year") == year, pl.col("quadrant") == quadrant)
    present = [c for c in codes if c in set(data[column])]
    table = (ordered(data).pivot(column, index=["o1", "o2", "o3", "level1", "level2", "product"], values="tj", aggregate_function="sum")
             .sort("o1", "o2", "o3"))
    table = table.with_columns(pl.col(present).fill_null(0)).with_columns(pl.sum_horizontal(present).alias("total"))
    return table.select(
        pl.col("level1").replace_strict(rows).alias(t["level1"]),
        pl.col("level2").replace_strict(rows, default=None).alias(t["level2"]),
        pl.col("product").replace_strict(rows).alias(t["product"]),
        *[pl.col(c).alias(f"{c} {names[c]}") for c in present],
        pl.col("total").alias(t["total"]))


def long_data(pefa: pl.DataFrame, lang: str) -> pl.DataFrame:
    t, rows, names = terms(lang), labels("pefa_rows", lang, key="key"), labels("activities", lang)
    return pefa.select(
        pl.col("year").alias(t["year"]),
        pl.col("quadrant").replace_strict({"Supply": t["supply"], "Use": t["use"]}).alias(t["quadrant"]),
        pl.col("level1").replace_strict(rows).alias(t["level1"]),
        pl.col("level2").replace_strict(rows, default=None).alias(t["level2"]),
        pl.col("product").replace_strict(rows).alias(t["product"]),
        pl.col("activity").alias(t["activity_code"]),
        pl.col("activity").replace_strict(names).alias(t["activity"]),
        pl.col("tj").alias(t["tj"]))


def isic_data(pefa: pl.DataFrame, lang: str) -> pl.DataFrame:
    """The accounts added up by ISIC section, the level at which the IMF tool reports."""
    t, rows = terms(lang), labels("pefa_rows", lang, key="key")
    sections = dict(read_lookup("activities").select("code", "imf_section").iter_rows())
    section_names = labels("imf_sections", lang)
    by_section = (ordered(pefa.with_columns(section=pl.col("activity").replace_strict(sections)))
                  .group_by("year", "quadrant", "o1", "o2", "o3", "level1", "level2", "product", "section")
                  .agg(pl.col("tj").sum())
                  .sort("year", "quadrant", "o1", "o2", "o3", "section"))
    return by_section.select(
        pl.col("year").alias(t["year"]),
        pl.col("quadrant").replace_strict({"Supply": t["supply"], "Use": t["use"]}).alias(t["quadrant"]),
        pl.col("level1").replace_strict(rows).alias(t["level1"]),
        pl.col("level2").replace_strict(rows, default=None).alias(t["level2"]),
        pl.col("product").replace_strict(rows).alias(t["product"]),
        pl.col("section").alias(t["section_code"]),
        pl.col("section").replace_strict(section_names).alias(t["activity"]),
        pl.col("tj").alias(t["tj"]))


INDICATORS = ["natural_inputs", "production", "transformation_input", "end_use_energy", "end_use_non_energy",
              "net_domestic_energy_use", "residuals", "output_mtnd", "value_added_mtnd", "household_consumption_mtnd",
              "intensity_output", "intensity_value_added", "intensity_household"]


def indicator_data(indicators: pl.DataFrame, lang: str) -> pl.DataFrame:
    t, names = terms(lang), labels("activities", lang)
    return indicators.select(
        pl.col("year").alias(t["year"]),
        pl.col("activity").alias(t["activity_code"]),
        pl.col("activity").replace_strict(names).alias(t["activity"]),
        *[pl.col(c).alias(t[c]) for c in INDICATORS])


def main() -> None:
    pefa = read_intermediate("pefa")
    indicators = read_intermediate("pefa_indicators")
    codes = read_lookup("activities")["code"].to_list()
    years = sorted(pefa["year"].unique().to_list())

    # One workbook per language.
    # Un classeur par langue.
    for lang in LANGUAGES:
        t = terms(lang)
        sheets = [(t["sheet_data"], long_data(pefa, lang), 1)]
        for year in years:
            sheets.append((f"{t['sheet_supply']} {year}", matrix(pefa, year, "Supply", "activity", codes, lang), 1))
            sheets.append((f"{t['sheet_use']} {year}", matrix(pefa, year, "Use", "activity", codes, lang), 1))
        sheets.append((t["sheet_isic"], isic_data(pefa, lang), 1))
        sheets.append((t["sheet_indicators"], indicator_data(indicators, lang), 3))
        notes = [t[k] for k in ["title_pefa", "unit_tj", "note_source_pefa", "note_method_pefa", "note_provisional", "note_site", "note_code"]]
        write_workbook(ACCOUNTS / lang / f"{NAME}.xlsx", t["sheet_notes"], notes, sheets, right_to_left=lang == "ar")


if __name__ == "__main__":
    main()
