"""Call the IMF tools without Excel (reference layer).

The IMF PEFA Converter and Air Emissions Account Converter (I2A), by Achille Pegoue
(IMF Statistics Department), are Excel workbooks that call Python functions through
xlwings. This module loads those functions unchanged from imf-tools/, replaces xlwings
with a minimal stand-in, and passes ranges built the way Excel builds them (lists of
lists, numbers as floats, empty cells as None). The pipeline uses it to confirm that
its own, explicit implementation gives the same numbers as the tools.

Appel des outils du FMI sans Excel (couche de référence). Le PEFA Converter et le
convertisseur I2A du FMI (Achille Pegoue, Département des statistiques) sont des
classeurs Excel qui appellent des fonctions Python par xlwings. Ce module charge ces
fonctions telles quelles depuis imf-tools/, remplace xlwings par un module minimal et
leur passe des plages construites comme Excel le fait. Le pipeline s'en sert pour
vérifier que sa propre mise en œuvre, explicite, donne les mêmes chiffres que les outils.
"""

from __future__ import annotations

import importlib.util
import sys
import types
import warnings
from pathlib import Path

import openpyxl
import pandas as pd
import polars as pl

warnings.filterwarnings("ignore", message="Data Validation extension", category=UserWarning)

from common import IMF_TOOLS

PEFA_FOLDER = IMF_TOOLS / "pefa-converter"
PEFA_WORKBOOK = PEFA_FOLDER / "PEFA_Converter.xlsm"
I2A_FOLDER = IMF_TOOLS / "i2a"
I2A_WORKBOOK = I2A_FOLDER / "I2A.xlsm"

# Default filter of cell PEFA!B1 in the workbook (with two leading spaces).
# Filtre par défaut de la cellule PEFA!B1 du classeur (avec deux espaces au début).
DEFAULT_FILTER = "  ALL (Statistical difference exclusive)"

PEFA_COLUMNS = ["PEFA_Target_Product_Level1", "PEFA_Target_Product_Level2", "PEFA_Target_Product",
                "PEFA_Target_Activity", "PEFA_Quadrant", "PEFA_Energy"]

# Values of the parameter cells of sheet Output_Source_Activity in I2A.xlsm.
# Valeurs des cellules de paramètres de la feuille Output_Source_Activity de I2A.xlsm.
USE_OECD = "Use OECD International Transport Emissions"
NO_OECD = "Do Not Use OECD International Transport Emissions"
UNIT_KT = "Thousand tonnes CO2Eq"


# ---------------------------------------------------------------------------
# Loading the tool code and rebuilding Excel ranges.
# Chargement du code des outils et reconstitution des plages Excel.
# ---------------------------------------------------------------------------

def _stub_xlwings() -> None:
    """Install an `xlwings` module whose `func` decorator returns the function unchanged."""
    if "xlwings" not in sys.modules or not hasattr(sys.modules["xlwings"], "func"):
        module = types.ModuleType("xlwings")
        module.func = lambda f: f
        sys.modules["xlwings"] = module


def _load(path: Path, name: str) -> types.ModuleType:
    _stub_xlwings()
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_pefa_converter() -> types.ModuleType:
    return _load(PEFA_FOLDER / "PEFA_Converter.py", "PEFA_Converter")


def load_i2a() -> types.ModuleType:
    return _load(I2A_FOLDER / "I2A.py", "I2A")


def _excel_value(x):
    """Return a cell value as xlwings does: numbers as floats."""
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, (int, float)):
        return float(x)
    return x


def _counta(rows: list[tuple], column: int | None = None, row: int | None = None) -> int:
    """COUNTA over a whole column or a whole row (0-based indices)."""
    if column is not None:
        return sum(1 for r in rows if len(r) > column and r[column] not in (None, ""))
    return sum(1 for x in rows[row] if x not in (None, ""))


def _offset(rows: list[tuple], row: int, column: int, height: int, width: int) -> list[list]:
    """OFFSET(anchor,,,height,width): a range as a list of lists."""
    block = []
    for r in rows[row: row + height]:
        r = list(r) + [None] * (column + width - len(r))
        block.append([_excel_value(x) for x in r[column: column + width]])
    return block


def _sheets(path: Path, names: list[str]) -> dict[str, list[tuple]]:
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sheets = {name: list(workbook[name].iter_rows(values_only=True)) for name in names}
    workbook.close()
    return sheets


