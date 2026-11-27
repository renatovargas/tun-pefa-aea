# Air emissions accounts: what the manuals say (for agents)

Sources in `refs/manuals/` (gitignored, synced), text in `refs/manuals/text/`. Written 2026-11-27. Paragraph numbers are those of the source.

## Lineage of the IMF I2A tool

The I2A manual (`imf2026i2a`, version 0.0, March 2026) says the tool converts inventories prepared with IPCC guidelines into AEA by ISIC activity plus households, and "incorporates good practices delineated in the SEEA-CF, the SEEA Technical Note: air emissions accounting, and the Eurostat Manual for air emissions accounts". Its conversion matrix plays the role of Annex 1 of the Eurostat manual (CRF/NFR to NACE correspondence); its residence adjustment uses OECD estimates of air and maritime transport emissions; its bridge rows (NRA-*, NRT-*, OTHER) copy the bridging items of the Eurostat questionnaire (Table 8).

## Eurostat Manual for Air Emissions Accounts, 2015 [`eurostat2015aea`]

- 9 and 12: differences between AEA and inventories are made explicit in bridging items; Annex 1 is the CRF/NFR to NACE correspondence; Annex 3 guides the bridging items.
- 32 to 38: AEA follow the residence principle of national accounts (resident = centre of economic interest on the economic territory). Emissions of resident units are recorded wherever they occur (35: emissions of a resident airline flying between two foreign cities belong to its home country's AEA). Inventories follow a territory principle (37). Small economies have larger gaps (36).
- 53, 69, 75, 82: CO2 from biomass combustion is a memo item in inventories and is reported separately in AEA, outside the CO2 totals.
- 113: rows of the questionnaire: industries (NACE A*64), households (transport, heating, other), bridging items.
- 114: SEEA-CF recommends a combined physical supply and use table for emissions; Eurostat collects only the supply table.
- 227 to 230 and Table 8: bridging items. AEA total (industries + households) − residents abroad + non-residents on the territory ± other = inventory total excluding LULUCF. Two causes: residence vs territory, and the scope of inventory totals (international aviation and navigation are memo items in UNFCCC totals).
- 269: LULUCF is excluded from inventory totals as compared and from AEA.
- 270: landfill emissions go to whoever operates the sites (waste industries, or municipalities); check the supply table of the national accounts.
- 271ff.: using energy statistics or energy accounts to allocate combustion emissions (energy-based approach).

## SEEA Technical Note: Air Emissions Accounts [`unsd2018airnote`] (draft of 13 July)

Short didactic note; figure contrasting territory and residence principles (around line 569 of the text extract); steps for adjusting territory-based data.

## SEEA Central Framework [`seea2014`]

Emissions are residual flows in the physical supply and use tables (chapter III, 3.238ff. for air emissions accounts): supplied by industries and households, received by the environment.

## IPCC 2006 Guidelines [`ipcc2006`]

Inventories by sector (1 Energy, 2 IPPU, 3 AFOLU in CRT as 3 Agriculture and 4 LULUCF, 5 Waste, 6 Other). Memo items 1.D: international bunkers (aviation 1.D.1.a, navigation 1.D.1.b), multilateral operations, CO2 from biomass. Tunisia reports in CRT format with AR5 GWP (CH4 28, N2O 265).
