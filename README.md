# Tunisia: energy and air emissions accounts

Physical energy flow accounts (PEFA) and air emissions accounts (AEA) for Tunisia, 2015 to 2022, following the System of Environmental-Economic Accounting (SEEA). The repository holds a reproducible Python pipeline that compiles the accounts from the national sources, and a trilingual Quarto website (English, French, Arabic) with methods documents, presentations and a data explorer.

Website: <https://renatovargas.github.io/tun-pefa-aea/>

## Quick start

```bash
uv sync                                   # install Python and the dependencies
uv run python scripts/run_pipeline.py     # compile the accounts (about 20 seconds)
bash scripts/render.sh                    # render the website into docs/
```

Rendering needs [Quarto](https://quarto.org) and a Chromium or Chrome browser (for Mermaid diagrams and the static images of Sankey diagrams in PDFs). Rendering never runs the pipeline: documents only read its outputs, so wording can change without recomputing anything.

## Layout

```
data/sources/      source files as received (energy balances, CRT inventory, supply and use tables)
data/lookups/      hand-edited correspondences and labels (English, French, Arabic), each rule with its reason
data/intermediate/ working tables of the pipeline (Parquet)
data/outputs/
  accounts/<lang>/ Excel workbooks of the accounts in en, fr and ar
  tables/          tidy tables read by the documents and the data explorer (Parquet and CSV, codes only)
  labels/          labels of every code in three languages
  checks/          results of the consistency checks of each script
scripts/
  run_pipeline.py  orchestrator: stages extract, pefa, aea, report
  common.py        shared paths, constants, lookups, checks and Excel output
  imf_tools.py     calls the IMF tools (PEFA Converter, I2A) without Excel, as a reference
  extract/         01 to 03: read the sources
  pefa/            10 to 15: energy accounts
  aea/             20 to 24: air emissions accounts
  report/          30: tables and labels for the site; doc_helpers.py and charts.py for the documents
imf-tools/         the IMF PEFA Converter and I2A tools, with their manuals
en/ fr/ ar/        the website in three mirrored trees (documents, slides, explorer, downloads)
research/          notes on the reference manuals
```

Code comments are in English, followed by their French translation. Each numbered script states what it reads, what it does and what it writes, and stops if one of its checks fails.

## IMF tools

The compilation follows the PEFA Converter and the Air Emissions Account Converter (I2A) of the IMF Statistics Department, by Achille Pegoue. The pipeline re-implements each of their rules explicitly and calls the original functions unchanged to confirm that both give the same numbers. See `imf-tools/README.md`.

## Maintainer note

Some reference material is kept outside git and synchronised privately by the maintainer; see `_remote.md`. Nothing in it is needed to run the pipeline or render the site.
