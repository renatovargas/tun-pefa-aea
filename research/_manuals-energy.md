# Energy accounts: what the manuals say (for agents)

Sources downloaded to `refs/manuals/` (gitignored, synced), with text extracts in `refs/manuals/text/`. Written 2026-11-27. Paragraph numbers are those of the source; cite with the bib keys in brackets.

## Lineage of the IMF PEFA Converter

The PEFA Converter manual (`imf2024pefa`) says the tool "builds on previous work undertaken by the UNSD in *Feasibility study on compiling energy accounts based on existing data sources*" and follows SEEA-CF, SEEA-Energy and the SEEA Technical Note on energy accounting. Its PEFA layout (supply table, use table, rows natural inputs / energy products by SIEC / residuals, columns ISIC sections + HH + Acc + RoW + Env) is that of SEEA-Energy chapter III and of the Eurostat PEFA tables A and B. The Indicator sheet follows the Eurostat key indicators (table D).

## SEEA Central Framework 2012 [`seea2014`] (`seea-cf-2012.pdf`, French `seea-cf-2012-fr.pdf`)

- Physical supply and use tables (PSUT), chapter III, section 3.3: supply table (rows: natural inputs, products, residuals; columns: industries, households, accumulation, rest of the world, environment) and use table with the same rows. Supply = use for each row (3.42ff.).
- Residuals and losses: 3.100 to 3.104 (four types of losses: during extraction, distribution, storage, transformation).
- Residence principle: accounts cover resident units, wherever they act (2.x and 3.x, as in the SNA).

## SEEA-Energy 2019 [`seeaenergy2019`] (`seea-energy-2019.pdf`)

- 2.14: energy from natural inputs flows from the environment into the economy, energy products circulate within it, energy residuals flow back to the environment.
- 2.15: conservation of energy. Extracted oil is a natural input; transformation gives products plus residuals (losses); end use returns the energy content as residual. This is why every use in EB2PEFA creates a residual row of equal size.
- 2.16 to 2.17: energy enters as natural input or imports; primary vs secondary products.
- 2.21: examples of energy residuals (flaring, distribution losses, storage leaks, transformation losses, heat from end use).
- 2.22: national economy = resident units; flows of international transport and tourism need adjustment (chapter III).
- Chapter III: physical supply and use tables for energy; classification of energy products follows SIEC (Standard International Energy Product Classification, from IRES).

## Eurostat PEFA Manual 2014 [`eurostat2014pefa`] (`eurostat-pefa-manual-2014.pdf`)

- 41 to 48: residence principle. PEFA record energy flows of resident units regardless of where they take place; energy statistics follow the territory principle; adjustments are shown in the bridge table (Table E). Natural resources on the territory are deemed owned by residents (48).
- Tables: A supply, B use, C emission-relevant use, D key indicators, E bridge.
- 101: seven key indicators (Statistics Netherlands pilot): 1 extraction of natural energy inputs; 2 domestic production of energy products; 3 intermediate consumption of energy products; 4 household consumption; 5 use of waste for energy; 6 net domestic energy use (NDEU); 7 total energy input/output.
- 103 to 106: NDEU = supply of energy residuals by industries and households + energy kept in products used for non-energy purposes (accumulation). It avoids double counting and is the accounts' counterpart of gross inland energy consumption (GIEC).
- 107, 109 to 111: NDEU is residence-based, GIEC territory-based. Bridge: NDEU − residents abroad + non-residents on the territory (± other) = GIEC. Differences come mainly from international transport.
- 127 and 4.2.1: adjustments relate to road, air and water transport (fuel bought abroad by residents, fuel bought on the territory by non-residents); bunkers in balances are territory-based.

The pipeline implements NDEU as defined in 103 (script 14). The IMF tool's Indicator sheet labels "NDEU" the end use for energy and non-energy purposes, which is close but not identical; the documents should say which definition they use.

## IRES 2018 [`ires2018`] (`ires-2018.pdf`)

International Recommendations for Energy Statistics. Defines SIEC (chapter 3), energy balance structure and conventions (chapter 8), units: 1 toe = 41.868 GJ. Energy balances follow the territory principle.

## SEEA Technical Note: Energy Accounting [`unsd2017energynote`] (draft dated 16 June 2016, file named April 2017)

Short introduction proposing a core set of energy accounts (PSUT, asset accounts, indicators) as a compilation starting point. Useful for didactic framing; cite as a draft.
