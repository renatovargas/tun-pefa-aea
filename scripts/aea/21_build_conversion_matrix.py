"""Build the Tunisian conversion matrix from inventory categories to economic activities.

Why    : the inventory classifies emissions by process (combustion in energy industries,
         road transport, enteric fermentation...), while the accounts classify them by the
         economic unit that emits them: the industries of the national accounts and
         households. The IMF tool performs this move with a conversion matrix that gives,
         for each CRT category and gas, the share of emissions assigned to each activity.
Inputs : data/intermediate/ghg_inventory.parquet (script 20), activity_keys.parquet (script 11)
         data/lookups/crt_to_activities.csv, activities.csv
         imf-tools/i2a/I2A.xlsm (default matrix and CRT table)
Outputs: data/intermediate/conversion_matrix.parquet   year, tool_code, activity, factor, prefix, method, key
         data/intermediate/conversion_changes.parquet  where the Tunisian matrix leaves the default ISIC sections
         data/intermediate/categories_without_factor.parquet  inventory emissions that the default matrix drops
         data/outputs/checks/21_build_conversion_matrix.csv
Method : each tool code takes the row of crt_to_activities.csv with the longest matching
         prefix, so a short prefix ("3" for agriculture) covers a whole sector and a longer
         one overrides it for a sub-category. Rows with method "key" reuse the road transport
         and tertiary keys of the energy accounts, so both accounts split these sectors the
         same way.
Run    : uv run python scripts/aea/21_build_conversion_matrix.py

Construction de la matrice de conversion tunisienne des catégories CRT vers les activités.
Chaque code prend la ligne de crt_to_activities.csv dont le préfixe est le plus long. Les
lignes à clé reprennent les clés du transport routier et du tertiaire des comptes de
l'énergie, pour que les deux comptes répartissent ces secteurs de la même façon.
"""

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import imf_tools  # noqa: E402
from common import Checks, read_intermediate, read_lookup, write_intermediate  # noqa: E402

SCRIPT = "21_build_conversion_matrix"


def tool_section(activity: str) -> str:
    """ISIC section of an activity of the tool, in the section codes of data/lookups/imf_sections.csv."""
    if activity.startswith("HH"):
        return "HH"
    if activity[0] in "ABCDEFH" and not activity.startswith(("NRA", "NRT")):
        return activity[0]
    if activity in ("LULUCF", "OTHER") or activity.startswith(("NRA", "NRT")):
        return activity
    return "Other"


def default_matrix(ranges: dict) -> pl.DataFrame:
    """The default conversion matrix of the tool in long format."""
    header = [str(c) for c in ranges["Conversion_Matrix"][0]]
    return (imf_tools.range_to_table(ranges["Conversion_Matrix"])
            .unpivot(index=["POLLUTANT", "Source_Code", "Check"], on=header[5:], variable_name="tool_activity", value_name="factor")
            .with_columns(pl.col("factor").cast(pl.Float64).fill_null(0), pl.col("Check").cast(pl.Float64).fill_null(0)))


