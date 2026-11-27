"""Shared functions of the pipeline: paths, constants, lookups, checks and Excel output.

Every numbered script imports this module. It holds no calculation of the accounts,
only what several scripts need in the same form.

Fonctions communes du pipeline : chemins, constantes, nomenclatures, contrôles et
sorties Excel. Chaque script numéroté importe ce module. Il ne contient aucun calcul
des comptes, seulement ce dont plusieurs scripts ont besoin sous la même forme.
"""

from __future__ import annotations

import time
from pathlib import Path

import polars as pl

# ---------------------------------------------------------------------------
# Paths. Every path is absolute, so a script runs from any folder.
# Chemins. Tous les chemins sont absolus : un script s'exécute depuis n'importe quel dossier.
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCES = DATA / "sources"
LOOKUPS = DATA / "lookups"
INTERMEDIATE = DATA / "intermediate"
OUTPUTS = DATA / "outputs"
ACCOUNTS = OUTPUTS / "accounts"  # Excel workbooks, one folder per language / classeurs Excel, un dossier par langue
TABLES = OUTPUTS / "tables"  # tidy tables read by the documents / tableaux lus par les documents
LABELS = OUTPUTS / "labels"  # label tables in three languages / libellés en trois langues
CHECKS = OUTPUTS / "checks"  # results of the consistency checks / résultats des contrôles
IMF_TOOLS = ROOT / "imf-tools"

REPO_URL = "https://github.com/renatovargas/tun-pefa-aea"
SITE_URL = "https://renatovargas.github.io/tun-pefa-aea/"

# ---------------------------------------------------------------------------
# Constants.
# Constantes.
# ---------------------------------------------------------------------------

# One tonne of oil equivalent is 41.868 GJ, so one thousand toe is 41.868 TJ.
# Une tonne équivalent pétrole vaut 41,868 GJ, donc une ktep vaut 41,868 TJ.
KTOE_TO_TJ = 41.868

# 100-year global warming potentials of the IPCC Fifth Assessment Report (AR5), used by the Tunisian inventory.
# Potentiels de réchauffement global à 100 ans du cinquième rapport du GIEC (AR5), utilisés par l'inventaire tunisien.
GWP_AR5 = {"CO2": 1, "CH4": 28, "N2O": 265}

LANGUAGES = ("en", "fr", "ar")

# Codes of the activities that are not industries of the supply and use tables.
# Codes des activités qui ne sont pas des branches du tableau des ressources et des emplois.
HOUSEHOLDS = "HH"
PSEUDO_ACTIVITIES = ["ROW", "ACC", "ENV", "STATDIFF"]

# Codes are text even when they look like numbers ("01", "06").
# Les codes sont du texte même quand ils ressemblent à des nombres (« 01 », « 06 »).
CODE_COLUMNS = {c: pl.String for c in ["code", "activity", "key_product", "prefix", "parent", "product", "flow"]}


# ---------------------------------------------------------------------------
# Reading and writing tables.
# Lecture et écriture des tableaux.
# ---------------------------------------------------------------------------

def read_lookup(name: str) -> pl.DataFrame:
    """Read a hand-edited lookup from data/lookups/, with code columns as text."""
    path = LOOKUPS / f"{name}.csv"
    header = pl.read_csv(path, n_rows=0).columns
    return pl.read_csv(path, schema_overrides={c: t for c, t in CODE_COLUMNS.items() if c in header})


