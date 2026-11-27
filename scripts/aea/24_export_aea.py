"""Write the air emissions accounts to Excel in English, French and Arabic.

Why    : the workbooks are the product that users download. They hold the same numbers in
         the three languages; only labels change.
Inputs : data/intermediate/aea.parquet (script 22), aea_bridge.parquet and aea_indicators.parquet (script 23)
         data/lookups/activities.csv, gases.csv, aea_bridge.csv, terms.csv
Outputs: data/outputs/accounts/<language>/aea-accounts-<language>.xlsx with sheets:
           Notes; Data (all years, long, by CRT category and activity); Bridge (accounts to
           inventory, all years); AEA <year> (activities in rows, gases in columns, as in the
           AEA sheet of the IMF tool); Source by activity (as in sheet Output_Source_Activity);
           Indicators.
Run    : uv run python scripts/aea/24_export_aea.py

Export des comptes des émissions atmosphériques en Excel, en anglais, en français et en
arabe. Les trois classeurs contiennent les mêmes chiffres ; seuls les libellés changent.
"""

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ACCOUNTS, LANGUAGES, PSEUDO_ACTIVITIES, labels, read_intermediate, read_lookup, terms, write_workbook  # noqa: E402

NAME = "aea-accounts"
GASES = ["CO2", "CH4", "N2O", "F-gases", "GHG"]
BRIDGE_ORDER = read_lookup("aea_bridge").sort("order")["code"].to_list()
ACTIVITIES = [c for c in read_lookup("activities")["code"] if c not in PSEUDO_ACTIVITIES]


def year_table(aea: pl.DataFrame, year: int, lang: str) -> pl.DataFrame:
    """Emissions of one year: activities in rows, gases in columns, with a total row."""
    t, names, gases = terms(lang), labels("activities", lang), labels("gases", lang)
    wide = (aea.filter(pl.col("year") == year, pl.col("activity").is_in(ACTIVITIES))
            .group_by("activity", "gas").agg(pl.col("kt_co2_eq").sum())
            .pivot("gas", index="activity", values="kt_co2_eq")
            .with_columns(order=pl.col("activity").replace_strict({c: i for i, c in enumerate(ACTIVITIES)}, return_dtype=pl.Int16))
            .sort("order"))
    columns = [g for g in GASES if g in wide.columns]
    wide = wide.with_columns(pl.col(columns).fill_null(0))
    total = wide.select(pl.col(columns).sum()).with_columns(activity=pl.lit(None, pl.String), order=pl.lit(999, pl.Int16))
    wide = pl.concat([wide, total.select(wide.columns)])
    return wide.select(pl.col("activity").alias(t["activity_code"]),
                       pl.col("activity").replace_strict(names, default=t["total"]).alias(t["activity"]),
                       *[pl.col(g).alias(gases[g]) for g in columns])


def bridge_table(bridge: pl.DataFrame, lang: str) -> pl.DataFrame:
    t, items = terms(lang), labels("aea_bridge", lang)
    return (bridge.filter(pl.col("gas") == "GHG")
            .unpivot(index="year", on=BRIDGE_ORDER, variable_name="code", value_name="kt")
            .pivot("year", index="code", values="kt")
            .select(pl.col("code").replace_strict(items).alias(t["bridge_item"]), pl.exclude("code")))


def long_data(aea: pl.DataFrame, lang: str) -> pl.DataFrame:
    t, names, gases = terms(lang), labels("activities", lang), labels("gases", lang)
    return aea.filter(pl.col("activity").is_in(ACTIVITIES), pl.col("gas") != "GHG").select(
        pl.col("year").alias(t["year"]), pl.col("gas").replace_strict(gases).alias(t["gas"]),
        pl.col("source").alias(t["crt_category"]), pl.col("activity").alias(t["activity_code"]),
        pl.col("activity").replace_strict(names).alias(t["activity"]), pl.col("kt_co2_eq").alias(t["kt_co2_eq"]))


def source_by_activity(aea: pl.DataFrame, lang: str) -> pl.DataFrame:
    """Total greenhouse gases by CRT category (rows) and activity (columns), all years."""
    t, names = terms(lang), labels("activities", lang)
    data = aea.filter(pl.col("activity").is_in(ACTIVITIES), pl.col("gas") == "GHG")
    present = [c for c in ACTIVITIES if c in set(data["activity"])]
    wide = (data.pivot("activity", index=["year", "source"], values="kt_co2_eq", aggregate_function="sum")
            .with_columns(pl.col(present).fill_null(0)).sort("year", "source"))
    return wide.select(pl.col("year").alias(t["year"]), pl.col("source").alias(t["crt_category"]),
                       *[pl.col(c).alias(f"{c} {names[c]}") for c in present])


INDICATORS = ["ghg_kt", "output_mtnd", "value_added_mtnd", "household_consumption_mtnd",
              "ghg_intensity_output", "ghg_intensity_value_added", "ghg_intensity_household"]


def indicator_data(indicators: pl.DataFrame, lang: str) -> pl.DataFrame:
    t, names = terms(lang), labels("activities", lang)
    return indicators.select(pl.col("year").alias(t["year"]), pl.col("activity").alias(t["activity_code"]),
                             pl.col("activity").replace_strict(names).alias(t["activity"]),
                             *[pl.col(c).alias(t[c]) for c in INDICATORS])


def main() -> None:
    aea = read_intermediate("aea")
    bridge = read_intermediate("aea_bridge")
    indicators = read_intermediate("aea_indicators")
    years = sorted(aea["year"].unique().to_list())

    # One workbook per language.
    # Un classeur par langue.
    for lang in LANGUAGES:
        t = terms(lang)
        sheets = [(t["sheet_data"], long_data(aea, lang), 3), (t["sheet_bridge"], bridge_table(bridge, lang), 1)]
        sheets += [(f"{t['sheet_aea']} {year}", year_table(aea, year, lang), 1) for year in years]
        sheets.append((t["sheet_source_activity"], source_by_activity(aea, lang), 2))
        sheets.append((t["sheet_indicators"], indicator_data(indicators, lang), 1))
        notes = [t[k] for k in ["title_aea", "unit_kt_co2_eq", "note_source_aea", "note_method_aea", "note_provisional", "note_site", "note_code"]]
        write_workbook(ACCOUNTS / lang / f"{NAME}-{lang}.xlsx", t["sheet_notes"], notes, sheets, right_to_left=lang == "ar")


if __name__ == "__main__":
    main()