def main() -> pl.DataFrame:
    inventory = read_intermediate("ghg_inventory").filter(pl.col("scope") != "memo")
    pefa_keys = read_intermediate("activity_keys")
    activities, mapping = read_lookup("activities"), read_lookup("crt_to_activities")
    ranges = imf_tools.i2a_ranges()
    years = sorted(inventory["year"].unique().to_list())
    default = default_matrix(ranges)

    # Emissions that the default matrix drops: categories whose factors are all zero (Check = 0).
    # Émissions que la matrice par défaut perd : catégories dont tous les facteurs sont nuls (Check = 0).
    no_factor = default.filter(pl.col("Check") == 0).select(gas="POLLUTANT", tool_code="Source_Code").unique()
    dropped = (inventory.filter(pl.col("scope") == "inventory").join(no_factor, on=["gas", "tool_code"])
               .group_by("year", "tool_code").agg(pl.col("kt_co2_eq").sum()).sort("tool_code", "year"))
    write_intermediate(dropped, "categories_without_factor")

    # The rule of each code is the longest prefix that covers it ("3." is covered by "3").
    # La règle de chaque code est le préfixe le plus long qui le couvre (« 3. » est couvert par « 3 »).
    prefixes = mapping["prefix"].to_list()

    def rule(code: str) -> str | None:
        code = code.rstrip(".")
        covering = [p for p in prefixes if code == p or code.startswith(p + ".")]
        return max(covering, key=len) if covering else None

    # OECD data enter through the codes of domestic aviation and domestic navigation, so these
    # codes need a rule even in years when the inventory has no emissions there.
    # Les données de l'OCDE entrent par les codes de l'aviation et de la navigation intérieures ;
    # ces codes ont besoin d'une règle même les années où l'inventaire n'y a pas d'émissions.
    oecd_codes = [r[1] for r in ranges["CRT"][1:] if r[11] in ("Domestic Aviation", "Domestic Navigation")]
    codes = (pl.concat([inventory.select("tool_code"), pl.DataFrame({"tool_code": oecd_codes})]).unique()
             .with_columns(prefix=pl.col("tool_code").map_elements(rule, return_dtype=pl.String)))

    # Keys: the road transport and tertiary keys of the energy accounts, by year and activity.
    # Clés : les clés du transport routier et du tertiaire des comptes de l'énergie, par année et activité.
    keys = (pefa_keys.filter(pl.col("method") == "key")
            .select("year", key="iea_flow", activity="activity", factor="factor")
            .group_by("year", "key", "activity").agg(pl.col("factor").sum()))
    assert set(mapping["key"].drop_nulls()) <= set(keys["key"]), "Unknown key in crt_to_activities.csv"

    # The matrix: direct rules give a factor of one; keyed rules take the factors of the key.
    # La matrice : les règles directes donnent un facteur de un ; les règles à clé prennent les facteurs de la clé.
    year_table = pl.DataFrame({"year": years}, schema={"year": pl.Int16})
    rules = codes.join(mapping, on="prefix", how="left")
    direct = rules.filter(pl.col("method") == "direct").join(year_table, how="cross").with_columns(factor=pl.lit(1.0))
    keyed = rules.filter(pl.col("method") == "key").drop("activity").join(keys, on="key")
    columns = ["year", "tool_code", "activity", "factor", "prefix", "method", "key"]
    matrix = pl.concat([direct.select(columns), keyed.select(columns)]).sort("year", "tool_code", "activity")
    write_intermediate(matrix, "conversion_matrix")

    # Differences with the default matrix, by ISIC section, for 2022 emissions.
    # Différences avec la matrice par défaut, par section de la CITI, pour les émissions de 2022.
    sections = dict(activities.select("code", "imf_section").iter_rows()) | {"LULUCF": "LULUCF"}
    last = max(years)
    emitted = (inventory.filter(pl.col("year") == last).group_by("tool_code").agg(pl.col("kt_co2_eq").sum())
               .filter(pl.col("kt_co2_eq").abs() > 0.05))
    default_sections = (
        default.filter(pl.col("factor") > 0)
        .join(inventory.filter(pl.col("year") == last).select(POLLUTANT="gas", Source_Code="tool_code").unique(), on=["POLLUTANT", "Source_Code"])
        .with_columns(section=pl.col("tool_activity").map_elements(tool_section, return_dtype=pl.String))
        .group_by("Source_Code", "section").agg(pl.col("factor").sum())
        .sort("factor", descending=True)
        .group_by("Source_Code", maintain_order=True)
        .agg(default_section=pl.col("section").first(), default_sections=pl.col("section").unique().sort().str.join(", "))
        .rename({"Source_Code": "tool_code"}))
    tunisia = (matrix.filter(pl.col("year") == last).with_columns(section=pl.col("activity").replace_strict(sections))
               .group_by("tool_code", "prefix")
               .agg(activities=pl.when(pl.col("method").first() == "key").then(pl.lit("key: ") + pl.col("key").first())
                    .otherwise(pl.col("activity").unique().sort().str.join(", ")),
                    section=pl.col("section").sort_by("factor", descending=True).first()))
    changes = (emitted.join(tunisia, on="tool_code", how="left").join(default_sections, on="tool_code", how="left")
               .with_columns(status=pl.when(pl.col("default_section").is_null()).then(pl.lit("no_default_factor"))
                             .when(pl.col("default_section") != pl.col("section")).then(pl.lit("changed"))
                             .otherwise(pl.lit("same")),
                             year=pl.lit(last, pl.Int16))
               .sort("tool_code")
               .select("year", "tool_code", "kt_co2_eq", "default_section", "default_sections", "section", "activities", "status"))
    write_intermediate(changes, "conversion_changes")

    sums = matrix.group_by("year", "tool_code").agg(pl.col("factor").sum())
    checks = Checks(SCRIPT)
    checks.add("all_codes_have_rule", codes["prefix"].null_count(), 0, "codes", "Tool codes without a rule in crt_to_activities.csv")
    checks.add("factors_sum_to_one", (sums["factor"] - 1).abs().max(), 1e-9, "share", "Factors of each code add up to one")
    checks.add("known_activities", len(set(matrix["activity"]) - set(activities["code"]) - {"LULUCF"}), 0, "activities",
               "Activities of the matrix missing from data/lookups/activities.csv")
    checks.save()
    return matrix


if __name__ == "__main__":
    main()
