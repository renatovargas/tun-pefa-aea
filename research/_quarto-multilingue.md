# Quarto multilingual sites: state of the art and the choice made here

Researched 2026-11-24 with Quarto 1.10.18. The conclusions are applied in `STRUCTURE.md`.

## Upstream status

- Quarto has no native multilingual website or book support. The long-standing request is quarto-dev/quarto-cli issue #275 ("Multilingual websites / books"), still open. <https://github.com/quarto-dev/quarto-cli/issues/275>
- The main packaged solution is **babelquarto** (rOpenSci). It uses suffixed files (`index.qmd`, `index.es.qmd`) and renders a main-language site plus one subfolder per language, with a language switch button. It is an R package, so it does not fit this Python-only project. <https://docs.ropensci.org/babelquarto/>, <https://joelnitta.com/posts/2024-12-06_babelquarto/>
- The common R-free workaround uses **Quarto profiles**, one per language, each with its own navbar and output. Examples: Mario Angst (German and English, subfolders per language) <https://quarto-dev.marioangst.com/en/blog/posts/multi-language-quarto/>, serhii.net notes <https://serhii.net/dtb/240619-1425-quarto-multilanguage-website/>, and Swisstransplant's swtdata, which renders the main language first with `quarto render --profile de`. <https://github.com/Swisstransplant/swtdata>
- Arabic in Quarto HTML works with `dir: rtl` and `lang`. A worked example for Arabic spans in Quarto: <https://adamiturabi.github.io/quarto-arabic-mwe/>. W3C guidance on document direction: <https://www.w3.org/International/questions/qa-html-dir>

## Findings from testing here

- All three languages share one `output-dir` (`docs/`) and one `site_libs/`. Each profile lists only its own folder in `project.render`, so `quarto render en --profile en` counts as a full render of that profile, and a full render cleans `output-dir`. Observed: it deleted `docs/fr/`. The fix is `--no-clean` on the English and Arabic renders. `scripts/render.sh` renders French first (the only language that executes code), then `en/` and `ar/` with `--no-clean`. Use `--no-clean` for any render made while other languages are already in `docs/`.
- Quarto resolves project-level metadata values that match an existing path. With folders named `fr/`, `en/`, `ar/`, `lang: fr` in a profile became `../fr` ("Invalid 'lang' value"). Region codes (`fr-FR`, `en-US`, `ar-TN`) avoid the clash and also select the right CSL locale.
- `csl` in a profile is resolved relative to the project root, as expected.
- Typst with Quarto's native bibliography wrote `style: "\../../assets/apa-fr.csl"` and failed ("path must not contain a backslash"). `citeproc: true` in the Typst format sends citations through pandoc and avoids it; HTML and PDF then format citations identically.
- Typst picks text direction from `lang`; it needs an Arabic font. `mainfont: "Noto Naskh Arabic"` plus `font-paths` to `assets/fonts/` works on any machine.
- revealjs takes `rtl: true`; the theme adds Arabic font rules under `.reveal.rtl`.
- Quarto has no Arabic UI strings (abstract title, table prefix, callouts). The `language:` block in `_quarto-ar.yml` supplies them.
- APA CSL: `apa-fr.csl` is the CSL repository's `apa-fr-provost` (APA 7 in French, default locale changed to fr-FR); `apa-en.csl` and `apa-ar.csl` are the repository's `apa.csl` with `default-locale` set. Proper nouns in BibTeX titles need braces, since English APA applies sentence case.
