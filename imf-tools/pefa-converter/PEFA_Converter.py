#
# Energy Accounts Tool
#
#   For queries on this macro, please contact
#
#       Achille Pegoue(apegoue@imf.org)
#       Senior economist, Statistics Department
#       Real Sector Division
#       International Monetary Fund (IMF)
#
#   Version 0.0 - November 2026


import xlwings as xw
import numpy as np
import pandas as pd
import os
#import plotly
#import plotly.plotly as py
import plotly.graph_objects as go
import random
from random import randint
import math 
import re


@xw.func
def EB2PEFA(EB, CM, EB_Bridging_Items, EB_Product, Filter):
    # EB: Energy Balance
    # CM: Concordance matrix
    # EB_Bridging_Items: Briding item (Flaring)

    # Converting the the Flow x product matrix EB into
    # 5-dimension matrix: Flow_Level1  Flow_Level2    Flow   Product    Energy
    # folder0 = os.path.dirname(os.path.realpath(__file__))

    EB = pd.DataFrame(EB)
    
    # Heading
    EB_Heading = EB.loc[0]
    # EB_Heading.insert(0,"Flow")
    EB_Heading[0] = 'EB_Flow'
    EB_Heading0 = EB_Heading.copy()

    # remove special character
    # final = [re.sub(r"[^a-zA-Z0-9]+", ' ', k) for k in a.split("\n")]

    for i in range(len(EB_Heading0)):
        # EB_Heading0[i] = ''.join(letter for letter in EB_Heading0[i] if letter.isalnum() )
        EB_Heading0[i] = ''.join(map(lambda letter: letter if letter.isalnum() else '_', EB_Heading0[i]))

    # EB_Heading =pd.DataFrame({'Heading_Original': EB_Heading,
    #                         'Heading_Modig': EB_Heading0})
    EB.columns = EB_Heading
    # remove missing flow
    EB = EB[EB['EB_Flow'].notna()]

    EB = EB.loc[1:].reset_index(drop=True)

    EB['EB_Flow_Level3'] = None

    # group of product
    EB_Product = pd.DataFrame(EB_Product)

    EB_Product.columns = EB_Product.loc[0]
    EB_Product = EB_Product.loc[1:].reset_index(drop=True)
    EB_Product_Renewable = list(EB_Product.loc[EB_Product['Group'].isin(['Renewable']), 'EB_Product'])
    EB_Product_Waste = list(EB_Product.loc[EB_Product['Group'].isin(['Waste']), 'EB_Product'])

    # Flow
    # Level 1

    Level = pd.DataFrame({'EB_Flow_Level1': ["Total primary energy supply",
                                             'Other flows',
                                             "Transformation processes",
                                             "Energy industry own use",
                                             "Losses",
                                             "Total final consumption",
                                             "Total final consumption",
                                             "Total final consumption",
                                             "Total final consumption",
                                             "Electricity output (GWh)",
                                             "Heat output"],

                          'EB_Flow_Level2': [None,
                                             None,
                                             None,
                                             None,
                                             None,
                                             "Industry",
                                             "Transport",
                                             "Other",
                                             "Non-energy use",
                                             None,
                                             None]
                          })

    EB_Flow_Change_Sign = ['Exports', 'Stock changes']

    i_EB = 0
    i_Flow_Level1 = 0

    # Total primary energy supply
    Len_EB = len(EB.index) - 1
    while ((EB.at[i_EB, "EB_Flow"] != Level.at[i_Flow_Level1, 'EB_Flow_Level1']) &
           (i_EB < Len_EB)):
        i_EB += 1

    # Total primary energy supply is found
    Flow_Matrix = pd.DataFrame(EB["EB_Flow"][0:i_EB])
    Flow_Matrix['EB_Flow_Level1'] = Level.at[i_Flow_Level1, 'EB_Flow_Level1']
    Flow_Matrix['EB_Flow_Level2'] = Level.at[i_Flow_Level1, 'EB_Flow_Level2']
    # Add empty row

    Flow_Matrix.loc[len(Flow_Matrix.index)] = None

    # Deal with Transfer and statistical discrepancy
    i_Flow_Level1 += 1
    i_EB += 1
    i_EB0 = i_EB
    while ((EB.at[i_EB, "EB_Flow"] != Level.at[i_Flow_Level1 + 1, 'EB_Flow_Level1']) &
           (i_EB < Len_EB)):
        i_EB += 1

    if i_EB != i_EB0:
        Flow_Matrix0 = pd.DataFrame(EB["EB_Flow"][i_EB0:i_EB])
        Flow_Matrix0['EB_Flow_Level1'] = Level.at[i_Flow_Level1, 'EB_Flow_Level1']
        Flow_Matrix0['EB_Flow_Level2'] = Level.at[i_Flow_Level1, 'EB_Flow_Level2']
        Flow_Matrix = pd.concat([Flow_Matrix, Flow_Matrix0], axis=0, ignore_index=True)

        # Add empty row
        # Flow_Matrix.loc[len(Flow_Matrix.index)]=None
        # i_EB += 1

    for i_Flow_Level1 in range(2, len(Level.index) - 1):

        if Level.at[i_Flow_Level1, 'EB_Flow_Level2']:

            # Col_Level = 'EB_Flow_Level2'

            if Level.at[i_Flow_Level1 - 1, 'EB_Flow_Level1'] != Level.at[i_Flow_Level1, 'EB_Flow_Level1']:
                # Add empty row for Total final consumption
                Flow_Matrix.loc[len(Flow_Matrix.index)] = [None] * 3
                i_EB += 1

            # Check if the corresponding category is for level 2
            # if EB.at[i_EB,"Flow"] != Level.at[i_Flow_Level1, Col_Level]:
            # return(Level.at[i_Flow_Level1, Col_Level])
            # continue

            i_EB += 1
            i_EB0 = i_EB

            if i_Flow_Level1 == len(Level.index) - 1:  # last category for level
                while i_EB < Len_EB:
                    i_EB += 1

            else:

                while ((EB.at[i_EB, "EB_Flow"] != Level.at[i_Flow_Level1 + 1, 'EB_Flow_Level2']) &
                       (EB.at[i_EB, "EB_Flow"] != Level.at[i_Flow_Level1 + 1, 'EB_Flow_Level1']) &
                       (i_EB < Len_EB)):
                    i_EB += 1

            # Add empty row
            Flow_Matrix.loc[len(Flow_Matrix.index)] = None

            Flow_Matrix0 = pd.DataFrame(EB["EB_Flow"][i_EB0:i_EB])
            Flow_Matrix0['EB_Flow_Level1'] = Level.at[i_Flow_Level1, 'EB_Flow_Level1']
            Flow_Matrix0['EB_Flow_Level2'] = Level.at[i_Flow_Level1, 'EB_Flow_Level2']
            Flow_Matrix = pd.concat([Flow_Matrix, Flow_Matrix0], axis=0, ignore_index=True)


        else:

            if i_EB < Len_EB:
                Col_Level = 'EB_Flow_Level1'

                if Level.at[i_Flow_Level1, 'EB_Flow_Level1'] == 'Losses':
                    Flow_Matrix0 = pd.DataFrame({"EB_Flow": ['Losses']})
                    Flow_Matrix0['EB_Flow_Level1'] = Level.at[i_Flow_Level1, 'EB_Flow_Level1']
                    Flow_Matrix0['EB_Flow_Level2'] = Level.at[i_Flow_Level1, 'EB_Flow_Level2']
                    Flow_Matrix = pd.concat([Flow_Matrix, Flow_Matrix0], axis=0, ignore_index=True)
                    i_EB += 1

                else:
                    if Level.at[i_Flow_Level1 - 1, 'EB_Flow_Level1'] != Level.at[i_Flow_Level1, 'EB_Flow_Level1']:
                        # Add empty row for Total final consumption
                        Flow_Matrix.loc[len(Flow_Matrix.index)] = None
                        i_EB += 1

                    i_EB0 = i_EB
                    if i_Flow_Level1 == len(Level.index) - 1:  # last category for level
                        while i_EB < (len(EB.index)):
                            i_EB += 1
                    else:
                        while ((EB.at[i_EB, "EB_Flow"] != Level.at[i_Flow_Level1 + 1, Col_Level]) &
                               (i_EB < Len_EB)):
                            i_EB += 1

                    # if i_EB != i_EB0:
                    Flow_Matrix0 = pd.DataFrame(EB["EB_Flow"][i_EB0:i_EB])
                    Flow_Matrix0['EB_Flow_Level1'] = Level.at[i_Flow_Level1, 'EB_Flow_Level1']
                    Flow_Matrix0['EB_Flow_Level2'] = Level.at[i_Flow_Level1, 'EB_Flow_Level2']
                    Flow_Matrix = pd.concat([Flow_Matrix, Flow_Matrix0], axis=0, ignore_index=True)

    EB['EB_Flow_Level1'] = Flow_Matrix['EB_Flow_Level1']
    EB['EB_Flow_Level2'] = Flow_Matrix['EB_Flow_Level2']
    #   EB[ 'Index'] = EB.index

    # Melt from wider to longer
    EB = pd.melt(EB, id_vars=['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3', 'EB_Flow'], value_vars=None,
                 var_name='EB_Product', value_name='Energy', col_level=None, ignore_index=False)  # True)

    EB = EB.dropna(subset=['Energy'])
    EB = EB.loc[EB['Energy'] != 0].reset_index(drop=True)

    ###############################################
    # CM: Concordance matrix
    CM = pd.DataFrame(CM)

    # Heading
    CM.columns = CM.loc[0]
    CM = CM[1:].reset_index(drop=True)
    CM['Transformation'] = None
    CM['EB_Flow_Level3'] = None

    # Remove character data
    # CM = CM.dropna(subset=['Allocation Factor'])
    CM['Allocation Factor'] = CM['Allocation Factor'].fillna(0)

    CM['Allocation Factor'] = [x if (type(x) == float) | (type(x) == int) else 0 for x in CM['Allocation Factor']]

    CM = CM.loc[CM['Allocation Factor'] != 0].reset_index(drop=True)

    CM = CM.fillna('Zachille_')
    CM = CM.groupby(['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3', 'EB_Category', 'EB_Flow', 'EB_Product',
                     'PEFA_Target_Product', 'PEFA_Target_Activity',
                     'PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2', 'PEFA_Quadrant',
                     'Transformation'])['Allocation Factor'].sum().reset_index()

    # Force sum of allocation factor by product to 1
    CM_Temp = CM.groupby(['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow', 'EB_Product',
                          'PEFA_Target_Product',
                          'PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2', 'PEFA_Quadrant',
                          'Transformation'])['Allocation Factor'].sum().reset_index()

    CM_Temp = CM_Temp.rename(columns={'Allocation Factor': 'Allocation Factor0'})

    CM = CM.merge(CM_Temp, on=['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow', 'EB_Product',
                               'PEFA_Target_Product',
                               'PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2', 'PEFA_Quadrant',
                               'Transformation'], how='left')
    CM['Allocation Factor'] = CM['Allocation Factor'] / CM['Allocation Factor0']
    CM.drop(['Allocation Factor0'], axis=1, inplace=True)
    CM.replace({'Zachille_': None}, inplace=True)

    # CM['Allocation Factor'].fillna(0, inplace=True)

    # Add EB_Category to energy balance
    CM_Temp1 = CM.fillna('Zachille_')

    CM_Temp1 = CM_Temp1.groupby(['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3', 'EB_Flow', 'EB_Category'])[
        'Allocation Factor'].sum().reset_index()
    CM_Temp1.replace({'Zachille_': None}, inplace=True)

    EB = EB.merge(CM_Temp1.drop(['Allocation Factor'], axis=1),
                  on=['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3', 'EB_Flow'], how='left')

    #######################################
    # Add bridging items
    EB_Bridging_Items = pd.DataFrame(EB_Bridging_Items)

    # Heading
    EB_Bridging_Items_Heading = EB_Bridging_Items.loc[0]

    # EB_Bridging_Items_Heading.loc[0:1] = ['EB_Flow' , 'Imports_Exports']
    # EB_Heading.insert(0,"Flow")

    EB_Bridging_Items.drop([0], axis=0, inplace=True)  # .reset_index(drop=True)

    EB_Bridging_Items.columns = EB_Bridging_Items_Heading

    # Melt from wider to longer
    EB_Bridging_Items = pd.melt(EB_Bridging_Items.drop(['Item'], axis=1),
                                id_vars=['EB_Flow', 'Imports_Exports', 'PEFA_Target_Activity', 'EB_Flow_Broader'],
                                value_vars=None, var_name='PEFA_Target_Product',
                                value_name='Energy', col_level=None, ignore_index=False)  # True)

    EB_Bridging_Items = EB_Bridging_Items.dropna(subset=['EB_Flow', 'Energy'])
    EB_Bridging_Items = EB_Bridging_Items.loc[EB_Bridging_Items['Energy'] != 0].reset_index(drop=True)

    EB_Bridging_Items['PEFA_Quadrant'] = 'Supply'
    EB_Bridging_Items['EB_Product'] = EB_Bridging_Items['PEFA_Target_Product']
    # EB_Bridging_Items.loc[EB_Bridging_Items['Imports_Exports'] == 'Fuel purchased on the territory by non-resident units (in PJ) (added to exports in PEFA)', 'PEFA_Quadrant'] = 'Use'
    EB_Bridging_Items.loc[EB_Bridging_Items['EB_Flow_Broader'] == 'Exports', 'PEFA_Quadrant'] = 'Use'
    #

    for i_Index in list(EB_Bridging_Items.index):

        i_Flow = EB_Bridging_Items.loc[i_Index, 'EB_Flow']  # list(EB_Bridging_Items['EB_Flow'].drop_duplicates()):

        CM_Temp1 = CM.loc[(CM['EB_Flow'] == i_Flow) & (CM['EB_Category'] != 'Bridging Items')].reset_index(drop=True)

        EB_Bridging_Items1 = EB_Bridging_Items.loc[[i_Index],
                                                   ['EB_Flow', 'EB_Product',
                                                    'PEFA_Quadrant', 'PEFA_Target_Product',
                                                    'PEFA_Target_Activity', 'EB_Flow_Broader', 'Energy']].reset_index(
            drop=True)
        EB_Bridging_Items1['EB_Category'] = 'Bridging Items'

        EB_Bridging_Items1['EB_Flow_Level3'] = i_Flow

        EB_Bridging_Items1['EB_Flow'] = EB_Bridging_Items1.loc[0, 'EB_Flow_Broader']
        CM_Temp1_Len = len(CM_Temp1)

        if CM_Temp1_Len == 0:  # not 'Total flaring and venting of natural gas (in PJ)':
            CM_Temp1 = CM.loc[(CM['EB_Flow'] == EB_Bridging_Items1.loc[0, 'EB_Flow_Broader']) &
                              (CM['EB_Category'] != 'Bridging Items')].reset_index(drop=True)

        for i_Column in list(set(CM_Temp1.columns) - set(EB_Bridging_Items1.columns)):
            EB_Bridging_Items1[i_Column] = CM_Temp1.loc[0, i_Column]

        CM_Temp1 = CM_Temp1.loc[
            CM_Temp1['PEFA_Target_Product'].isin(list(EB_Bridging_Items1['EB_Product'].drop_duplicates()))]
        CM_Temp1 = CM_Temp1.fillna('Zachille_')
        CM_Temp1['EB_Product'] = CM_Temp1['PEFA_Target_Product']

        CM_Temp1 = CM_Temp1.groupby(['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow', 'EB_Product',
                                     'PEFA_Target_Product', 'PEFA_Target_Activity',
                                     'PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2', 'PEFA_Quadrant',
                                     'Transformation'])['Allocation Factor'].max().reset_index()

        # Force sum of allocation factor by product to 1
        CM_Temp2 = CM_Temp1.groupby(['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow', 'EB_Product',
                                     'PEFA_Target_Product',
                                     'PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2', 'PEFA_Quadrant',
                                     'Transformation'])['Allocation Factor'].max().reset_index()

        CM_Temp2 = CM_Temp2.rename(columns={'Allocation Factor': 'Allocation Factor0'})

        CM_Temp1 = CM_Temp1.merge(CM_Temp2, on=['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow', 'EB_Product',
                                                'PEFA_Target_Product',
                                                'PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2',
                                                'PEFA_Quadrant',
                                                'Transformation'], how='left')

        CM_Temp1['Allocation Factor'] = CM_Temp1['Allocation Factor'] / CM_Temp1['Allocation Factor0']

        CM_Temp1.drop(['Allocation Factor0'], axis=1, inplace=True)
        CM_Temp1.replace({'Zachille_': None}, inplace=True)

        CM_Temp1['Comment'] = i_Flow
        CM_Temp1['EB_Flow_Level3'] = i_Flow
        CM_Temp1['EB_Category'] = 'Bridging Items'

        EB_Bridging_Items1['Comment'] = i_Flow
        EB_Bridging_Items1['EB_Product'] = EB_Bridging_Items1['PEFA_Target_Product']

        CM_Bridging_Items1 = EB_Bridging_Items1.drop(['Energy'], axis=1)
        CM_Bridging_Items1['Transformation'] = None

        CM_Bridging_Items1['Allocation Factor'] = 1
        CM_Bridging_Items1['EB_Product'] = CM_Bridging_Items1['PEFA_Target_Product']

        if CM_Temp1_Len == 0:  # Flaring

            # Expand CM and EB
            CM_Temp1['PEFA_Quadrant'] = EB_Bridging_Items1.loc[0, 'PEFA_Quadrant']
            CM = pd.concat([CM, CM_Temp1], axis=0, ignore_index=True)

            EB = pd.concat([EB, EB_Bridging_Items1.loc[:, ['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3',
                                                           'EB_Flow', 'EB_Product', 'Energy', 'EB_Category']]], axis=0,
                           ignore_index=True)

        else:  # Work out transportation

            # Work exports and imports
            ##Classification

            CM_Temp2 = CM_Temp1.copy()
            CM_Temp1['PEFA_Quadrant'] = EB_Bridging_Items1.loc[0, 'PEFA_Quadrant']
            CM_Temp1.loc[CM_Temp1[
                             'PEFA_Quadrant'] == 'Supply', 'PEFA_Target_Product_Level2'] = 'Production of energy products by SIEC class:'

            CM_Temp1['Transformation'] = 'Ignore'
            CM_Temp1['PEFA_Target_Activity'] = 'RoW'

            CM_Temp1['EB_Flow_Level3'] = EB_Bridging_Items1.loc[0, 'EB_Flow_Broader']

            CM_Temp1 = CM_Temp1.fillna('Zachille_')

            CM_Temp1 = CM_Temp1.groupby(
                ['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3', 'EB_Category', 'EB_Flow', 'EB_Product',
                 'PEFA_Target_Product', 'PEFA_Target_Activity',
                 'PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2', 'PEFA_Quadrant',
                 'Transformation'])['Allocation Factor'].max().reset_index()

            CM_Temp1.replace({'Zachille_': None}, inplace=True)

            CM = pd.concat([CM, CM_Temp1], axis=0, ignore_index=True)

            ## Energy balance

            for i_Column in ['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3', 'EB_Flow', 'EB_Product']:
                EB_Bridging_Items1[i_Column] = CM_Temp1.loc[0, i_Column]

            EB = pd.concat([EB, EB_Bridging_Items1.loc[:, ['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3',
                                                           'EB_Flow', 'EB_Product', 'Energy', 'EB_Category']]], axis=0,
                           ignore_index=True)

            # Get the difference between export and import
            CM_Temp2['EB_Flow_Level3'] = None
            CM_Temp2['Transformation'] = None

            CM = pd.concat([CM, CM_Temp2], axis=0, ignore_index=True)

            EB_Bridging_Items1['EB_Flow_Level3'] = None

            EB_Bridging_Items1['Energy'] = EB_Bridging_Items1['Energy'].fillna(0)

            EB_Bridging_Items1 = EB_Bridging_Items1.loc[:, ['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3',
                                                            'EB_Flow', 'EB_Product', 'Energy', 'PEFA_Quadrant',
                                                            'EB_Category']]

            EB_Bridging_Items1.loc[EB_Bridging_Items1['PEFA_Quadrant'] == 'Use', 'Energy'] = -1 * \
                                                                                             EB_Bridging_Items1.loc[
                                                                                                 EB_Bridging_Items1[
                                                                                                     'PEFA_Quadrant'] == 'Use', 'Energy']

            EB = pd.concat([EB, EB_Bridging_Items1.loc[:, ['EB_Flow_Level1', 'EB_Flow_Level2',
                                                           'EB_Flow', 'EB_Product', 'Energy', 'EB_Category']]], axis=0,
                           ignore_index=True)

    # Remove character data
    EB['Energy'] = [x if (type(x) == float) | (type(x) == int) else 0 for x in EB['Energy']]

    # EB['Energy'] = [0 if x is None else x for x in EB['Energy']]
    EB['Energy'] = EB['Energy'].fillna(0)

    EB = EB.fillna('Zachille_')
    EB = EB.groupby(['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3', 'EB_Flow', 'EB_Product',
                     'EB_Category'])['Energy'].sum().reset_index()

    EB.replace({'Zachille_': None}, inplace=True)

    CM = CM.fillna('Zachille_')

    CM = CM.groupby(['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3', 'EB_Category', 'EB_Flow', 'EB_Product',
                     'PEFA_Target_Product', 'PEFA_Target_Activity',
                     'PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2', 'PEFA_Quadrant',
                     'Transformation'])['Allocation Factor'].max().reset_index()

    CM.replace({'Zachille_': None}, inplace=True)

    ###################################
    # Substrat memo item of non-energy use form total

    EB0 = EB.loc[(EB['EB_Flow_Level1'] == 'Total final consumption') &
                 (EB['EB_Flow_Level2'] == 'Non-energy use') &
                 (EB['EB_Flow'] == '   Memo: Non-energy use chemical/petrochemical')].rename(
        columns={'Energy': 'Energy0'})
    if (len(EB0) > 0):
        EB0['EB_Flow'] = 'Non-energy use industry/transformation/energy'
        # return (EB)
        EB = EB.merge(EB0,
                      on=['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3', 'EB_Flow', 'EB_Product', 'EB_Category'],
                      how='outer')

        # EB['Energy0'] =  [ 0 if  (x is None) | (type(x) != float) else x for x in EB['Energy0'] ]
        EB['Energy0'] = EB['Energy0'].fillna(0)
        EB['Energy'] = EB['Energy'].fillna(0)
        EB.loc[EB['Energy'] == 0, 'Energy'] = EB.loc[EB['Energy'] == 0, 'Energy0']

        EB['Energy'] = EB['Energy'] - EB['Energy0']

        EB = EB.drop(['Energy0'], axis=1)

    ###############################################
    ####### Change sign Exports, stock changes
    for i_EB in EB_Flow_Change_Sign:
        EB.loc[EB['EB_Flow'] == i_EB, 'Energy'] = -1 * EB.loc[EB['EB_Flow'] == i_EB, 'Energy']

    ###############  Info   #######################
    Filter = str(Filter)
    if (Filter != 'ALL') & (Filter != '  ALL (Statistical difference exclusive)'):
        if Filter != '  o/w Statistical differences':
            CM = CM.loc[CM['EB_Category'] == Filter].reset_index(drop=True)
            EB = EB.loc[EB['EB_Category'] == Filter].reset_index(drop=True)
        else:
            CM.loc[CM['EB_Flow'] == 'Statistical differences', 'EB_Category'] = '  o/w Statistical differences'
            EB.loc[EB['EB_Flow'] == 'Statistical differences', 'EB_Category'] = '  o/w Statistical differences'
            CM = CM.loc[CM['EB_Category'] == Filter].reset_index(drop=True)
            EB = EB.loc[EB['EB_Category'] == Filter].reset_index(drop=True)

    #################################

    ########################
    ### WORK OUT ITEMS THAT NEED UPSTREAM TRANSFORMATION
    # ITEM1 Production
    ## Will be used to populate Energy product from the supply
    CM_Temp1 = CM.loc[(CM['EB_Flow_Level1'] == 'Total primary energy supply') &
                      (CM['EB_Flow'] == 'Production') &
                      (CM['Transformation'] != 'Ignore')]

    if (len(CM_Temp1) > 0):

        CM = CM.loc[~ ((CM['EB_Flow_Level1'] == 'Total primary energy supply') &
                       (CM['EB_Flow'] == 'Production') &
                       (CM['Transformation'] != 'Ignore'))]

        ###correct the sign for accumulation
        CM_Temp1.loc[CM_Temp1['PEFA_Target_Activity'] == 'Acc', 'Allocation Factor'] = -1 * CM_Temp1.loc[
            CM_Temp1['PEFA_Target_Activity'] == 'Acc', 'Allocation Factor']
        CM = pd.concat([CM, CM_Temp1], axis=0, ignore_index=True)

        ## Duplicate for energy from natural inputs na d waste from the use
        CM_Temp2 = CM_Temp1.loc[~ CM_Temp1['PEFA_Target_Activity'].isin(['Acc', 'RoW'])]

        CM_Temp2['PEFA_Quadrant'] = 'Use'

        CM_Temp2['PEFA_Target_Product_Level1'] = 'Energy from natural inputs:'
        CM_Temp2['PEFA_Target_Product_Level2'] = None
        CM_Temp2['PEFA_Target_Product'] = 'Natural resource inputs'

        ## Renewable
        if 1 == 2:
            for i_Str in EB_Renewable:
                CM_Temp2.loc[CM_Temp2['EB_Product'].str.lower().str.contains(
                    str.lower(i_Str)), 'PEFA_Target_Product'] = 'Inputs of energy from renewable sources'

        CM_Temp2.loc[CM_Temp2['EB_Product'].isin(
            EB_Product_Renewable), 'PEFA_Target_Product'] = 'Inputs of energy from renewable sources'

        ##Waste
        CM_Temp2.loc[
            CM_Temp2['EB_Product'].isin(EB_Product_Waste), 'PEFA_Target_Product_Level1'] = 'Other residual flows:'

        CM_Temp2.loc[CM_Temp2['EB_Product'].isin(EB_Product_Waste), 'PEFA_Target_Product'] = 'Energy from solid waste'

        CM = pd.concat([CM, CM_Temp2], axis=0, ignore_index=True)

        ## duplicate for Environment and accumulation(waste) from the supply
        CM_Temp2['PEFA_Quadrant'] = 'Supply'
        CM_Temp2['PEFA_Target_Activity'] = 'Env'
        CM_Temp2.loc[CM_Temp2['EB_Product'].isin(EB_Product_Waste), 'PEFA_Target_Activity'] = 'Acc'
        CM = pd.concat([CM, CM_Temp2], axis=0, ignore_index=True)

        ##flaring and venting
        CM_Temp2 = CM_Temp2.loc[~ CM_Temp2['EB_Flow_Level3'].isnull()]
        if len(CM_Temp2) > 0:
            CM_Temp2 = CM_Temp2.loc[
                CM_Temp2['EB_Flow_Level3'].str.lower().str.contains('|'.join(['venting', 'flaring']))]
            if len(CM_Temp2) > 0:
                CM_Temp2['PEFA_Quadrant'] = 'Use'
                CM_Temp2['PEFA_Target_Product'] = 'Energy residuals from losses'
                CM_Temp2['PEFA_Target_Product_Level1'] = 'Energy residuals:'
                CM = pd.concat([CM, CM_Temp2], axis=0, ignore_index=True)

    # ITEM1; Working out Transfers
    # Sign

    CM_Temp = CM.loc[(CM['EB_Flow_Level1'] == 'Other flows') &
                     (CM['EB_Flow'] == 'Transfers') &
                     (CM['Transformation'] != 'Ignore')]

    if len(CM_Temp) > 0:
        # duplicate to record residual use
        CM_Temp['PEFA_Target_Product_Level1'] = 'Other residual flows:'
        CM_Temp['PEFA_Target_Product_Level2'] = None
        CM_Temp['PEFA_Target_Product'] = 'Energy from solid waste'
        CM_Temp['PEFA_Quadrant'] = 'Use'
        CM = pd.concat([CM, CM_Temp], axis=0, ignore_index=True)

        # duplicate to record accumulation supply
        CM_Temp['PEFA_Quadrant'] = 'Supply'
        CM_Temp['PEFA_Target_Activity'] = 'Acc'
        CM = pd.concat([CM, CM_Temp], axis=0, ignore_index=True)

        # ITEM1; Working out statistical difference
        # Sign
    CM_Row = ((CM['EB_Flow_Level1'] == 'Other flows') &
              (CM['EB_Flow'] == 'Statistical differences') &
              (CM['Transformation'] != 'Ignore'))
    CM_Temp = CM.loc[CM_Row]

    if (len(CM_Temp) > 0):
        CM = CM.loc[~ (CM_Row)]

        # Pro rate share
        CM_Temp.fillna('Zachille_', inplace=True)

        CM_Temp = CM_Temp.merge(CM_Temp.rename(columns={'Allocation Factor': 'Sum Allocation Factor'}).groupby(
            ['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow', 'EB_Product'])['Sum Allocation Factor'].sum().reset_index(),
                                on=['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow', 'EB_Product'], how='inner')
        CM_Temp.loc[CM_Temp['Sum Allocation Factor'] != 0, 'Allocation Factor'] = CM_Temp.loc[CM_Temp[
                                                                                                  'Sum Allocation Factor'] != 0, 'Allocation Factor'] / \
                                                                                  CM_Temp.loc[CM_Temp[
                                                                                                  'Sum Allocation Factor'] != 0, 'Sum Allocation Factor']
        CM_Temp['Allocation Factor'] = -1 * CM_Temp['Allocation Factor']

        CM_Temp = CM_Temp.replace({'Zachille_': None})
        CM = pd.concat([CM, CM_Temp], axis=0, ignore_index=True)

        # for target activity in industry, duplicate to record output
        CM_Temp = CM.loc[(CM['EB_Flow_Level1'] == 'Other flows') & (CM['EB_Flow'] == 'Statistical differences') & ~ CM[
            'PEFA_Target_Activity'].isin(['Acc', 'RoW'])]
        # CM_Temp['Allocation Factor'] =  -1 * CM_Temp['Allocation Factor']
        CM_Temp['PEFA_Target_Product_Level1'] = 'Energy residuals:'
        CM_Temp['PEFA_Target_Product_Level2'] = None
        CM_Temp['PEFA_Target_Product'] = 'Energy residuals from end-use'
        CM_Temp['PEFA_Quadrant'] = 'Supply'
        CM = pd.concat([CM, CM_Temp], axis=0, ignore_index=True)

        # Duplicate for environment
        CM_Temp['PEFA_Target_Product_Level1'] = 'Energy residuals:'
        CM_Temp['PEFA_Target_Product_Level2'] = None
        CM_Temp['PEFA_Target_Product'] = 'Energy residuals from end-use'
        CM_Temp['PEFA_Quadrant'] = 'Use'
        CM_Temp['PEFA_Target_Activity'] = 'Env'
        CM = pd.concat([CM, CM_Temp], axis=0, ignore_index=True)

    ########################
    # Merging EB and CM

    PEFA = EB.merge(CM,
                    on=['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3', 'EB_Flow', 'EB_Product', 'EB_Category'],
                    how='inner')

    PEFA['PEFA_Energy'] = pd.to_numeric(PEFA['Energy'], errors='coerce') * pd.to_numeric(PEFA['Allocation Factor'],
                                                                                         errors='coerce') / 1000
    # return (PEFA)
    ########################
    ### WORK OUT ITEMS THAT NEED DOWNSTREAM TRANSFORMATION

    PEFA_Row = ((PEFA['EB_Flow_Level1'].isin(['Transformation processes',
                                              'Energy industry own use',
                                              'Losses',
                                              'Total final consumption',
                                              'Electricity output (GWh)',
                                              'Heat output'])) |
                ((PEFA['EB_Flow_Level1'] == 'Total primary energy supply') &
                 (PEFA['EB_Flow'].isin(['International marine bunkers', 'International aviation bunkers']))))

    PEFA_Temp = PEFA.loc[PEFA_Row]

    if len(PEFA_Temp) > 0:
        PEFA = PEFA.loc[~(PEFA_Row)]

        # Exclusion of irrelevant transaction for elec_heat
        # return(PEFA_Temp)
        if 1 == 2:
            PEFA_Temp = PEFA_Temp.loc[~((PEFA_Temp['PEFA_Energy'] > 0) &
                                        (PEFA_Temp['EB_Category'].isin(['Elec_Heat'])) &
                                        ~(((PEFA_Temp['EB_Flow'].isin(
                                            ['Main activity producer electricity plants (transf.)',
                                             'Autoproducer electricity plants (transf.)',
                                             'Autoproducers - electricity plants'])) &
                                           (PEFA_Temp['EB_Product'] == 'Electricity')) |
                                          ((PEFA_Temp['EB_Flow'].isin(['Main activity producer heat plants (transf.)',
                                                                       'Main activity producers - heat plants'])) &
                                           (PEFA_Temp['EB_Product'].isin(['Heat']))) |
                                          ((PEFA_Temp['EB_Flow'].isin(['Main activity producer CHP plants (transf.)',
                                                                       'Main activity producers - CHP plants'])) &
                                           (PEFA_Temp['EB_Product'].isin(['Heat', 'Electricity'])))))
            ,]

        # return (PEFA_Temp)
        PEFA_Temp1 = PEFA_Temp.copy()

        # Determine supply or use side
        # PEFA_Temp.loc[PEFA_Temp['PEFA_Energy']<0, 'PEFA_Quadrant'] = 'Use'
        # PEFA_Temp.loc[(PEFA_Temp['PEFA_Energy'] < 0) & (PEFA_Temp['EB_Flow_Level1']== 'Transformation processes'),
        #              'PEFA_Target_Product_Level2']='Transformation of energy products by SIEC class:'
        # PEFA_Temp.loc[(PEFA_Temp['PEFA_Energy'] < 0) & (PEFA_Temp['EB_Flow_Level1'] == 'Energy industry own use'),
        #              'PEFA_Target_Product_Level2'] = 'End-use of energy products by SIEC class:'

        PEFA_Temp.loc[(PEFA_Temp['PEFA_Energy'] > 0) &
                      (PEFA_Temp['EB_Flow_Level1'].isin(['Transformation processes',
                                                         'Total primary energy supply'])),  # ,'Energy industry own use', 'Losses'
                      'PEFA_Quadrant'] = 'Supply'

        # PEFA_Temp.loc[(PEFA_Temp['PEFA_Energy']>0 & PEFA_Temp['EB_Flow_Level1']== 'Transformation processes'), 'PEFA_Target_Product_Level2']='Production of energy products by SIEC class:'

        PEFA_Temp.loc[(PEFA_Temp['PEFA_Energy'] > 0) &
                      (PEFA_Temp['EB_Flow_Level1'].isin(
                          ['Transformation processes'])),  # ,'Energy industry own use' , 'Losses'
                      'PEFA_Target_Product_Level2'] = 'Production of energy products by SIEC class:'

        PEFA_Temp.loc[
            (PEFA_Temp['EB_Flow_Level1'].isin(['Transformation processes'])) |  # , 'Energy industry own use', 'Losses'
            ((PEFA_Temp['EB_Flow_Level1'] == 'Total primary energy supply') &
             (PEFA_Temp['EB_Category'] != 'Bridging Items')), 'PEFA_Energy'] = \
            PEFA_Temp.loc[(PEFA_Temp['EB_Flow_Level1'].isin(
                ['Transformation processes'])) |  # , 'Energy industry own use', 'Losses'
                          ((PEFA_Temp['EB_Flow_Level1'] == 'Total primary energy supply') &
                           (PEFA_Temp['EB_Category'] != 'Bridging Items')), 'PEFA_Energy'].abs()

        PEFA_Temp.loc[
            (PEFA_Temp['EB_Flow_Level1'].isin(['Energy industry own use', 'Losses'])), 'PEFA_Energy'] = \
            -1 * PEFA_Temp.loc[(PEFA_Temp['EB_Flow_Level1'].isin(
                ['Energy industry own use', 'Losses'])), 'PEFA_Energy']

        ## Correct for elect_heat Elec_Heat

        # PEFA_Temp.loc[PEFA_Temp['EB_Category'].isin(['Elec_Heat']) ,'PEFA_Target_Product_Level1'] ='Energy residuals:'
        # PEFA_Temp.loc[PEFA_Temp['EB_Category'].isin(['Elec_Heat']), 'PEFA_Target_Product_Level2'] = None
        # PEFA_Temp.loc[PEFA_Temp['EB_Category'].isin(['Elec_Heat']), 'PEFA_Target_Product']='Energy residuals from losses'

        ##aggregate to assign to Energy residuals from losses
        # Add supply of losses by activity

        PEFA_Temp1.loc[
            PEFA_Temp1['EB_Flow_Level1'].isin(['Transformation processes', 'Energy industry own use', 'Losses']),
            'PEFA_Energy'] = -1 * PEFA_Temp1.loc[
            PEFA_Temp1['EB_Flow_Level1'].isin(['Transformation processes', 'Energy industry own use', 'Losses']),
            'PEFA_Energy']
        PEFA_Temp1.loc[(PEFA_Temp1['EB_Flow_Level1'] == 'Total primary energy supply') &
                       (PEFA_Temp1['EB_Category'] != 'Bridging Items'), 'PEFA_Energy'] = \
            PEFA_Temp1.loc[(PEFA_Temp1['EB_Flow_Level1'] == 'Total primary energy supply') &
                           (PEFA_Temp1['EB_Category'] != 'Bridging Items'), 'PEFA_Energy'].abs()
        PEFA_Temp1['PEFA_Target_Product_Level1'] = 'Energy residuals:'
        PEFA_Temp1['PEFA_Target_Product_Level2'] = None
        PEFA_Temp1['PEFA_Target_Product'] = 'Energy residuals from losses'  # Energy residuals from end-use

        PEFA_Temp1.loc[((PEFA_Temp1['EB_Flow_Level1'].isin(['Energy industry own use',
                                                            'Losses',
                                                            'Total final consumption'])) & (
                            ~(PEFA_Temp1['EB_Flow'] == 'Losses'))) |
                       ((PEFA_Temp1['EB_Flow_Level1'] == 'Total primary energy supply') &
                        (PEFA_Temp1['EB_Flow'].isin(['International marine bunkers',
                                                     'International aviation bunkers']))), 'PEFA_Target_Product'] = \
            'Energy residuals from end-use'

        PEFA_Temp1.loc[(PEFA_Temp1['EB_Flow_Level1'] == 'Total final consumption') &
                       (PEFA_Temp1['EB_Flow_Level2'] == 'Non-energy use'),
                       'PEFA_Target_Product_Level1'] = 'Other residual flows:'

        PEFA_Temp1.loc[(PEFA_Temp1['EB_Flow_Level1'] == 'Total final consumption') &
                       (PEFA_Temp1['EB_Flow_Level2'] == 'Non-energy use'),
                       'PEFA_Target_Product'] = 'Residuals from end-use for non-energy purposes'

        PEFA_Temp1['PEFA_Quadrant'] = 'Supply'

        # , 'Electricity output (GWh)', 'Heat output'

        PEFA_Temp = pd.concat([PEFA_Temp, PEFA_Temp1], axis=0, ignore_index=True)

        # Add use of losses by the environment
        PEFA_Temp1['PEFA_Quadrant'] = 'Use'
        PEFA_Temp1['PEFA_Target_Activity'] = 'Env'
        PEFA_Temp1.loc[(PEFA_Temp1['EB_Flow_Level1'] == 'Total final consumption') &
                       (PEFA_Temp1['EB_Flow_Level2'] == 'Non-energy use'), 'PEFA_Target_Activity'] = 'Acc'
        PEFA_Temp = pd.concat([PEFA_Temp, PEFA_Temp1], axis=0, ignore_index=True)

        PEFA = pd.concat([PEFA, PEFA_Temp], axis=0, ignore_index=True)

    # PEFA=PEFA.loc[PEFA['PEFA_Energy']!=0]
    # return(PEFA)
    ##########
    # Prepare PESUT
    # PEFA=PEFA.loc[PEFA['PEFA_Energy']!=0]
    # return (PEFA)

    # return (PEFA)
    PEFA.fillna('Zachille_', inplace=True)

    PEFA_Stat_Diff = PEFA.loc[PEFA['EB_Flow'] == 'Statistical differences']
    PEFA_Stat_Diff['PEFA_Target_Activity'] = 'Statistical differences'

    PEFA_Stat_Diff = PEFA_Stat_Diff.groupby(['PEFA_Target_Product_Level1',
                                             'PEFA_Target_Product_Level2',
                                             'PEFA_Target_Product',
                                             'PEFA_Target_Activity',
                                             'PEFA_Quadrant'])['PEFA_Energy'].sum().reset_index()

    if Filter == '  ALL (Statistical difference exclusive)':
        PEFA = PEFA.loc[PEFA['EB_Flow'] != 'Statistical differences']

    PEFA = PEFA.groupby(['PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2', 'PEFA_Target_Product',
                         'PEFA_Target_Activity', 'PEFA_Quadrant'])['PEFA_Energy'].sum().reset_index()

    PEFA = pd.concat([PEFA, PEFA_Stat_Diff], axis=0, ignore_index=True)

    PEFA = PEFA.replace({'Zachille_': None})

    # PEFA_Stat_Diff = PEFA_Stat_Diff.replace({'Zachille_': None})

    return (PEFA)


