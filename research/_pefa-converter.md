# PEFA Converter (IMF, Achille Pegoue): how EB2PEFA works

Notes from reading `outils-fmi/pefa-converter/PEFA_Converter.py` (function `EB2PEFA`, lines 27 to 789; `EE_EB2PEFA` below it is an older copy, unused) and running it headless with `scripts/outils_fmi.py`. Written 2026-11-24.

## Inputs (named ranges, rebuilt by `outils_fmi.plages_classeur`)

- `Energy_Balance`: IEA layout, **TJ** (sheet header "UNIT: TJ"), IEA signs (exports, bunkers, transformation inputs, own use, losses negative; stock changes positive = draw). 95 flows in a fixed order (`Energy_Balance_Template` column A); the code finds Level1/Level2 blocks by walking that order, so every template row must be present. Products across (63 + Total).
- `Concordance_Matrix` (B1, 12 columns): `EB_Flow_Level1, EB_Flow_Level2, EB_Flow, EB_Product, Allocation Factor, PEFA_Target_Product, PEFA_Target_Activity, Comment, PEFA_Target_Product_Level1, PEFA_Target_Product_Level2, PEFA_Quadrant, EB_Category`. Activities are ISIC sections A, B, C, D, E, F, H, Other, HH plus Acc and RoW. Factors are normalised to sum 1 per (flow, product, target product, quadrant).
- `EB_Bridging_Items`: residence adjustments by PEFA product (PJ), empty in the sample.
- `EB_Product` (Classification!U:W): EB product → PEFA product (Coal, Oil, Natural gas, Biofuels, Waste, Electricity, Heat, ...) and group (Renewable, Waste). Heat is in the Renewable group.
- `Filter` (PEFA!B1): default `'  ALL (Statistical difference exclusive)'`.

## Logic

1. Melt the balance; attach `EB_Category` from the CM.
2. Production rows: supply of the energy product by the producing activity; duplicated as use of natural inputs (or renewable inputs) by that activity and supply of natural inputs by `Env`.
3. Transfers: supply by C, duplicated as residual use and Acc supply.
4. Statistical differences: factors negated; appended once at the end with activity "Statistical differences" (Use quadrant).
5. Downstream flows (transformation, own use, losses, final consumption, bunkers): use of energy products; transformation outputs become supply. Each is duplicated as residual supply by the activity (residuals from losses for transformation and losses, from end-use for own use, final consumption and bunkers, from non-energy use) and residual use by `Env` (`Acc` for non-energy).
6. Output: long table by PEFA product levels, activity, quadrant; `PEFA_Energy` = TJ × factor / 1000, i.e. **PJ**.

## Findings

- The plan's sample imbalance (supply 24 197.846 PJ, use 24 386.288 PJ) comes from the default CM, which has rows for the `Total` column on the four non-energy flows. Non-energy use is counted twice. Dropping the `Total` column from the balance range gives supply = use = 24 009.40 PJ. Report to the author.
- With filter `'  o/w Statistical differences'`, the statistical difference is counted twice (once in the main table, once in the appended block).
- Road transport goes entirely to H; no household split. Solar thermal production goes to D.
- pandas must be < 3 (`fillna('Zachille_')` on a float column fails under pandas 3).
