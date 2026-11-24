# I2A (IMF Air Emissions Account Converter, Achille Pegoue): how it works

Notes from reading `outils-fmi/i2a/I2A.py` (function `I2A`, lines 29 to 617) and running it headless with `scripts/outils_fmi.py` (`plages_i2a`, `oecd_i2a`, `i2a`). Written 2026-11-24. Manual: `User_Manual_AEA_Converter.docx`, version 0.0, March 2026 (bib keys `imf2026i2a`, `pegoue2026i2a`).

## Call

Workbook formula `Output_Source_Activity!B3`: `I2A(Inventory_2, Conversion_Matrix, CRT, NFR, Activity, Inventory!B1, B1, B2, OECD_Air, OECD_Sea, D1, H1)`. Positional names in the code: `Inventory, ECM, UNFCCC, EDGAR, Activity, Type_Inventory, IPCC_Level, Activity_Level, OECD_Air, OECD_Sea, Use_OECD, Unit`. The workbook passes the CRT table in the `UNFCCC` slot. For Tunisia: `Type_Inventory="UNFCCC"`, levels `None`, `Use_OECD="Use OECD International Transport Emissions"`, `Unit="Thousand tonnes CO2Eq"`.

## Inputs

- Inventory (sheet `Inventory_2`, from B5): `Info, Data_Source, IPCC_annex, CountryRegion, REF_AREA, CountryName, POLLUTANT, Source_Code, Source_Description, FossilType, years…`. Only `Info == "Most detailed Component"` and fossil rows are used. Unit: thousand tonnes CO2 eq (manual). Pollutants CO2, CH4, N2O, F-gases.
- The active sheets (`Conversion_Matrix`, `Conversion_Matrix_CRT`, `Activity`, `CRT`) hold demo data (Canada, random factors). Defaults are in `Conversion_Matrix_CRT_Def` (385 codes × 4 gases, NACE A*64-like columns + HH + bridging + LULUCF), `Activity_Def`, `CRT_Def`. `outils_fmi.plages_i2a` reads the `_Def` sheets.
- OECD: `I2A_Data/DSD_AIR_TRANSPORT.csv` and `DSD_MARITIME_TRANSPORT.csv` are in tonnes; `Tool_DSD_*.csv` (IMF imputations) are in kilotonnes, but the code divides by 10^6 as if tonnes. Only the Tunisian rows of the originals are committed (`_TUN.csv`); `oecd_i2a` applies the `Read_OECD` filter (annual, `_T` flights, resident sources; `ALL_VESSELS`). Maritime data for Tunisia start in 2019.

## Logic

1. Melt; group by pollutant, code, **description**, year, source (pandas drops rows with a missing description, line 257).
2. OECD air: `RES_DOM_OUT, RES_INT_FROM, RES_INT_TO, RES_INT_OUT` → `RES_ABROAD`; `RES_DOM_IN` kept; code = CRT row with Comment "Domestic Aviation" (1.A.3.a). Sea: `ALL_VESSELS`, code 1.A.3.d.
3. Matrix rows normalised to sum 1 (all-zero rows stay zero, so their emissions vanish); blank pollutant = all four gases. Inner merge on (pollutant, code).
4. Residence (lines 395-514), per activity: `RES_DOM_IN − inventory` (positive → activity and `OTHER` with opposite sign; negative → removed from activity, to `NRT-AIR`; CH4/N2O of 1.A.3.a all go to NRT-AIR since OECD has CO2 only). `RES_ABROAD` → activity and `NRA-AIR`. `ALL_VESSELS − inventory` positive → activity only (the `NRA-WATER` test on line 425 checks the Series index, not the codes); negative → `NRT-WATER`.
5. Totals: `AEA-TOTAL` = activities listed before it in the Activity table; `INV-TOTAL` = rows from AEA-TOTAL to INV-TOTAL, **without signs** (Sign column read on lines 521-524 but unused). Final groupby (line 559) again drops rows whose code has no description in the CRT table.

## Findings (for the author; worked around in pages 20-23)

- Default matrix has no factors for 3.D (agricultural soils) and 1.C: 1 481.8 kt CO2 eq lost for Tunisia in 2022.
- Codes in the matrix but not in `CRT_Def` (`2`, `3`, `4`, `5`, `6` without dot, all of `4.D.2.*`) are dropped silently; the inventory is mapped to codes present in both.
- `INV-TOTAL` exceeds the inventory by 2 × NRA-AIR + NRA-WATER (checked every year on page 23).
- `Tunisia_UNFCCC.xlsx` (provided) is in kt of each gas, writes N2O as `N20`, omits sub-categories (5.A, 5.B, 5.D under 5) and F-gases. Not used; the CRT `Data` sheet is the source.
- The Tunisian matrix must carry rows for 1.A.3.a and 1.A.3.d even without inventory emissions, or the OECD data are dropped.

## Layer comparison

The polars re-implementation on page 22 matches the tool to below 1e-11 kt on: default matrix without OECD, with OECD, and the Tunisian matrix by SUT branch with OECD (run year by year because keys vary).