def EE_EB2PEFA(EB, CM, EB_Bridging_Items, EB_Product, Filter):
    # EB: Energy Balance
    # CM: Concordance matrix
    # EB_Bridging_Items: Briding item (Flaring)

    #Converting the the Flow x product matrix EB into
    # 5-dimension matrix: Flow_Level1  Flow_Level2    Flow   Product    Energy
    #folder0 = os.path.dirname(os.path.realpath(__file__))

    EB = pd.DataFrame(EB)

    #Heading
    EB_Heading =  EB.loc[0]
    #EB_Heading.insert(0,"Flow")
    EB_Heading[0] ='EB_Flow'
    EB_Heading0 = EB_Heading.copy()

    #remove special character
    #final = [re.sub(r"[^a-zA-Z0-9]+", ' ', k) for k in a.split("\n")]

    for i in range( len(EB_Heading0)):
        #EB_Heading0[i] = ''.join(letter for letter in EB_Heading0[i] if letter.isalnum() )
        EB_Heading0[i] = ''.join(map( lambda letter: letter if letter.isalnum() else '_', EB_Heading0[i] ))

    #EB_Heading =pd.DataFrame({'Heading_Original': EB_Heading,
     #                         'Heading_Modig': EB_Heading0})
    EB.columns = EB_Heading
    #return(EB_Heading0 )

    EB = EB.loc[1:].reset_index(drop=True)

    EB['EB_Flow_Level3']=None

    # group of product
    EB_Product = pd.DataFrame(EB_Product)

    EB_Product.columns = EB_Product.loc[0]
    EB_Product = EB_Product.loc[1:].reset_index(drop=True)
    EB_Product_Renewable = list(EB_Product.loc[EB_Product['Group'].isin(['Renewable']),'EB_Product'])
    EB_Product_Waste = list(EB_Product.loc[EB_Product['Group'].isin(['Waste']), 'EB_Product'])


    # Flow
    #Level 1

    Level = pd.DataFrame ({'EB_Flow_Level1' : ["Total primary energy supply" ,
               'Other flows' ,
               "Transformation processes" ,
               "Energy industry own use" ,
               "Losses" ,
               "Total final consumption",
               "Total final consumption" ,
               "Total final consumption" ,
               "Total final consumption" ,
               "Electricity output (GWh)" ,
               "Heat output"],

    'EB_Flow_Level2' : [ None,
                 None,
                 None,
                 None,
                 None,
                 "Industry" ,
                "Transport" ,
                "Other" ,
                "Non-energy use" ,
                None ,
                None]
    })

    EB_Flow_Change_Sign = ['Exports', 'Stock changes']

    i_EB = 0
    i_Flow_Level1 = 0

    # Total primary energy supply
    while  (EB.at[i_EB,"EB_Flow"] != Level.at[i_Flow_Level1, 'EB_Flow_Level1']):
        i_EB += 1

    # Total primary energy supply is found
    Flow_Matrix = pd.DataFrame(EB["EB_Flow"][0:i_EB])
    Flow_Matrix['EB_Flow_Level1'] = Level.at[i_Flow_Level1, 'EB_Flow_Level1']
    Flow_Matrix['EB_Flow_Level2'] = Level.at[i_Flow_Level1, 'EB_Flow_Level2']
    #Add empty row

    Flow_Matrix.loc[len(Flow_Matrix.index)]= None

    # Deal with Transfer and statistical discrepancy
    i_Flow_Level1 += 1
    i_EB += 1
    i_EB0 = i_EB
    while  (EB.at[i_EB,"EB_Flow"] != Level.at[i_Flow_Level1+1, 'EB_Flow_Level1']):
        i_EB += 1


    if i_EB != i_EB0:
        Flow_Matrix0 = pd.DataFrame( EB["EB_Flow"][i_EB0:i_EB])
        Flow_Matrix0['EB_Flow_Level1'] = Level.at[i_Flow_Level1, 'EB_Flow_Level1']
        Flow_Matrix0['EB_Flow_Level2'] = Level.at[i_Flow_Level1, 'EB_Flow_Level2']
        Flow_Matrix = pd.concat([Flow_Matrix, Flow_Matrix0], axis=0, ignore_index=True)


        #Add empty row
        #Flow_Matrix.loc[len(Flow_Matrix.index)]=None
        #i_EB += 1

    # Transformation processes  & Energy industry own use
    for i_Flow_Level1 in range(2,len(Level.index)):

        if Level.at[i_Flow_Level1, 'EB_Flow_Level2']:

            #Col_Level = 'EB_Flow_Level2'

            if Level.at[i_Flow_Level1-1, 'EB_Flow_Level1'] != Level.at[i_Flow_Level1, 'EB_Flow_Level1']:
                #Add empty row for Total final consumption
                Flow_Matrix.loc[len(Flow_Matrix.index)]=[None] * 3
                i_EB += 1

            # Check if the corresponding category is for level 2
            #if EB.at[i_EB,"Flow"] != Level.at[i_Flow_Level1, Col_Level]:
                #return(Level.at[i_Flow_Level1, Col_Level])
                #continue

            i_EB += 1
            i_EB0 = i_EB

            if i_Flow_Level1 == len(Level.index)-1: # last category for level
                while  i_EB < len(EB.index):
                    i_EB += 1

            else:
                while  ((EB.at[i_EB,"EB_Flow"] != Level.at[i_Flow_Level1+1, 'EB_Flow_Level2'] ) &
                    (EB.at[i_EB,"EB_Flow"] != Level.at[i_Flow_Level1+1, 'EB_Flow_Level1'] )):
                    i_EB += 1

            #Add empty row
            Flow_Matrix.loc[len(Flow_Matrix.index)]=None

            Flow_Matrix0 = pd.DataFrame(EB["EB_Flow"][i_EB0:i_EB])
            Flow_Matrix0['EB_Flow_Level1'] = Level.at[i_Flow_Level1, 'EB_Flow_Level1']
            Flow_Matrix0['EB_Flow_Level2'] = Level.at[i_Flow_Level1, 'EB_Flow_Level2']
            Flow_Matrix = pd.concat([Flow_Matrix, Flow_Matrix0], axis=0, ignore_index=True)

        else:
            Col_Level = 'EB_Flow_Level1'

            if Level.at[i_Flow_Level1, 'EB_Flow_Level1']=='Losses':

                Flow_Matrix0 = pd.DataFrame({"EB_Flow":['Losses']})
                Flow_Matrix0['EB_Flow_Level1'] = Level.at[i_Flow_Level1, 'EB_Flow_Level1']
                Flow_Matrix0['EB_Flow_Level2'] = Level.at[i_Flow_Level1, 'EB_Flow_Level2']
                Flow_Matrix = pd.concat([Flow_Matrix, Flow_Matrix0], axis=0, ignore_index=True)
                i_EB += 1

            else:
                if Level.at[i_Flow_Level1-1, 'EB_Flow_Level1'] != Level.at[i_Flow_Level1, 'EB_Flow_Level1']:
                    #Add empty row for Total final consumption
                    Flow_Matrix.loc[len(Flow_Matrix.index)]=None
                    i_EB += 1

                i_EB0 = i_EB
                if i_Flow_Level1 == len(Level.index)-1: # last category for level
                    while  i_EB < len(EB.index):
                        i_EB += 1
                else:
                    while  (EB.at[i_EB,"EB_Flow"] != Level.at[i_Flow_Level1+1, Col_Level]):
                        i_EB += 1


            #if i_EB != i_EB0:
                Flow_Matrix0 = pd.DataFrame(EB["EB_Flow"][i_EB0:i_EB])
                Flow_Matrix0['EB_Flow_Level1'] = Level.at[i_Flow_Level1, 'EB_Flow_Level1']
                Flow_Matrix0['EB_Flow_Level2'] = Level.at[i_Flow_Level1, 'EB_Flow_Level2']
                Flow_Matrix = pd.concat([Flow_Matrix, Flow_Matrix0], axis=0, ignore_index=True)



    EB['EB_Flow_Level1'] = Flow_Matrix['EB_Flow_Level1']
    EB[ 'EB_Flow_Level2'] = Flow_Matrix[ 'EB_Flow_Level2']
    #   EB[ 'Index'] = EB.index

    # Melt from wider to longer
    EB=pd.melt(EB, id_vars=['EB_Flow_Level1', 'EB_Flow_Level2' , 'EB_Flow_Level3' , 'EB_Flow'], value_vars=None, var_name='EB_Product', value_name='Energy', col_level=None, ignore_index=False) #True)

    EB = EB.dropna(subset=['Energy'])
    EB = EB.loc[EB['Energy'] != 0].reset_index(drop=True)



    ###############################################
    # CM: Concordance matrix
    CM = pd.DataFrame(CM)


    #Heading
    CM.columns  =  CM.loc[0]
    CM = CM[1:].reset_index(drop=True)
    CM['Transformation']=None
    CM['EB_Flow_Level3'] = None

    # Remove character data
    #CM = CM.dropna(subset=['Allocation Factor'])
    CM['Allocation Factor'] = CM['Allocation Factor'].fillna(0)

    CM['Allocation Factor'] = [x if (type(x) == float) | (type(x) == int)  else 0 for x in CM['Allocation Factor']]


    CM = CM.loc[CM['Allocation Factor'] != 0].reset_index(drop=True)

    CM = CM.fillna('Zachille_')
    CM = CM.groupby(['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3', 'EB_Category', 'EB_Flow', 'EB_Product',
                      'PEFA_Target_Product', 'PEFA_Target_Activity',
                      'PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2', 'PEFA_Quadrant',
                       'Transformation'])['Allocation Factor'].sum().reset_index()

    # Force sum of allocation factor by product to 1
    CM_Temp = CM.groupby(['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow', 'EB_Product',
                                 'PEFA_Target_Product',
                                 'PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2', 'PEFA_Quadrant',
                                 'Transformation'])['Allocation Factor'].sum().reset_index()

    CM_Temp = CM_Temp.rename(columns={'Allocation Factor': 'Allocation Factor0'})

    CM = CM.merge(CM_Temp, on=['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow', 'EB_Product',
                                            'PEFA_Target_Product',
                                            'PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2', 'PEFA_Quadrant',
                                            'Transformation'], how='left')
    CM['Allocation Factor'] = CM['Allocation Factor'] / CM['Allocation Factor0']
    CM.drop(['Allocation Factor0'], axis=1, inplace=True)
    CM.replace({'Zachille_': None}, inplace=True)


    #CM['Allocation Factor'].fillna(0, inplace=True)

    # Add EB_Category to energy balance
    CM_Temp1 = CM.fillna('Zachille_')


    CM_Temp1 = CM_Temp1.groupby(['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3', 'EB_Flow','EB_Category'])['Allocation Factor'].sum().reset_index()
    CM_Temp1.replace({'Zachille_': None}, inplace=True)

    EB = EB.merge(CM_Temp1.drop(['Allocation Factor'], axis=1) , on=['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3', 'EB_Flow'], how='left')

    #######################################
    # Add bridging items
    EB_Bridging_Items = pd.DataFrame(EB_Bridging_Items)

    # Heading
    EB_Bridging_Items_Heading = EB_Bridging_Items.loc[0]

    #EB_Bridging_Items_Heading.loc[0:1] = ['EB_Flow' , 'Imports_Exports']
    # EB_Heading.insert(0,"Flow")

    EB_Bridging_Items.drop([0] ,  axis = 0, inplace = True) #.reset_index(drop=True)

    EB_Bridging_Items.columns = EB_Bridging_Items_Heading

    # Melt from wider to longer
    EB_Bridging_Items = pd.melt(EB_Bridging_Items.drop(['Item'], axis = 1),
                                id_vars=['EB_Flow' , 'Imports_Exports', 'PEFA_Target_Activity', 'EB_Flow_Broader'],
                                value_vars=None, var_name='PEFA_Target_Product',
                                value_name='Energy', col_level=None, ignore_index=False)  # True)

    EB_Bridging_Items = EB_Bridging_Items.dropna(subset = ['EB_Flow', 'Energy'])
    EB_Bridging_Items = EB_Bridging_Items.loc[EB_Bridging_Items['Energy'] !=0].reset_index(drop=True)

    EB_Bridging_Items['PEFA_Quadrant'] = 'Supply'
    EB_Bridging_Items['EB_Product'] = EB_Bridging_Items['PEFA_Target_Product']
    #EB_Bridging_Items.loc[EB_Bridging_Items['Imports_Exports'] == 'Fuel purchased on the territory by non-resident units (in PJ) (added to exports in PEFA)', 'PEFA_Quadrant'] = 'Use'
    EB_Bridging_Items.loc[EB_Bridging_Items['EB_Flow_Broader'] == 'Exports', 'PEFA_Quadrant'] = 'Use'
    #

    for i_Index in list(EB_Bridging_Items.index) :


        i_Flow = EB_Bridging_Items.loc[i_Index, 'EB_Flow'] # list(EB_Bridging_Items['EB_Flow'].drop_duplicates()):

        CM_Temp1 = CM.loc[(CM['EB_Flow']== i_Flow) & (CM['EB_Category']!='Bridging Items') ].reset_index(drop=True)

        EB_Bridging_Items1 = EB_Bridging_Items.loc[[i_Index],
                                                   ['EB_Flow', 'EB_Product',
                                                    'PEFA_Quadrant', 'PEFA_Target_Product',
                                                    'PEFA_Target_Activity', 'EB_Flow_Broader' , 'Energy']].reset_index(drop=True)
        EB_Bridging_Items1['EB_Category']='Bridging Items'


        EB_Bridging_Items1['EB_Flow_Level3'] = i_Flow

        EB_Bridging_Items1['EB_Flow'] = EB_Bridging_Items1.loc[0, 'EB_Flow_Broader']
        CM_Temp1_Len = len(CM_Temp1)

        if  CM_Temp1_Len == 0 : # not 'Total flaring and venting of natural gas (in PJ)':
            CM_Temp1 =  CM.loc[(CM['EB_Flow']== EB_Bridging_Items1.loc[0,'EB_Flow_Broader']) &
                               (CM['EB_Category'] != 'Bridging Items')].reset_index(drop=True)

        for i_Column in list(set(CM_Temp1.columns) - set(EB_Bridging_Items1.columns)):
                EB_Bridging_Items1[i_Column] = CM_Temp1.loc[0, i_Column]


        CM_Temp1= CM_Temp1.loc[CM_Temp1['PEFA_Target_Product'].isin( list(EB_Bridging_Items1['EB_Product'].drop_duplicates()) ) ]
        CM_Temp1 = CM_Temp1.fillna('Zachille_')
        CM_Temp1['EB_Product'] = CM_Temp1['PEFA_Target_Product']


        CM_Temp1 = CM_Temp1.groupby(['EB_Flow_Level1', 'EB_Flow_Level2',  'EB_Flow', 'EB_Product',
         'PEFA_Target_Product' ,   'PEFA_Target_Activity',
        'PEFA_Target_Product_Level1',  'PEFA_Target_Product_Level2' , 'PEFA_Quadrant',
         'Transformation'   ])['Allocation Factor'].max().reset_index()

        #Force sum of allocation factor by product to 1
        CM_Temp2 = CM_Temp1.groupby(['EB_Flow_Level1', 'EB_Flow_Level2',  'EB_Flow', 'EB_Product',
                                     'PEFA_Target_Product',
                                     'PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2', 'PEFA_Quadrant',
                                     'Transformation'])['Allocation Factor'].max().reset_index()

        CM_Temp2=CM_Temp2.rename(columns={'Allocation Factor':'Allocation Factor0'})

        CM_Temp1 = CM_Temp1.merge(CM_Temp2, on=['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow', 'EB_Product',
                                     'PEFA_Target_Product',
                                     'PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2', 'PEFA_Quadrant',
                                       'Transformation' ], how='left')

        CM_Temp1['Allocation Factor']=CM_Temp1['Allocation Factor']/CM_Temp1['Allocation Factor0']

        CM_Temp1.drop(['Allocation Factor0'], axis=1, inplace=True)
        CM_Temp1.replace({'Zachille_': None}, inplace=True)

        CM_Temp1['Comment'] = i_Flow
        CM_Temp1['EB_Flow_Level3'] = i_Flow
        CM_Temp1['EB_Category'] = 'Bridging Items'

        EB_Bridging_Items1['Comment'] = i_Flow
        EB_Bridging_Items1['EB_Product'] = EB_Bridging_Items1['PEFA_Target_Product']

        CM_Bridging_Items1 = EB_Bridging_Items1.drop(['Energy'], axis=1)
        CM_Bridging_Items1['Transformation'] = None

        CM_Bridging_Items1['Allocation Factor'] = 1
        CM_Bridging_Items1['EB_Product'] = CM_Bridging_Items1['PEFA_Target_Product']

        if CM_Temp1_Len ==0 : # Flaring

            # Expand CM and EB
            CM_Temp1['PEFA_Quadrant'] = EB_Bridging_Items1.loc[0, 'PEFA_Quadrant']
            CM = pd.concat([CM, CM_Temp1], axis=0, ignore_index=True)

            EB = pd.concat([EB, EB_Bridging_Items1.loc[:, ['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3',
                                                           'EB_Flow', 'EB_Product', 'Energy', 'EB_Category']]], axis=0,
                           ignore_index=True)

        else: #Work out transportation

            #Work exports and imports
            ##Classification

            CM_Temp2=CM_Temp1.copy()
            CM_Temp1['PEFA_Quadrant'] = EB_Bridging_Items1.loc[0, 'PEFA_Quadrant']
            CM_Temp1.loc[CM_Temp1['PEFA_Quadrant']=='Supply', 'PEFA_Target_Product_Level2']='Production of energy products by SIEC class:'

            CM_Temp1['Transformation'] ='Ignore'
            CM_Temp1['PEFA_Target_Activity']='RoW'

            CM_Temp1['EB_Flow_Level3']=EB_Bridging_Items1.loc[0,'EB_Flow_Broader']

            CM_Temp1 = CM_Temp1.fillna('Zachille_')

            CM_Temp1 = CM_Temp1.groupby(['EB_Flow_Level1', 'EB_Flow_Level2',  'EB_Flow_Level3' , 'EB_Category',   'EB_Flow', 'EB_Product',
                'PEFA_Target_Product' ,    'PEFA_Target_Activity',
                'PEFA_Target_Product_Level1',  'PEFA_Target_Product_Level2' , 'PEFA_Quadrant',
                'Transformation' ])['Allocation Factor'].max().reset_index()

            CM_Temp1.replace({'Zachille_': None}, inplace=True)

            CM = pd.concat([CM, CM_Temp1], axis=0, ignore_index=True)


            ## Energy balance

            for i_Column in ['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3', 'EB_Flow', 'EB_Product']:
                EB_Bridging_Items1[i_Column] = CM_Temp1.loc[0, i_Column]

            EB = pd.concat([EB, EB_Bridging_Items1.loc[:, ['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3',
                                                           'EB_Flow','EB_Product', 'Energy', 'EB_Category']]], axis=0, ignore_index=True)


            #Get the difference between export and import
            CM_Temp2['EB_Flow_Level3']=None
            CM_Temp2['Transformation'] = None

            CM = pd.concat([CM, CM_Temp2], axis=0, ignore_index = True)

            EB_Bridging_Items1['EB_Flow_Level3'] = None

            EB_Bridging_Items1['Energy'] = EB_Bridging_Items1['Energy'].fillna(0)

            EB_Bridging_Items1= EB_Bridging_Items1.loc[:, ['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3',
                                       'EB_Flow', 'EB_Product', 'Energy', 'PEFA_Quadrant', 'EB_Category']]

            EB_Bridging_Items1.loc[EB_Bridging_Items1['PEFA_Quadrant'] =='Use', 'Energy'] = -1 * EB_Bridging_Items1.loc[EB_Bridging_Items1['PEFA_Quadrant']=='Use', 'Energy']

            EB = pd.concat([EB, EB_Bridging_Items1.loc[:, ['EB_Flow_Level1', 'EB_Flow_Level2',
                                                           'EB_Flow', 'EB_Product', 'Energy', 'EB_Category']]], axis=0,
                           ignore_index=True)



    #Remove character data
    EB['Energy']= [ x if  (type(x) == float) | (type(x) == int)  else 0 for x in EB['Energy'] ]

    #EB['Energy'] = [0 if x is None else x for x in EB['Energy']]
    EB['Energy'] = EB['Energy'].fillna(0)

    EB = EB.fillna('Zachille_')
    EB = EB.groupby(['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3','EB_Flow', 'EB_Product',
                                 'EB_Category'])['Energy'].sum().reset_index()

    EB.replace({'Zachille_': None}, inplace=True)

    CM = CM.fillna('Zachille_')

    CM = CM.groupby(['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow_Level3', 'EB_Category', 'EB_Flow', 'EB_Product',
                      'PEFA_Target_Product', 'PEFA_Target_Activity',
                      'PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2', 'PEFA_Quadrant',
                      'Transformation'])['Allocation Factor'].max().reset_index()

    CM.replace({'Zachille_': None}, inplace=True)

    ###################################
    # Substrat memo item of non-energy use form total

    EB0 = EB.loc[(EB['EB_Flow_Level1']== 'Total final consumption') &
                 (EB['EB_Flow_Level2']=='Non-energy use') &
                 (EB['EB_Flow'] == '   Memo: Non-energy use chemical/petrochemical') ].rename(columns={'Energy': 'Energy0'})
    if (len(EB0)>0):
        EB0['EB_Flow']='Non-energy use industry/transformation/energy'
        #return (EB)
        EB = EB.merge(EB0, on=['EB_Flow_Level1' , 'EB_Flow_Level2' , 'EB_Flow_Level3', 'EB_Flow' , 'EB_Product', 'EB_Category'], how='outer')

        #EB['Energy0'] =  [ 0 if  (x is None) | (type(x) != float) else x for x in EB['Energy0'] ]
        EB['Energy0'] = EB['Energy0'].fillna(0)
        EB['Energy'] = EB['Energy'].fillna(0)
        EB.loc[EB['Energy'] == 0, 'Energy']= EB.loc[EB['Energy']==0 , 'Energy0']

        EB['Energy'] = EB['Energy'] - EB['Energy0']

        EB =  EB.drop(['Energy0'],  axis=1)

    ###############################################
    ####### Change sign Exports, stock changes
    for i_EB in EB_Flow_Change_Sign:
        EB.loc[EB['EB_Flow'] == i_EB, 'Energy'] = -1* EB.loc[EB['EB_Flow'] == i_EB, 'Energy']

    ###############  Info   #######################
    Filter=str(Filter)
    if (Filter != 'ALL') & (Filter != '  ALL (Statistical difference exclusive)'):
        if Filter != '  o/w Statistical differences':
            CM = CM.loc[CM['EB_Category']==  Filter ].reset_index(drop=True)
            EB = EB.loc[EB['EB_Category'] == Filter].reset_index(drop=True)
        else:
            CM.loc[CM['EB_Flow'] == 'Statistical differences', 'EB_Category']='  o/w Statistical differences'
            EB.loc[EB['EB_Flow'] == 'Statistical differences', 'EB_Category'] = '  o/w Statistical differences'
            CM = CM.loc[CM['EB_Category'] == Filter].reset_index(drop=True)
            EB = EB.loc[EB['EB_Category'] == Filter].reset_index(drop=True)

    #################################


    ########################
    ### WORK OUT ITEMS THAT NEED UPSTREAM TRANSFORMATION
    # ITEM1 Production
    ## Will be used to populate Energy product from the supply
    CM_Temp1=CM.loc[(CM['EB_Flow_Level1']=='Total primary energy supply') &
                   (CM['EB_Flow']== 'Production') &
                   ( CM['Transformation']!='Ignore')]

    if(len(CM_Temp1)>0):

        CM=CM.loc[~ ((CM['EB_Flow_Level1']=='Total primary energy supply') &
                       (CM['EB_Flow']== 'Production') &
                       (CM['Transformation']!='Ignore'))]

        ###correct the sign for accumulation
        CM_Temp1.loc[CM_Temp1['PEFA_Target_Activity']=='Acc', 'Allocation Factor' ]=-1 * CM_Temp1.loc[CM_Temp1['PEFA_Target_Activity']=='Acc', 'Allocation Factor' ]
        CM = pd.concat([CM, CM_Temp1], axis=0,ignore_index=True)

        ## Duplicate for energy from natural inputs na d waste from the use
        CM_Temp2 = CM_Temp1.loc[~ CM_Temp1['PEFA_Target_Activity'].isin(['Acc','RoW'])]

        CM_Temp2['PEFA_Quadrant'] = 'Use'

        CM_Temp2['PEFA_Target_Product_Level1'] = 'Energy from natural inputs:'
        CM_Temp2[ 'PEFA_Target_Product_Level2'] = None
        CM_Temp2['PEFA_Target_Product'] = 'Natural resource inputs'

        ## Renewable
        if 1==2:
            for i_Str in  EB_Renewable:
                CM_Temp2.loc[CM_Temp2['EB_Product'].str.lower().str.contains(str.lower( i_Str )), 'PEFA_Target_Product'] = 'Inputs of energy from renewable sources'

        CM_Temp2.loc[CM_Temp2['EB_Product'].isin(EB_Product_Renewable) , 'PEFA_Target_Product'] = 'Inputs of energy from renewable sources'



        ##Waste
        CM_Temp2.loc[CM_Temp2['EB_Product'].isin(EB_Product_Waste), 'PEFA_Target_Product_Level1'] = 'Other residual flows:'

        CM_Temp2.loc[CM_Temp2['EB_Product'].isin(EB_Product_Waste), 'PEFA_Target_Product'] = 'Energy from solid waste'

        CM = pd.concat([CM, CM_Temp2], axis=0,ignore_index=True)


        ## duplicate for Environment and accumulation(waste) from the supply
        CM_Temp2['PEFA_Quadrant'] = 'Supply'
        CM_Temp2['PEFA_Target_Activity'] = 'Env'
        CM_Temp2.loc[CM_Temp2['EB_Product'].isin(EB_Product_Waste), 'PEFA_Target_Activity'] = 'Acc'
        CM = pd.concat([CM, CM_Temp2], axis=0, ignore_index=True)

        ##flaring and venting
        CM_Temp2 = CM_Temp2.loc[~ CM_Temp2['EB_Flow_Level3'].isnull()]
        if len(CM_Temp2) > 0:
            CM_Temp2 = CM_Temp2.loc[CM_Temp2['EB_Flow_Level3'].str.lower().str.contains('|'.join(['venting' , 'flaring']))]
            if len(CM_Temp2)>0:
                CM_Temp2['PEFA_Quadrant'] = 'Use'
                CM_Temp2['PEFA_Target_Product'] = 'Energy residuals from losses'
                CM_Temp2['PEFA_Target_Product_Level1'] = 'Energy residuals:'
                CM = pd.concat([CM, CM_Temp2], axis=0, ignore_index=True)

    #ITEM1; Working out Transfers
    #Sign

    CM_Temp=CM.loc[(CM['EB_Flow_Level1']=='Other flows') &
                   (CM['EB_Flow']== 'Transfers') &
                   ( CM['Transformation'] != 'Ignore')]

    if len(CM_Temp) > 0:

        #duplicate to record residual use
        CM_Temp['PEFA_Target_Product_Level1'] = 'Other residual flows:'
        CM_Temp['PEFA_Target_Product_Level2'] = None
        CM_Temp['PEFA_Target_Product'] = 'Energy from solid waste'
        CM_Temp['PEFA_Quadrant'] = 'Use'
        CM = pd.concat([CM, CM_Temp], axis=0, ignore_index=True)

        #duplicate to record accumulation supply
        CM_Temp['PEFA_Quadrant'] = 'Supply'
        CM_Temp['PEFA_Target_Activity'] = 'Acc'
        CM = pd.concat([CM, CM_Temp], axis=0, ignore_index=True)


        # ITEM1; Working out statistical difference
        # Sign
    CM_Row = ((CM['EB_Flow_Level1'] == 'Other flows') &
                     (CM['EB_Flow'] == 'Statistical differences') &
                     (CM['Transformation'] != 'Ignore'))
    CM_Temp = CM.loc[CM_Row]

    if (len(CM_Temp) > 0):
        CM = CM.loc[~ (CM_Row)]

        # Pro rate share
        CM_Temp.fillna('Zachille_', inplace=True)

        CM_Temp = CM_Temp.merge(CM_Temp.rename(columns={'Allocation Factor': 'Sum Allocation Factor'}).groupby(
            ['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow', 'EB_Product'])['Sum Allocation Factor'].sum().reset_index(),
                                on=['EB_Flow_Level1', 'EB_Flow_Level2', 'EB_Flow', 'EB_Product'], how='inner')
        CM_Temp.loc[CM_Temp['Sum Allocation Factor'] != 0, 'Allocation Factor'] = CM_Temp.loc[CM_Temp[
                                                                                                  'Sum Allocation Factor'] != 0, 'Allocation Factor'] / \
                                                                                  CM_Temp.loc[CM_Temp[
                                                                                                  'Sum Allocation Factor'] != 0, 'Sum Allocation Factor']
        CM_Temp['Allocation Factor'] = -1 * CM_Temp['Allocation Factor']

        CM_Temp = CM_Temp.replace({'Zachille_': None})
        CM = pd.concat([CM, CM_Temp], axis=0, ignore_index=True)

        # for target activity in industry, duplicate to record output
        CM_Temp = CM.loc[(CM['EB_Flow_Level1'] == 'Other flows') & (CM['EB_Flow'] == 'Statistical differences') & ~ CM[
            'PEFA_Target_Activity'].isin(['Acc', 'RoW'])]
        # CM_Temp['Allocation Factor'] =  -1 * CM_Temp['Allocation Factor']
        CM_Temp['PEFA_Target_Product_Level1'] = 'Energy residuals:'
        CM_Temp['PEFA_Target_Product_Level2'] = None
        CM_Temp['PEFA_Target_Product'] = 'Energy residuals from end-use'
        CM_Temp['PEFA_Quadrant'] = 'Supply'
        CM = pd.concat([CM, CM_Temp], axis=0, ignore_index=True)

        # Duplicate for environment
        CM_Temp['PEFA_Target_Product_Level1'] = 'Energy residuals:'
        CM_Temp['PEFA_Target_Product_Level2'] = None
        CM_Temp['PEFA_Target_Product'] = 'Energy residuals from end-use'
        CM_Temp['PEFA_Quadrant'] = 'Use'
        CM_Temp['PEFA_Target_Activity'] = 'Env'
        CM = pd.concat([CM, CM_Temp], axis=0, ignore_index=True)

    ########################
    # Merging EB and CM

    PEFA = EB.merge(  CM, on=['EB_Flow_Level1' , 'EB_Flow_Level2' , 'EB_Flow_Level3', 'EB_Flow' ,  'EB_Product', 'EB_Category'], how='inner')


    PEFA['PEFA_Energy']= pd.to_numeric(PEFA['Energy'] , errors='coerce') * pd.to_numeric(PEFA['Allocation Factor'], errors='coerce') / 1000
    #return (PEFA)
    ########################
    ### WORK OUT ITEMS THAT NEED DOWNSTREAM TRANSFORMATION

    PEFA_Row =((PEFA['EB_Flow_Level1'].isin(['Transformation processes',
                                             'Energy industry own use',
                                             'Losses' ,
                                             'Total final consumption',
                                             'Electricity output (GWh)' ,
                                             'Heat output'])) |
                       ((PEFA['EB_Flow_Level1'] =='Total primary energy supply') &
                        (PEFA['EB_Flow'].isin(['International marine bunkers' , 'International aviation bunkers']))))

    PEFA_Temp = PEFA.loc[PEFA_Row]

    if len(PEFA_Temp)>0:
        PEFA=PEFA.loc[~(PEFA_Row)]

        #Exclusion of irrelevant transaction for elec_heat
        #return(PEFA_Temp)
        if 1==2:
            PEFA_Temp = PEFA_Temp.loc[~((PEFA_Temp['PEFA_Energy'] > 0) &
                                        (PEFA_Temp['EB_Category'].isin(['Elec_Heat'])) &
                                        ~(((PEFA_Temp['EB_Flow'].isin(
                                            ['Main activity producer electricity plants (transf.)',
                                             'Autoproducer electricity plants (transf.)',
                                             'Autoproducers - electricity plants'])) &
                                           (PEFA_Temp['EB_Product'] == 'Electricity')) |
                                          ((PEFA_Temp['EB_Flow'].isin(['Main activity producer heat plants (transf.)',
                                                                       'Main activity producers - heat plants'])) &
                                           (PEFA_Temp['EB_Product'].isin(['Heat']))) |
                                          ((PEFA_Temp['EB_Flow'].isin(['Main activity producer CHP plants (transf.)',
                                                                       'Main activity producers - CHP plants'])) &
                                           (PEFA_Temp['EB_Product'].isin(['Heat', 'Electricity'])))))
            ,]

        #return (PEFA_Temp)
        PEFA_Temp1=PEFA_Temp.copy()

        #Determine supply or use side
        #PEFA_Temp.loc[PEFA_Temp['PEFA_Energy']<0, 'PEFA_Quadrant'] = 'Use'
        #PEFA_Temp.loc[(PEFA_Temp['PEFA_Energy'] < 0) & (PEFA_Temp['EB_Flow_Level1']== 'Transformation processes'),
        #              'PEFA_Target_Product_Level2']='Transformation of energy products by SIEC class:'
        #PEFA_Temp.loc[(PEFA_Temp['PEFA_Energy'] < 0) & (PEFA_Temp['EB_Flow_Level1'] == 'Energy industry own use'),
        #              'PEFA_Target_Product_Level2'] = 'End-use of energy products by SIEC class:'


        PEFA_Temp.loc[(PEFA_Temp['PEFA_Energy']>0) &
                                (PEFA_Temp['EB_Flow_Level1'].isin(['Transformation processes' , 'Total primary energy supply'])), # ,'Energy industry own use', 'Losses'
                                'PEFA_Quadrant'] = 'Supply'

        #PEFA_Temp.loc[(PEFA_Temp['PEFA_Energy']>0 & PEFA_Temp['EB_Flow_Level1']== 'Transformation processes'), 'PEFA_Target_Product_Level2']='Production of energy products by SIEC class:'

        PEFA_Temp.loc[(PEFA_Temp['PEFA_Energy']>0) &
                                (PEFA_Temp['EB_Flow_Level1'].isin(['Transformation processes'])) , # ,'Energy industry own use' , 'Losses'
                                'PEFA_Target_Product_Level2'] ='Production of energy products by SIEC class:'

        PEFA_Temp.loc[(PEFA_Temp['EB_Flow_Level1'].isin(['Transformation processes'])) | #, 'Energy industry own use', 'Losses'
                      ((PEFA_Temp['EB_Flow_Level1']=='Total primary energy supply')  &
                       (PEFA_Temp['EB_Category'] != 'Bridging Items')), 'PEFA_Energy'] = \
        PEFA_Temp.loc[(PEFA_Temp['EB_Flow_Level1'].isin(['Transformation processes'])) | #, 'Energy industry own use', 'Losses'
                      ((PEFA_Temp['EB_Flow_Level1']=='Total primary energy supply')  &
                       (PEFA_Temp['EB_Category'] != 'Bridging Items')), 'PEFA_Energy'].abs()

        PEFA_Temp.loc[
            (PEFA_Temp['EB_Flow_Level1'].isin(['Energy industry own use', 'Losses'])) , 'PEFA_Energy'] = \
            -1*PEFA_Temp.loc[(PEFA_Temp['EB_Flow_Level1'].isin(
                ['Energy industry own use', 'Losses'])), 'PEFA_Energy']

        ## Correct for elect_heat Elec_Heat

        #PEFA_Temp.loc[PEFA_Temp['EB_Category'].isin(['Elec_Heat']) ,'PEFA_Target_Product_Level1'] ='Energy residuals:'
        #PEFA_Temp.loc[PEFA_Temp['EB_Category'].isin(['Elec_Heat']), 'PEFA_Target_Product_Level2'] = None
        #PEFA_Temp.loc[PEFA_Temp['EB_Category'].isin(['Elec_Heat']), 'PEFA_Target_Product']='Energy residuals from losses'


        ##aggregate to assign to Energy residuals from losses
        #Add supply of losses by activity

        PEFA_Temp1.loc[PEFA_Temp1['EB_Flow_Level1'].isin(['Transformation processes','Energy industry own use', 'Losses']) ,
                                 'PEFA_Energy']=-1* PEFA_Temp1.loc[PEFA_Temp1['EB_Flow_Level1'].isin(['Transformation processes','Energy industry own use', 'Losses']) ,
                                                                             'PEFA_Energy']
        PEFA_Temp1.loc[(PEFA_Temp1['EB_Flow_Level1']=='Total primary energy supply')  &
                       (PEFA_Temp1['EB_Category'] != 'Bridging Items'), 'PEFA_Energy'] = \
            PEFA_Temp1.loc[(PEFA_Temp1['EB_Flow_Level1']=='Total primary energy supply')  &
                       (PEFA_Temp1['EB_Category'] != 'Bridging Items'),'PEFA_Energy'].abs()
        PEFA_Temp1['PEFA_Target_Product_Level1'] = 'Energy residuals:'
        PEFA_Temp1['PEFA_Target_Product_Level2'] = None
        PEFA_Temp1['PEFA_Target_Product'] = 'Energy residuals from losses'  # Energy residuals from end-use

        PEFA_Temp1.loc[((PEFA_Temp1['EB_Flow_Level1'].isin(['Energy industry own use',
                                                            'Losses' ,
                                                            'Total final consumption'])) & (
            ~(PEFA_Temp1['EB_Flow'] == 'Losses'))) |
        ((PEFA_Temp1['EB_Flow_Level1'] == 'Total primary energy supply') &
         (PEFA_Temp1['EB_Flow'].isin(['International marine bunkers',
                                      'International aviation bunkers']))), 'PEFA_Target_Product'] = \
            'Energy residuals from end-use'

        PEFA_Temp1.loc[(PEFA_Temp1['EB_Flow_Level1']== 'Total final consumption') &
                       (PEFA_Temp1['EB_Flow_Level2']=='Non-energy use') ,
                       'PEFA_Target_Product_Level1'] = 'Other residual flows:'

        PEFA_Temp1.loc[(PEFA_Temp1['EB_Flow_Level1']== 'Total final consumption') &
                       (PEFA_Temp1['EB_Flow_Level2']=='Non-energy use') ,
                       'PEFA_Target_Product'] = 'Residuals from end-use for non-energy purposes'

        PEFA_Temp1['PEFA_Quadrant'] = 'Supply'

        #, 'Electricity output (GWh)', 'Heat output'

        PEFA_Temp = pd.concat([PEFA_Temp, PEFA_Temp1], axis=0, ignore_index=True)

        #Add use of losses by the environment
        PEFA_Temp1['PEFA_Quadrant'] = 'Use'
        PEFA_Temp1['PEFA_Target_Activity'] = 'Env'
        PEFA_Temp1.loc[(PEFA_Temp1['EB_Flow_Level1']== 'Total final consumption') &
                       (PEFA_Temp1['EB_Flow_Level2']=='Non-energy use') , 'PEFA_Target_Activity'] = 'Acc'
        PEFA_Temp = pd.concat([PEFA_Temp, PEFA_Temp1], axis=0, ignore_index=True)

        PEFA = pd.concat([PEFA, PEFA_Temp], axis=0, ignore_index=True)

    #PEFA=PEFA.loc[PEFA['PEFA_Energy']!=0]
    #return(PEFA)
    ##########
    # Prepare PESUT
    #PEFA=PEFA.loc[PEFA['PEFA_Energy']!=0]
    #return (PEFA)

    #return (PEFA)
    PEFA.fillna('Zachille_', inplace=True)

    PEFA_Stat_Diff = PEFA.loc[PEFA['EB_Flow']== 'Statistical differences']
    PEFA_Stat_Diff['PEFA_Target_Activity'] = 'Statistical differences'

    PEFA_Stat_Diff = PEFA_Stat_Diff.groupby(['PEFA_Target_Product_Level1',
                                             'PEFA_Target_Product_Level2',
                                             'PEFA_Target_Product',
                                             'PEFA_Target_Activity',
                                             'PEFA_Quadrant'])['PEFA_Energy'].sum().reset_index()

    if Filter == '  ALL (Statistical difference exclusive)':
        PEFA=PEFA.loc[PEFA['EB_Flow'] != 'Statistical differences' ]

    PEFA = PEFA.groupby([ 'PEFA_Target_Product_Level1', 'PEFA_Target_Product_Level2','PEFA_Target_Product' ,
                     'PEFA_Target_Activity', 'PEFA_Quadrant'])['PEFA_Energy'].sum().reset_index()

    PEFA = pd.concat([PEFA, PEFA_Stat_Diff], axis=0, ignore_index=True)

    PEFA = PEFA.replace({'Zachille_': None})

    #PEFA_Stat_Diff = PEFA_Stat_Diff.replace({'Zachille_': None})


    return(PEFA)

