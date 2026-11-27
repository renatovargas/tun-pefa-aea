"""Helpers for the documents, presentations and data explorer.

The documents never compute the accounts: they read the tables that the pipeline publishes
in data/outputs/tables/ and the labels in data/outputs/labels/, and format them. Every number
quoted in the text is an inline expression that reads these tables, so the text follows the
data whenever the pipeline runs again.

Usage in a document (the first chunk):
    import sys; sys.path.insert(0, "scripts/report")
    from doc_helpers import *
    setup("en")

Aides pour les documents, les présentations et l'explorateur de données. Les documents ne
calculent rien : ils lisent les tableaux publiés par le pipeline et les mettent en forme.
Chaque nombre cité dans le texte est une expression en ligne qui lit ces tableaux.
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import polars as pl

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "data" / "outputs" / "tables"
LABELS = ROOT / "data" / "outputs" / "labels"
REPO = "https://github.com/renatovargas/tun-pefa-aea"
LANG = "en"

# ---------------------------------------------------------------------------
# Colours. Each entity keeps its colour in every chart and language (reference palette
# of the visualisation guidance, validated for colour-vision deficiency).
# Couleurs. Chaque entité garde sa couleur dans tous les graphiques et toutes les langues.
# ---------------------------------------------------------------------------

BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#257de0", "#f47230", "#00b894", "#f2a600", "#ee7fac", "#008a17", "#6a4ce2", "#ec4647")
GREY, INK, INK2, GRID = "#8c8c8c", "#191919", "#666666", "#e6e6e6"
IMF_BLUE = "#204B92"

PRODUCT_COLORS = {"Natural gas": BLUE, "Oil": ORANGE, "Electricity": YELLOW, "Biofuels": GREEN, "Heat": RED,
                  "End-use of energy products for non-energy purposes": VIOLET}
GAS_COLORS = {"CO2": BLUE, "CH4": ORANGE, "N2O": AQUA, "F-gases": VIOLET}
SECTION_COLORS = {"A": GREEN, "B": ORANGE, "C": BLUE, "D": YELLOW, "E": AQUA, "F": MAGENTA, "H": VIOLET,
                  "Other": RED, "HH": "#5c5c5c"}
SECTOR_COLORS = {"1": BLUE, "2": ORANGE, "3": GREEN, "5": AQUA, "RES": VIOLET}
SEQUENTIAL = ["#cce3fd", "#9dc8f7", "#6aabf1", "#338ced", "#2370cd", "#1757ac", "#0e3d7e"]


# ---------------------------------------------------------------------------
# Language, labels and numbers.
# Langue, libellés et nombres.
# ---------------------------------------------------------------------------

def setup(lang: str) -> None:
    """Choose the language of labels and numbers, and set the chart style."""
    global LANG
    LANG = lang
    fm.fontManager.addfont(str(ROOT / "assets" / "fonts" / "NotoNaskhArabic.ttf"))
    matplotlib.rcParams.update({
        "font.family": ["DejaVu Sans", "Noto Naskh Arabic"], "font.size": 9,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titlesize": 10, "axes.titleweight": "bold",
        "axes.titlelocation": "right" if lang == "ar" else "left", "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
        "xtick.color": INK2, "ytick.color": INK2, "xtick.major.size": 0, "ytick.major.size": 0,
        "legend.frameon": False, "figure.dpi": 150, "savefig.bbox": "tight", "figure.figsize": (7, 3.6),
    })
    os.environ.setdefault("BROWSER_PATH", "/usr/bin/chromium")
    import plotly.io as pio
    pio.renderers.default = "notebook_connected" if output_format() in ("html", "revealjs") else "png"
    pio.defaults.default_scale = 2


def output_format() -> str:
    """Target format of the Quarto render under way ("html", "typst", "revealjs"...); "html" outside Quarto."""
    import json
    info = os.environ.get("QUARTO_EXECUTE_INFO")
    if not info or not Path(info).exists():
        return "html"
    return json.load(open(info))["format"]["identifier"].get("base-format", "html")


def read(name: str) -> pl.DataFrame:
    """A table published by scripts/report/30_publish_tables.py."""
    return pl.read_parquet(TABLES / f"{name}.parquet")


_label_cache: dict[tuple[str, str], dict[str, str]] = {}


def lab(dimension: str, lang: str | None = None) -> dict[str, str]:
    """Labels of a dimension (activities, pefa_rows, gases, crt_categories, imf_sections, terms...)."""
    lang = lang or LANG
    if (dimension, lang) not in _label_cache:
        table = pl.read_csv(LABELS / f"{dimension}.csv", infer_schema_length=0)
        _label_cache[(dimension, lang)] = dict(zip(table["code"], table[lang]))
    return _label_cache[(dimension, lang)]


def L(dimension: str, code: str) -> str:
    """One label; the code itself when no label exists."""
    return lab(dimension).get(code, code)


def activity(code: str) -> str:
    """Label of an activity, ISIC section or Sankey node."""
    for dimension in ("activities", "imf_sections"):
        if code in lab(dimension):
            return lab(dimension)[code]
    return lab("terms").get(f"node_{code}", code)


def num(x: float, digits: int = 0) -> str:
    """A number formatted for the language of the document (French: 1 234,5; English and Arabic: 1,234.5)."""
    if x is None:
        return "–"
    text = f"{x:,.{digits}f}"
    if LANG == "fr":
        text = text.replace(",", " ").replace(".", ",")
    return text


def pct(x: float, digits: int = 0) -> str:
    return num(100 * x, digits) + (" %" if LANG == "fr" else "%")


def pj(tj: float, digits: int = 0) -> str:
    """Terajoules shown as petajoules."""
    return num(tj / 1000, digits)


def mt(kt: float, digits: int = 1) -> str:
    """Kilotonnes shown as megatonnes."""
    return num(kt / 1000, digits)


def script_link(path: str) -> str:
    """Markdown link to a script on GitHub."""
    return f"[`{Path(path).name}`]({REPO}/blob/main/scripts/{path})"


# ---------------------------------------------------------------------------
# Tables. great_tables renders to HTML and, through Quarto, to Typst for the PDF.
# Tableaux. great_tables produit le HTML et, par Quarto, le Typst du PDF.
# ---------------------------------------------------------------------------

def gt(df: pl.DataFrame, decimals: int | dict[str, int] = 0, title: str | None = None, source: str | None = None,
       stub: str | None = None, groupname: str | None = None):
    """A table with the house style: light header rule, numbers formatted for the language."""
    from great_tables import GT, loc, style

    sep, dec = (" ", ",") if LANG == "fr" else (",", ".")
    table = GT(df, rowname_col=stub, groupname_col=groupname)
    numeric = [c for c, t in df.schema.items() if t.is_numeric() and c not in (stub, groupname)]
    if isinstance(decimals, int):
        decimals = {c: decimals for c in numeric}
    for column, d in decimals.items():
        if column in numeric:
            table = table.fmt_number(columns=column, decimals=d, sep_mark=sep, dec_mark=dec)
    if title:
        table = table.tab_header(title=title)
    if source:
        table = table.tab_source_note(source)
    size = "18px" if output_format() == "revealjs" else "11px"
    table = (table.tab_options(table_font_size=size, heading_title_font_size="13px", column_labels_font_weight="bold",
                               table_border_top_color=IMF_BLUE, column_labels_border_bottom_color=IMF_BLUE,
                               table_body_hlines_color=GRID, row_group_font_weight="bold", data_row_padding="3px")
             .sub_missing(missing_text="–")
             .tab_style(style=style.text(color=INK2), locations=loc.column_labels()))
    return table


# ---------------------------------------------------------------------------
# Charts.
# Graphiques.
# ---------------------------------------------------------------------------

def bar_labels(ax, bars, fmt=lambda v: num(v), inside: bool = False) -> None:
    """Direct labels at the end of horizontal bars."""
    for b in bars:
        w = b.get_width()
        ax.annotate(fmt(w), (w, b.get_y() + b.get_height() / 2), xytext=(3, 0), textcoords="offset points",
                    va="center", ha="left", fontsize=7.5, color=INK2)


def mirror(ax) -> None:
    """Right-to-left layout for Arabic charts: category labels on the right."""
    if LANG == "ar":
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")
        ax.spines["left"].set_visible(False)
        # Leave room for the value labels, which would otherwise touch the category labels.
        # Laisser de la place aux étiquettes de valeur, qui toucheraient sinon les libellés.
        low, high = ax.get_xlim()
        ax.set_xlim(low, high + 0.12 * (high - low))


def sankey(nodes: list[str], colors: list[str], links: list[tuple[int, int, float, str]], height: int = 420, unit: str = "PJ"):
    """A plotly Sankey diagram: interactive on the website, an image in the PDF."""
    import plotly.graph_objects as go

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=nodes, color=colors, pad=14, thickness=14, line=dict(width=0)),
        link=dict(source=[s for s, _, _, _ in links], target=[t for _, t, _, _ in links], value=[v for _, _, v, _ in links],
                  color=[c for _, _, _, c in links], hovertemplate="%{source.label} → %{target.label}: %{value:,.1f} " + unit + "<extra></extra>"),
    ))
    fig.update_layout(height=height, width=820, margin=dict(l=10, r=10, t=10, b=10),
                      font=dict(family="DejaVu Sans, Noto Naskh Arabic, sans-serif", size=11, color=INK))
    return fig


def fade(hex_color: str, alpha: float = 0.45) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def lookup(name: str) -> pl.DataFrame:
    """A hand-edited lookup of data/lookups/ (mappings with their rationale)."""
    return pl.read_csv(ROOT / "data" / "lookups" / f"{name}.csv", infer_schema_length=0)


def check(script: str, name: str) -> dict:
    """One row of the checks table as a dictionary."""
    return read("checks").filter(pl.col("script") == script, pl.col("check") == name).row(0, named=True)
