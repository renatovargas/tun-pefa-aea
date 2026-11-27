"""Extract the national energy balances of ONEM, 2015 to 2022.

Why    : the balances are the source of the energy accounts. Their layout changes between
         years, so they are read by their labels, never by cell positions.
Inputs : data/sources/energy-balance/balance20XX.xlsx|xltx (thousand toe, one sheet each)
         data/lookups/balance_flow_sources.csv, balance_product_sources.csv (source labels to codes)
         data/lookups/balance_flows.csv, balance_products.csv (codes, hierarchy and signs)
Outputs: data/intermediate/energy_balances.parquet  long table: year, order, flow, product, ktoe, tj
         data/outputs/checks/01_extract_energy_balances.csv
Method : each workbook is read as text, the product header is rebuilt from two rows, the
         rows are put in long format, and each source label receives a stable code. Labels
         that repeat ("Raffineries" as input and as output) are told apart by the block they
         sit in. The script stops on any label without a code, then checks that every total
         equals the signed sum of its parts.
Run    : uv run python scripts/extract/01_extract_energy_balances.py

Extraction des bilans énergétiques de l'ONEM, 2015 à 2022. Les bilans sont lus par leurs
libellés, jamais par la position des cellules, car leur présentation change d'une année à
l'autre. Chaque libellé reçoit un code stable ; le script s'arrête sur tout libellé inconnu,
puis vérifie que chaque total égale la somme signée de ses composantes.
"""

import re
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import KTOE_TO_TJ, SOURCES, Checks, read_lookup, write_intermediate  # noqa: E402

SCRIPT = "01_extract_energy_balances"
FOLDER = SOURCES / "energy-balance"

# Block headings change the meaning of labels that repeat further down the sheet.
# Les titres de bloc changent le sens des libellés qui se répètent plus bas dans la feuille.
BLOCK_HEADINGS = {
    "Entrées en transformation": "transformation_input",
    "Sortie de transformation": "transformation_output",
    "Echanges, transfer, restitutions": "transfers",
    "Consommation finale non énergétique": "non_energy",
    "Consommation finale énergétique": "energy",
}


def clean(text: str | None) -> str | None:
    """Remove extra spaces and line breaks from a label."""
    if text is None:
        return None
    text = " ".join(text.split())
    return text or None


def balance_files() -> dict[int, Path]:
    return {int(re.search(r"(\d{4})", f.name).group(1)): f for f in sorted(FOLDER.glob("balance*.xl*"))}


def read_balance(path: Path, year: int) -> pl.DataFrame:
    """Read one balance and return a long table with the source labels."""
    raw = pl.read_excel(path, has_header=False, engine="calamine", infer_schema_length=0)
    rows = raw.with_row_index()

    # The product header spans the row that starts with "en 1000 tep" and the row below it.
    # L'en-tête des produits occupe la ligne qui commence par « en 1000 tep » et la suivante.
    header = rows.filter(pl.col("column_0").str.starts_with("en 1000 tep"))["index"][0]
    products = [clean(" ".join(x for x in (raw[header, j], raw[header + 1, j]) if x)) for j in range(1, raw.width)]

    # The body starts at primary production.
    # Le corps du bilan commence à la production primaire.
    start = rows.filter(pl.col("column_0").str.strip_chars() == "Production primaire")["index"][0]
    body = raw[start:].rename({"column_0": "flow_source"} | {f"column_{j}": products[j - 1] for j in range(1, raw.width)})
    body = body.with_columns(pl.col("flow_source").map_elements(clean, return_dtype=pl.String))
    body = body.filter(pl.col("flow_source").is_not_null())

    # Each row inherits the block of the last heading above it.
    # Chaque ligne hérite du bloc du dernier titre placé au-dessus d'elle.
    blocks, current = [], "supply"
    for label in body["flow_source"]:
        current = BLOCK_HEADINGS.get(label, current)
        blocks.append(current)
    body = body.with_columns(pl.Series("block", blocks), pl.Series("source_order", range(1, body.height + 1)))

    long = body.unpivot(index=["source_order", "block", "flow_source"], variable_name="product_source", value_name="value")

    # One 2015 cell carries a footnote mark ("0 *"); the asterisk is removed.
    # Une cellule de 2015 porte un renvoi (« 0 * ») ; l'astérisque est retiré.
    text = long["value"].str.replace(r"\s*\*$", "").str.strip_chars()
    values = text.cast(pl.Float64, strict=False)
    unreadable = long.filter(values.is_null() & text.ne(""))
    if unreadable.height:
        raise ValueError(f"{year}: non-numeric values {unreadable['value'].unique().to_list()}")
    return (
        long.with_columns(ktoe=values, year=pl.lit(year, pl.Int16))
        .filter(pl.col("ktoe").is_not_null() & (pl.col("ktoe") != 0))
        .drop("value")
    )


