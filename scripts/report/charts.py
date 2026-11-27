"""Charts shared by the documents, the presentations and the three languages.

Each function reads published tables, draws one chart and takes every word it prints from
the label tables, so the same call gives the English, French or Arabic chart. Call
doc_helpers.setup(lang) first.

Graphiques partagés par les documents, les présentations et les trois langues. Chaque
fonction lit les tableaux publiés et prend tous ses mots dans les tables de libellés.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import polars as pl

import doc_helpers as h
from doc_helpers import (GAS_COLORS, GREY, GRID, IMF_BLUE, INK2, ORANGE, PRODUCT_COLORS, SECTION_COLORS, SECTOR_COLORS,
                         SEQUENTIAL, L, activity, bar_labels, fade, lab, mirror, num, read, sankey)

NON_ENERGY = "End-use of energy products for non-energy purposes"
END_USE = "End-use of energy products by SIEC class:"
GASES = ["CO2", "CH4", "N2O", "F-gases"]


def T(key: str) -> str:
    return L("terms", key)


def short(text: str, n: int = 40) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def _acts() -> list[str]:
    return [c for c in lab("activities") if c not in ("ROW", "ACC", "ENV", "STATDIFF")]


def _years(table: pl.DataFrame) -> list[int]:
    return sorted(table["year"].unique().to_list())


def _done(fig):
    """Lay out and close the figure, so that a notebook shows it once, as the value of the cell."""
    fig.tight_layout()
    plt.close(fig)
    return fig


def _hbar_finish(ax, xlabel: str) -> None:
    ax.set_xlabel(xlabel)
    ax.grid(axis="y", visible=False)
    mirror(ax)


# ---------------------------------------------------------------------------
# Energy accounts.
# Comptes de l'énergie.
# ---------------------------------------------------------------------------

def energy_supply(figsize=(7, 3.2)):
    """Supply of energy products by origin, all years (PJ)."""
    s = read("pefa_sankey").filter(pl.col("stage") == "supply")
    years = _years(s)
    fig, ax = plt.subplots(figsize=figsize)
    for source, color, key in [("PROD", IMF_BLUE, "chart_domestic_production"), ("IMP", ORANGE, "chart_imports")]:
        values = [s.filter(pl.col("year") == y, pl.col("source") == source)["tj"].sum() / 1000 for y in years]
        ax.plot(years, values, color=color, linewidth=2, marker="o", markersize=5, label=T(key))
        ax.annotate(num(values[-1]), (years[-1], values[-1]), xytext=(6, 0), textcoords="offset points", va="center", fontsize=8, color=INK2)
    ax.set_ylabel(T("chart_pj"))
    ax.set_ylim(0, None)
    ax.legend(loc="lower left", ncols=2)
    ax.grid(axis="x", visible=False)
    return _done(fig)


def activity_keys(year: int, figsize=(7.5, 4.2)):
    """Shares of the road transport and tertiary keys, one year."""
    keys = read("pefa_activity_keys").filter(pl.col("method") == "key", pl.col("year") == year)
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    for ax, flow, key in [(axes[0], "Road", "chart_road_key"), (axes[1], "Commercial and public services", "chart_tertiary_key")]:
        d = keys.filter(pl.col("iea_flow") == flow).sort("factor", descending=True).head(10).sort("factor")
        bars = ax.barh([short(activity(c), 32) for c in d["activity"]], d["factor"] * 100, color=IMF_BLUE, height=0.6)
        bar_labels(ax, bars, fmt=lambda v: num(v, 0))
        ax.set_title(T(key), fontsize=9)
        _hbar_finish(ax, T("chart_percent"))
    return _done(fig)


def implied_prices(year: int, figsize=(7, 4.6)):
    """Implied price of energy by industry, one year (TND per GJ), without refining and electricity."""
    d = (read("pefa_plausibility").filter(pl.col("year") == year, pl.col("energy_tj") > 0, ~pl.col("activity").is_in(["19", "35"]))
         .sort("implied_price_tnd_per_gj"))
    fig, ax = plt.subplots(figsize=figsize)
    names = [short(activity(c)) for c in d["activity"]]
    ax.hlines(names, 0, d["implied_price_tnd_per_gj"], color=GRID, linewidth=1)
    ax.scatter(d["implied_price_tnd_per_gj"], names, color=IMF_BLUE, s=28, zorder=3)
    _hbar_finish(ax, T("chart_tnd_per_gj"))
    return _done(fig)


def energy_sankey(year: int, height: int = 460):
    """Energy products by origin and use, one year (PJ)."""
    flows = read("pefa_sankey").filter(pl.col("year") == year, pl.col("tj") > 0)
    order = ["PROD", "IMP"] + [p for p in PRODUCT_COLORS if p in set(flows["target"])] + \
            [n for n in ["TRANSF", "HH", "A", "B", "C", "D", "E", "F", "H", "Other", "EXP", "STATDIFF"] if n in set(flows["target"])]
    idx = {n: i for i, n in enumerate(order)}
    names = [lab("terms").get(f"node_{n}") or (L("pefa_rows", n) if n in PRODUCT_COLORS else activity(n)) for n in order]
    colors = [IMF_BLUE if n == "PROD" else GREY if n in ("IMP", "EXP", "TRANSF", "STATDIFF") else PRODUCT_COLORS.get(n) or SECTION_COLORS.get(n, GREY)
              for n in order]
    links = [(idx[s], idx[t], v / 1000, fade(PRODUCT_COLORS.get(t if s in ("PROD", "IMP") else s, GREY)))
             for s, t, v in flows.select("source", "target", "tj").iter_rows() if s in idx and t in idx]
    return sankey(names, colors, links, height=height, unit=T("chart_pj"))


def energy_users(year: int, n: int = 12, figsize=(7.2, 4.6)):
    """End use of energy for energy purposes by user and product, one year (PJ)."""
    acts = _acts()
    use = (read("pefa_supply_use").filter(pl.col("year") == year, pl.col("quadrant") == "Use", pl.col("level2") == END_USE,
                                          pl.col("product") != NON_ENERGY, pl.col("activity").is_in(acts))
           .group_by("activity", "product").agg(pl.col("tj").sum()))
    top = use.group_by("activity").agg(pl.col("tj").sum()).sort("tj", descending=True).head(n).sort("tj")["activity"].to_list()
    fig, ax = plt.subplots(figsize=figsize)
    left = [0.0] * len(top)
    for product in [p for p in PRODUCT_COLORS if p in set(use["product"])]:
        values = [use.filter(pl.col("activity") == a, pl.col("product") == product)["tj"].sum() / 1000 for a in top]
        ax.barh([short(activity(a)) for a in top], values, left=left, color=PRODUCT_COLORS[product], height=0.62,
                label=L("pefa_rows", product), edgecolor="white", linewidth=0.8)
        left = [l + v for l, v in zip(left, values)]
    for i, total in enumerate(left):
        ax.annotate(num(total, 1), (total, i), xytext=(3, 0), textcoords="offset points", va="center", fontsize=7.5, color=INK2)
    ax.legend(loc="lower right", fontsize=8)
    _hbar_finish(ax, T("chart_pj"))
    return _done(fig)


def energy_intensity(year: int, figsize=(7, 5)):
    """End use of energy per million TND of value added by industry, one year."""
    d = (read("pefa_indicators").filter(pl.col("year") == year, pl.col("activity") != "HH", pl.col("value_added_mtnd") > 0)
         .sort("intensity_value_added"))
    fig, ax = plt.subplots(figsize=figsize)
    bars = ax.barh([short(activity(c), 42) for c in d["activity"]], d["intensity_value_added"], color=IMF_BLUE, height=0.6)
    bar_labels(ax, bars, fmt=lambda v: num(v, 1))
    _hbar_finish(ax, T("chart_tj_per_mtnd"))
    return _done(fig)


def ndeu_vs_gic(figsize=(7, 3)):
    """Net domestic energy use of the accounts and gross inland consumption of the balance (PJ)."""
    ind, bal = read("pefa_indicators"), read("energy_balance")
    years = _years(ind)
    ndeu = [ind.filter(pl.col("year") == y)["net_domestic_energy_use"].sum() / 1000 for y in years]
    gic = [bal.filter(pl.col("year") == y, pl.col("flow") == "GIC", pl.col("product") == "TOTAL")["tj"].sum() / 1000 for y in years]
    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(years, ndeu, color=IMF_BLUE, linewidth=2, marker="o", markersize=5, label=T("chart_ndeu"))
    ax.plot(years, gic, color=ORANGE, linewidth=2, marker="o", markersize=5, label=T("chart_gic"))
    ax.set_ylabel(T("chart_pj"))
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(axis="x", visible=False)
    return _done(fig)


# ---------------------------------------------------------------------------
# Air emissions accounts.
# Comptes des émissions atmosphériques.
# ---------------------------------------------------------------------------

def emissions_by_gas(figsize=(7, 3.4)):
    """Greenhouse gas emissions of resident units by gas, all years (Mt CO2 eq)."""
    aea = read("aea_emissions")
    years = _years(aea)
    d = aea.filter(pl.col("activity").is_in(_acts()), pl.col("gas").is_in(GASES)).group_by("year", "gas").agg(pl.col("kt_co2_eq").sum())
    fig, ax = plt.subplots(figsize=figsize)
    bottom = [0.0] * len(years)
    for g in GASES:
        values = [d.filter(pl.col("year") == y, pl.col("gas") == g)["kt_co2_eq"].sum() / 1000 for y in years]
        ax.bar(years, values, bottom=bottom, color=GAS_COLORS[g], label=L("gases", g), width=0.65, edgecolor="white", linewidth=0.8)
        bottom = [x + v for x, v in zip(bottom, values)]
    ax.set_ylabel(T("chart_mt_co2"))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncols=4, fontsize=8)
    ax.grid(axis="x", visible=False)
    return _done(fig)


def emissions_sankey(year: int, height: int = 520):
    """Emissions by inventory category and section of the emitter, one year (kt CO2 eq)."""
    f = read("aea_sankey").filter(pl.col("year") == year, pl.col("kt_co2_eq") > 0)
    cats = sorted(f["category"].unique().to_list())
    secs = [s for s in ["A", "B", "C", "D", "E", "F", "H", "Other", "HH"] if s in set(f["section"])]
    idx = {n: i for i, n in enumerate(cats + secs)}
    names = [f"{c} {L('crt_categories', c)}" if c != "RES" else T("chart_residents_abroad") for c in cats] + [activity(s) for s in secs]
    sector = lambda c: SECTOR_COLORS.get("RES" if c == "RES" else c[0], GREY)
    colors = [sector(c) for c in cats] + [SECTION_COLORS[s] for s in secs]
    links = [(idx[c], idx[s], v, fade(sector(c))) for c, s, v in f.select("category", "section", "kt_co2_eq").iter_rows()]
    return sankey(names, colors, links, height=height, unit=T("chart_kt_co2"))


def emitters(year: int, n: int = 15, figsize=(7.2, 5)):
    """Greenhouse gas emissions by activity and gas, one year (kt CO2 eq)."""
    d = (read("aea_emissions").filter(pl.col("year") == year, pl.col("activity").is_in(_acts()), pl.col("gas").is_in(GASES))
         .group_by("activity", "gas").agg(pl.col("kt_co2_eq").sum()))
    top = d.group_by("activity").agg(pl.col("kt_co2_eq").sum()).sort("kt_co2_eq", descending=True).head(n).sort("kt_co2_eq")["activity"].to_list()
    fig, ax = plt.subplots(figsize=figsize)
    left = [0.0] * len(top)
    for g in GASES:
        values = [d.filter(pl.col("activity") == a, pl.col("gas") == g)["kt_co2_eq"].sum() for a in top]
        ax.barh([short(activity(a), 42) for a in top], values, left=left, color=GAS_COLORS[g], height=0.62, label=L("gases", g),
                edgecolor="white", linewidth=0.8)
        left = [l + v for l, v in zip(left, values)]
    for i, total in enumerate(left):
        ax.annotate(num(total, 0), (total, i), xytext=(3, 0), textcoords="offset points", va="center", fontsize=7.5, color=INK2)
    ax.legend(loc="lower right", fontsize=8)
    _hbar_finish(ax, T("chart_kt_co2"))
    return _done(fig)


def emission_intensity(year: int, figsize=(7, 5)):
    """Greenhouse gas emissions per million TND of value added by industry, one year."""
    d = (read("aea_indicators").filter(pl.col("year") == year, pl.col("activity") != "HH", pl.col("value_added_mtnd") > 0)
         .sort("ghg_intensity_value_added"))
    fig, ax = plt.subplots(figsize=figsize)
    bars = ax.barh([short(activity(c), 42) for c in d["activity"]], d["ghg_intensity_value_added"], color=IMF_BLUE, height=0.6)
    bar_labels(ax, bars, fmt=lambda v: num(v, 0))
    _hbar_finish(ax, T("chart_t_per_mtnd"))
    return _done(fig)


def implied_factors(year: int, figsize=(7, 5)):
    """Implied CO2 factor of combustion by activity, with the range of the inventory by fuel (t CO2 per TJ)."""
    fi = read("aea_implied_factors_inventory").filter(pl.col("year") == year)
    d = (read("aea_implied_factors_accounts").filter(pl.col("year") == year, pl.col("t_co2_per_tj").is_not_null(), pl.col("fossil_tj") > 100)
         .sort("t_co2_per_tj"))
    fig, ax = plt.subplots(figsize=figsize)
    names = [short(activity(c), 42) for c in d["activity"]]
    ax.axvspan(fi["t_co2_per_tj"].min(), fi["t_co2_per_tj"].max(), color=SEQUENTIAL[0], zorder=0)
    ax.scatter(d["t_co2_per_tj"], names, color=IMF_BLUE, s=26, zorder=3)
    _hbar_finish(ax, T("chart_t_per_tj"))
    return _done(fig)
