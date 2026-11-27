# IMF tools

This folder holds the tools of the Statistics Department of the International Monetary Fund (IMF) whose logic the pipeline follows. Their author is Achille Pegoue, senior economist in the Real Sector Division. They are published here with the agreement of their author and will be removed if the IMF requests it.

| Folder | Content |
|:--|:--|
| `pefa-converter/` | PEFA Converter: workbook `PEFA_Converter.xlsm`, xlwings function `PEFA_Converter.py` and manual (version 0.0, November 2024). It converts an energy balance in the format of the International Energy Agency (IEA) into physical supply and use tables for energy (PEFA). |
| `i2a/` | Air Emissions Account Converter (I2A): workbook `I2A.xlsm`, xlwings function `I2A.py` and manual (version 0.0, March 2026). It converts a greenhouse gas inventory into air emissions accounts (AEA). `I2A_Data/` holds only the rows for Tunisia of the OECD files `DSD_AIR_TRANSPORT.csv` and `DSD_MARITIME_TRANSPORT.csv` shipped with the tool (suffix `_TUN`); the other data files of the tool are not used. |

The pipeline calls the functions `EB2PEFA` and `I2A` unchanged through `scripts/imf_tools.py`, and re-implements each step explicitly to document it (scripts 13 and 22). Every piece of code taken or adapted from these tools cites the tool and its author.

## The "Total" column of the balance

The `Energy_Balance` range of the example workbook includes the "Total" column. The default concordance matrix has rows for this product in the four non-energy flows. With this column, `EB2PEFA` counts non-energy use twice, once by product and once through the total, so supply and use of the example differ (24,197.846 PJ and 24,386.288 PJ); without it they are equal (24,009.40 PJ). The tool is kept as it is, and the pipeline passes the `Energy_Balance` range without the "Total" column, for the example and for Tunisia (script 13).

## Points noted in the I2A tool

The tool is kept as it is. The pipeline works around the following points by preparing the inputs, and shows them with numbers (scripts 20 to 23).

- The active sheets of the workbook carry demonstration factors; the default tables are in the sheets `Conversion_Matrix_CRT_Def`, `Activity_Def` and `CRT_Def`.
- The default matrix has no factors for agricultural soils (3.D) nor for CO2 transport and storage (1.C). Their emissions are dropped without a message.
- The tool groups its rows by code and by category label (lines 257 and 559 of `I2A.py`). A category without a label, for example a code of the matrix missing from `CRT_Def` (4.D.2.c.ii), disappears.
- The total `INV-TOTAL` adds the bridging items without their sign, so it exceeds the inventory by twice the emissions of residents abroad.
- The positive gap of maritime transport is not recorded in the bridging item `NRA-WATER`, because the test on line 425 looks at the index of the activity table rather than its codes.
- The files `Tool_DSD_*.csv` (IMF imputations) are in kilotonnes, while the function treats OECD data as tonnes. The pipeline uses the original OECD files, in tonnes.
- The file `data/sources/ghg-inventory/Tunisia_UNFCCC.xlsx`, prepared for the tool, is in kilotonnes of each gas rather than CO2 equivalent, writes N2O as "N20" and omits sub-categories; the pipeline starts from the CRT tables.