def assign_codes(long: pl.DataFrame) -> pl.DataFrame:
    """Give every row a flow code and a product code; stop on any unknown label."""
    flows = read_lookup("balance_flow_sources").rename({"source_label": "flow_source", "code": "flow"})
    products = read_lookup("balance_product_sources").rename({"source_label": "product_source", "code": "product"})
    coded = long.join(flows, on=["block", "flow_source"], how="left").join(products, on="product_source", how="left")
    missing = coded.filter(pl.col("flow").is_null() | pl.col("product").is_null())
    if missing.height:
        raise ValueError("Labels without a code: " + str(missing.select("year", "block", "flow_source", "product_source").unique().rows()))
    return coded


def aggregate(coded: pl.DataFrame) -> pl.DataFrame:
    """Add up rows that receive the same code (the 2015 layout) and convert to terajoules."""
    order = read_lookup("balance_flows").with_row_index("order").select(pl.col("code").alias("flow"), "order")
    return (
        coded.group_by("year", "flow", "product")
        .agg(pl.col("flow_source").unique(maintain_order=True).str.join(" + "),
             pl.col("product_source").first(), pl.col("ktoe").sum())
        .join(order, on="flow")
        .with_columns(tj=pl.col("ktoe") * KTOE_TO_TJ, order=pl.col("order").cast(pl.Int16))
        .sort("year", "order", "product")
        .select("year", "order", "flow", "product", "flow_source", "product_source", "ktoe", "tj")
    )


def hierarchy_gaps(balances: pl.DataFrame, dimension: str) -> pl.DataFrame:
    """Compare each published total with the signed sum of its parts.

    `dimension` is "flow" or "product". Returns one gap per year, total and item of the other dimension.
    """
    lookup = read_lookup({"flow": "balance_flows", "product": "balance_products"}[dimension])
    if "sign" not in lookup.columns:
        lookup = lookup.with_columns(sign=pl.lit(1))
    other = "product" if dimension == "flow" else "flow"
    children = lookup.filter(pl.col("parent").is_not_null()).select(pl.col("code").alias(dimension), "parent", "sign")
    computed = (balances.join(children, on=dimension)
                .group_by("year", "parent", other).agg((pl.col("ktoe") * pl.col("sign")).sum().alias("computed")))
    published = balances.filter(pl.col(dimension).is_in(children["parent"].unique().implode())).select(
        "year", pl.col(dimension).alias("parent"), other, pl.col("ktoe").alias("published"))
    return (published.join(computed, on=["year", "parent", other], how="full", coalesce=True)
            .with_columns(pl.col("published", "computed").fill_null(0))
            .with_columns(gap=pl.col("published") - pl.col("computed")))


def availability_gaps(balances: pl.DataFrame) -> pl.DataFrame:
    """Check, by product, that available for final consumption equals supply minus transformation, own use and losses.

    Available = gross inland consumption - transformation input + transformation output
                + transfers - energy sector own use - losses.
    """
    signs = {"GIC": 1, "TI": -1, "TO": 1, "TRF": 1, "OWNUSE": -1, "LOSSES": -1}
    computed = (balances.filter(pl.col("flow").is_in(list(signs)))
                .with_columns(sign=pl.col("flow").replace_strict(signs, return_dtype=pl.Int8))
                .group_by("year", "product").agg((pl.col("ktoe") * pl.col("sign")).sum().alias("computed")))
    published = balances.filter(pl.col("flow") == "AVAIL").select("year", "product", pl.col("ktoe").alias("published"))
    return (published.join(computed, on=["year", "product"], how="full", coalesce=True)
            .with_columns(pl.col("published", "computed").fill_null(0))
            .with_columns(gap=pl.col("published") - pl.col("computed")))


def main() -> pl.DataFrame:
    # Read, code and stack every year.
    # Lire, coder et empiler toutes les années.
    tables = [read_balance(path, year) for year, path in balance_files().items()]
    balances = aggregate(assign_codes(pl.concat(tables)))
    write_intermediate(balances, "energy_balances")

    # The published balances are rounded to the unit, so totals may differ from their parts by a few ktoe.
    # Les bilans publiés sont arrondis à l'unité : un total peut différer de ses composantes de quelques ktep.
    checks = Checks(SCRIPT)
    checks.add("flow_hierarchy", hierarchy_gaps(balances, "flow")["gap"].abs().max(), 2.5, "ktoe",
               "Largest gap between a flow total and the signed sum of its sub-flows")
    checks.add("product_hierarchy", hierarchy_gaps(balances, "product")["gap"].abs().max(), 2.5, "ktoe",
               "Largest gap between a product total and the sum of its products")
    checks.add("availability_identity", availability_gaps(balances)["gap"].abs().max(), 2.5, "ktoe",
               "Largest gap in: available = supply - transformation - own use - losses")
    checks.save()
    return balances


if __name__ == "__main__":
    main()