def range_to_table(block: list[list]) -> pl.DataFrame:
    """Turn an Excel range (header row first) into a polars table."""
    return pl.DataFrame(block[1:], schema=[str(c) for c in block[0]], orient="row", infer_schema_length=None)


# ---------------------------------------------------------------------------
# PEFA Converter.
# PEFA Converter.
# ---------------------------------------------------------------------------

def pefa_ranges(balance_sheet: str = "Energy_Balance") -> dict:
    """Rebuild the named ranges of PEFA_Converter.xlsm from their OFFSET/COUNTA definitions.

    Energy_Balance      OFFSET(Energy_Balance!$A$2,,,COUNTA($A:$A),COUNTA($2:$2))
    Concordance_Matrix  OFFSET(Concordance_Matrix!$B$1,,,COUNTA($B:$B),COUNTA($1:$1))
    EB_Bridging_Items   OFFSET(Bridging_Items!$A$2,,,COUNTA($A:$A)+1,COUNTA($2:$2))
    EB_Product          OFFSET(Classification!$U$1,,,COUNTA($U:$U),3)
    """
    s = _sheets(PEFA_WORKBOOK, [balance_sheet, "Concordance_Matrix", "Bridging_Items", "Classification", "PEFA"])
    balance, cm, bridge, classification = (s[n] for n in [balance_sheet, "Concordance_Matrix", "Bridging_Items", "Classification"])
    return {
        "EB": _offset(balance, 1, 0, _counta(balance, column=0), _counta(balance, row=1)),
        "CM": _offset(cm, 0, 1, _counta(cm, column=1), _counta(cm, row=0)),
        "EB_Bridging_Items": _offset(bridge, 1, 0, _counta(bridge, column=0) + 1, _counta(bridge, row=1)),
        "EB_Product": _offset(classification, 0, 20, _counta(classification, column=20), 3),
        "Filter": s["PEFA"][0][1],
    }


def template_flows() -> list[str]:
    """Ordered flows of the balance template (sheet Energy_Balance_Template, column A)."""
    return [r[0] for r in pefa_ranges("Energy_Balance_Template")["EB"][1:]]


def template_products() -> list[str]:
    """Ordered products of the balance template, without the Total column."""
    return [p for p in pefa_ranges("Energy_Balance_Template")["EB"][0][1:] if p != "Total"]


def drop_total_column(block: list[list]) -> list[list]:
    """Remove the Total column of an Energy_Balance range (see imf-tools/README.md)."""
    j = block[0].index("Total")
    return [row[:j] + row[j + 1:] for row in block]


def balance_to_range(balance: pl.DataFrame, flows: list[str], products: list[str]) -> list[list]:
    """Build the Energy_Balance range from a long balance (iea_flow, iea_product, tj).

    All template rows are present, in template order, because EB2PEFA finds the blocks
    of the balance by the position of their headings. Empty cells are 0, as in the template.
    """
    totals = balance.group_by("iea_flow", "iea_product").agg(pl.col("tj").sum())
    values = {(f, p): v for f, p, v in totals.iter_rows()}
    return [[None] + list(products)] + [[f] + [float(values.get((f, p), 0.0)) for p in products] for f in flows]


def matrix_to_range(matrix: pl.DataFrame, columns: list[str]) -> list[list]:
    """A concordance matrix as an Excel range: header, then rows, empty cells as None."""
    return [columns] + [list(r) for r in matrix.select(columns).iter_rows()]


def eb2pefa(eb: list[list], cm: list[list], bridge: list[list], products: list[list],
            filter_text: str = DEFAULT_FILTER) -> pl.DataFrame:
    """Call EB2PEFA and return its result as a polars table (energy in PJ, as in the tool)."""
    module = load_pefa_converter()
    # The tool code raises pandas warnings (SettingWithCopy, FutureWarning) that do not affect the result.
    # Le code de l'outil émet des avertissements pandas sans effet sur le résultat.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = pd.DataFrame(module.EB2PEFA(eb, cm, bridge, products, filter_text))
    columns = {c: [x if isinstance(x, str) else None for x in result[c]] for c in PEFA_COLUMNS[:-1]}
    columns["PEFA_Energy"] = [float(x) for x in result["PEFA_Energy"]]
    return pl.DataFrame(columns)


# ---------------------------------------------------------------------------
# Air Emissions Account Converter (I2A).
# Convertisseur des comptes des émissions atmosphériques (I2A).
# ---------------------------------------------------------------------------