def write_parquet(table: pl.DataFrame, folder: Path, name: str) -> Path:
    """Write a table as zstd-compressed Parquet and report its size."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.parquet"
    table.write_parquet(path, compression="zstd")
    log(f"wrote {path.relative_to(ROOT)} ({table.height} rows)")
    return path


def read_intermediate(name: str) -> pl.DataFrame:
    return pl.read_parquet(INTERMEDIATE / f"{name}.parquet")


def write_intermediate(table: pl.DataFrame, name: str) -> Path:
    return write_parquet(table, INTERMEDIATE, name)


def write_output_table(table: pl.DataFrame, name: str) -> Path:
    """Write a table for the documents and the data explorer, in Parquet and in CSV."""
    path = write_parquet(table, TABLES, name)
    table.write_csv(TABLES / f"{name}.csv")
    return path


def read_output_table(name: str) -> pl.DataFrame:
    return pl.read_parquet(TABLES / f"{name}.parquet")


# ---------------------------------------------------------------------------
# Labels in three languages.
# Libellés en trois langues.
# ---------------------------------------------------------------------------

def labels(lookup: str, language: str, key: str = "code") -> dict[str, str]:
    """Map the codes of a lookup to their labels in one language."""
    table = read_lookup(lookup)
    return dict(zip(table[key].cast(pl.String), table[language]))


def terms(language: str) -> dict[str, str]:
    """Terms used in Excel headers, sheet names and notes (data/lookups/terms.csv)."""
    return labels("terms", language, key="key")


# ---------------------------------------------------------------------------
# Checks. Each script records its checks in data/outputs/checks/<script>.csv, and
# stops if one fails, so that no later step reads a wrong table.
# Contrôles. Chaque script enregistre ses contrôles dans data/outputs/checks/<script>.csv
# et s'arrête si l'un d'eux échoue, pour qu'aucune étape ultérieure ne lise un tableau faux.
# ---------------------------------------------------------------------------

class Checks:
    """Collect named checks with their value, tolerance and unit."""

    def __init__(self, script: str):
        self.script = script
        self.rows: list[dict] = []

    def add(self, name: str, value: float, tolerance: float, unit: str, description: str) -> None:
        """Record a check that passes when |value| <= tolerance. Stop the pipeline when it fails."""
        value = float(value)
        passed = abs(value) <= tolerance
        self.rows.append({"script": self.script, "check": name, "value": value, "tolerance": tolerance,
                          "unit": unit, "passed": passed, "description": description})
        status = "ok" if passed else "FAILED"
        log(f"check {name}: {value:.3g} {unit} (tolerance {tolerance:g}) {status}")
        if not passed:
            self.save()
            raise AssertionError(f"{self.script}: check '{name}' failed ({value} {unit} > {tolerance})")

    def save(self) -> None:
        CHECKS.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(self.rows, schema={"script": pl.String, "check": pl.String, "value": pl.Float64,
                                        "tolerance": pl.Float64, "unit": pl.String, "passed": pl.Boolean,
                                        "description": pl.String}).write_csv(CHECKS / f"{self.script}.csv")


# ---------------------------------------------------------------------------
# Excel workbooks.
# Classeurs Excel.
# ---------------------------------------------------------------------------

def write_workbook(path: Path, notes_name: str, notes: list[str], sheets: list[tuple[str, pl.DataFrame, int]],
                   right_to_left: bool) -> Path:
    """Write a workbook with a notes sheet followed by one sheet per table.

    `sheets` holds (sheet name, table, decimals). Arabic workbooks read from right to left.
    """
    import xlsxwriter

    path.parent.mkdir(parents=True, exist_ok=True)
    with xlsxwriter.Workbook(path) as workbook:
        bold = workbook.add_format({"bold": True, "font_size": 13})
        note_sheet = workbook.add_worksheet(notes_name[:31])
        for i, line in enumerate(notes):
            note_sheet.write(i, 0, line, bold if i == 0 else None)
        note_sheet.set_column(0, 0, 110)
        for name, table, decimals in sheets:
            table.write_excel(workbook=workbook, worksheet=name[:31], autofit=True, float_precision=decimals,
                              table_style="Table Style Light 9")
        if right_to_left:
            for sheet in workbook.worksheets():
                sheet.right_to_left()
    log(f"wrote {path.relative_to(ROOT)}")
    return path


# ---------------------------------------------------------------------------
# Messages.
# Messages.
# ---------------------------------------------------------------------------

_START = time.time()


def log(message: str) -> None:
    print(f"[{time.time() - _START:6.1f}s] {message}", flush=True)
