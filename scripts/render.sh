#!/usr/bin/env bash
# Render the whole site in the three languages. Rendering never runs the pipeline:
# run `uv run python scripts/run_pipeline.py` first when the data or the lookups change.
# English renders first (it also renders the root language picker) and cleans docs/;
# French and Arabic then render into the same docs/ with --no-clean, which is essential,
# since a full render of one profile would otherwise delete the other languages.
# Quarto needs a Chromium browser to draw Mermaid diagrams in PDFs, and Plotly needs it
# for the static images of the Sankey diagrams.
set -euo pipefail
cd "$(dirname "$0")/.."
export QUARTO_CHROMIUM="${QUARTO_CHROMIUM:-$(command -v chromium || command -v google-chrome || true)}"
export BROWSER_PATH="${BROWSER_PATH:-$QUARTO_CHROMIUM}"

uv run python scripts/check_translations.py || echo "Warning: translations are incomplete (see above)."
uv run quarto render --profile en
uv run quarto render fr --profile fr --no-clean
uv run quarto render ar --profile ar --no-clean