def i2a_ranges() -> dict:
    """Rebuild the I2A ranges for a CRT inventory from their OFFSET/COUNTA definitions.

    The "_Def" sheets hold the default tables of the tool; the active sheets of the
    example workbook carry demonstration factors. The ranges are built from the "_Def"
    sheets with the definitions of the named ranges:
    Conversion_Matrix_CRT  OFFSET($A$1,,,COUNTA($C:$C),COUNTA($1:$1))
    Activity               OFFSET($A$1,,,COUNTA($A:$A),COUNTA($1:$1))
    CRT                    OFFSET($A$1,,,COUNTA($A:$A),COUNTA($1:$1))
    """
    s = _sheets(I2A_WORKBOOK, ["Conversion_Matrix_CRT_Def", "Activity_Def", "CRT_Def", "NFR"])
    cm, act, crt, nfr = (s[n] for n in ["Conversion_Matrix_CRT_Def", "Activity_Def", "CRT_Def", "NFR"])
    return {
        "Conversion_Matrix": _offset(cm, 0, 0, _counta(cm, column=2), _counta(cm, row=0)),
        "Activity": _offset(act, 0, 0, _counta(act, column=0), _counta(act, row=0)),
        "CRT": _offset(crt, 0, 0, _counta(crt, column=0), _counta(crt, row=0)),
        "NFR": _offset(nfr, 0, 0, _counta(nfr, column=0), _counta(nfr, row=0)),
    }


def oecd_ranges(country: str = "TUN") -> dict:
    """OECD air and maritime transport emissions, filtered as Read_OECD does.

    The files in imf-tools/i2a/I2A_Data/ are the rows of the country taken from the
    DSD_AIR_TRANSPORT.csv and DSD_MARITIME_TRANSPORT.csv files shipped with the tool
    (values in tonnes). Read_OECD keeps annual data for all flights, for the emissions of
    residents, and all vessels for maritime transport.
    """
    air = pd.read_csv(I2A_FOLDER / "I2A_Data" / f"DSD_AIR_TRANSPORT_{country}.csv")
    air = air[(air["REF_AREA"] == country) & (air["FREQ"] == "A") & (air["FLIGHT_TYPE"] == "_T")
              & air["EMISSIONS_SOURCE"].isin(["RES_DOM_IN", "RES_DOM_OUT", "RES_INT_FROM", "RES_INT_TO", "RES_INT_OUT"])]
    sea = pd.read_csv(I2A_FOLDER / "I2A_Data" / f"DSD_MARITIME_TRANSPORT_{country}.csv")
    sea = sea[(sea["REF_AREA"] == country) & (sea["FREQ"] == "A") & (sea["VESSEL"] == "ALL_VESSELS")]

    def block(d: pd.DataFrame) -> list[list]:
        d = d.astype(object).where(d.notna(), None)
        return [list(d.columns)] + d.values.tolist()

    return {"OECD_Air": block(air), "OECD_Sea": block(sea)}


def i2a(inventory: list[list], matrix: list[list], crt: list[list], nfr: list[list], activity: list[list],
        oecd: dict | None = None, use_oecd: str = NO_OECD, unit: str = UNIT_KT) -> pl.DataFrame:
    """Call I2A as the formula in Output_Source_Activity!B3 does and return a long polars table.

    Arguments in the order of the formula: Inventory_2, Conversion_Matrix, CRT, NFR,
    Activity, inventory type ("UNFCCC"), CRT and activity levels (empty cells),
    OECD_Air, OECD_Sea, OECD choice and unit.
    """
    module = load_i2a()
    oecd = oecd or {"OECD_Air": [], "OECD_Sea": []}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = module.I2A(inventory, matrix, crt, nfr, activity, "UNFCCC", None, None,
                         oecd["OECD_Air"], oecd["OECD_Sea"], use_oecd, unit)
    keys = ["POLLUTANT", "Source_Code", "Source_Description", "Activity", "Description"]
    years = [c for c in out.columns if c not in keys + ["REF_AREA", "CountryName"]]
    long = out.melt(id_vars=keys, value_vars=years, var_name="year", value_name="value")
    long = long[long["value"].notna()]
    return pl.DataFrame({
        **{c: [x if isinstance(x, str) else None for x in long[c]] for c in keys},
        "year": [int(a) for a in long["year"]],
        "value": [float(v) for v in long["value"]],
    })
