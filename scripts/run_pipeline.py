"""Run the pipeline, or some of its stages, in order.

Stages : extract  scripts 01 to 03. Read the source files in data/sources/.
         pefa     scripts 10 to 15. Energy accounts.
         aea      scripts 20 to 24. Air emissions accounts (needs extract and pefa).
         report   script 30. Tables and labels for the documents and the data explorer.
Run    : from the project root, with the stages to run. With no stage named, it runs all of them.
           uv run python scripts/run_pipeline.py
           uv run python scripts/run_pipeline.py pefa aea report
         The site is rendered afterwards with `bash scripts/render.sh`; rendering never runs the pipeline.

Each script runs in its own namespace and stops the run if one of its checks fails.

Exécute le pipeline, ou certaines de ses étapes, dans l'ordre. Sans argument, il exécute
toutes les étapes. Chaque script s'exécute dans son propre espace de noms et arrête le
traitement si l'un de ses contrôles échoue. Le site est rendu ensuite avec scripts/render.sh.
"""

import runpy
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent

PIPELINE = {
    "extract": ["extract/01_extract_energy_balances", "extract/02_extract_crt_inventory", "extract/03_extract_supply_use_tables"],
    "pefa": ["pefa/10_map_balance_to_iea_template", "pefa/11_build_activity_keys", "pefa/12_build_concordance_matrix",
             "pefa/13_compile_pefa_tables", "pefa/14_check_pefa_and_indicators", "pefa/15_export_pefa"],
    "aea": ["aea/20_prepare_ghg_inventory", "aea/21_build_conversion_matrix", "aea/22_compile_aea_tables",
            "aea/23_bridge_and_indicators", "aea/24_export_aea"],
    "report": ["report/30_publish_tables"],
}


def main(requested: list[str]) -> None:
    requested = requested or list(PIPELINE)
    unknown = set(requested) - set(PIPELINE)
    if unknown:
        sys.exit(f"Unknown stage: {', '.join(sorted(unknown))}. Stages: {', '.join(PIPELINE)}")

    # Stages always run in the order of the pipeline, whatever the order of the arguments.
    # Les étapes s'exécutent toujours dans l'ordre du pipeline, quel que soit l'ordre des arguments.
    sys.path.insert(0, str(SCRIPTS))
    start = time.time()
    for stage in [s for s in PIPELINE if s in requested]:
        for script in PIPELINE[stage]:
            print(f"\n== {script}", flush=True)
            runpy.run_path(str(SCRIPTS / f"{script}.py"), run_name="__main__")
    print(f"\nPipeline finished in {time.time() - start:.0f} s.")


if __name__ == "__main__":
    main(sys.argv[1:])
