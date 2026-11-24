#
# Air Emissions Account Tool
#
#       It implements the inventory-first approach
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
from pathlib import Path
# pip install pandas openpyxl
#from holoviews.examples.gallery.demos.bokeh.square_limit import nonet


@xw.func
def I2A(Inventory,
        ECM,
        UNFCCC, EDGAR,
        Activity,Type_Inventory,
        IPCC_Level, Activity_Level,
        OECD_Air = None , OECD_Sea = None, Use_OECD = None,
        Unit='Megatonnes CO2Eq'):


    EDGAR = pd.DataFrame(EDGAR)
    EDGAR.columns = EDGAR.iloc[0]
    EDGAR = EDGAR[1:]

    UNFCCC = pd.DataFrame(UNFCCC)
    UNFCCC.columns = UNFCCC.iloc[0]
    UNFCCC = UNFCCC[1:]

    Activity = pd.DataFrame(Activity)
    Activity.columns = Activity.iloc[0]
    Activity = Activity[1:]

    Inventory = pd.DataFrame(Inventory)
    Inventory.columns = Inventory.iloc[0]
    Inventory = Inventory[1:]

    Inventory = Inventory.replace({'NULL': 0})

#Allocation factors
    af0 = pd.DataFrame(ECM)

    af0.columns = af0.iloc[0]

    if Type_Inventory == "UNFCCC":
        Inventory['IPCC_count'] = Inventory['Source_Code'].astype(str).str.len()
        Inventory.loc[(Inventory['IPCC_count'] == 1) |
                 ((Inventory['Source_Code'].astype(str).str[2] == '0') & (Inventory['IPCC_count'] == 3)), 'Source_Code'] = \
        Inventory.loc[(Inventory['IPCC_count'] == 1) |
                 ((Inventory['Source_Code'].astype(str).str[2] == '0') & (Inventory['IPCC_count'] == 3)), 'Source_Code'].astype(str).str[0] + "."
        Inventory.drop(columns=['IPCC_count'], inplace=True)

        UNFCCC['IPCC_count'] = UNFCCC['Code'].astype(str).str.len()
        UNFCCC.loc[(UNFCCC['IPCC_count'] == 1) |
                 ((UNFCCC['Code'].astype(str).str[2] == '0') & (UNFCCC['IPCC_count'] == 3)), 'Code'] = \
            UNFCCC.loc[(UNFCCC['IPCC_count'] == 1) |
                     ((UNFCCC['Code'].astype(str).str[2] == '0') & (UNFCCC['IPCC_count'] == 3)), 'Code'].astype(str).str[
                0] + "."
        UNFCCC.drop(columns=['IPCC_count'], inplace=True)
      
        af0['IPCC_count'] = af0['Source_Code'].astype(str).str.len()
        af0.loc[(af0['IPCC_count'] == 1) |
                 ((af0['Source_Code'].astype(str).str[2] == '0') & (af0['IPCC_count'] == 3)), 'Source_Code'] = \
            af0.loc[(af0['IPCC_count'] == 1) |
                     ((af0['Source_Code'].astype(str).str[2] == '0') & (af0['IPCC_count'] == 3)), 'Source_Code'].astype(str).str[
                0] + "."
        af0.drop(columns=['IPCC_count'], inplace=True)

    #Selecting relevant rows that match with conversion matrix to avoid duplicates
    if 'Info' in Inventory.columns:

        Inventory = Inventory[Inventory['Info']=='Most detailed Component']
        Inventory.drop('Info', axis=1, inplace=True)

    Inventory = Inventory[ (Inventory['FossilType'] == 'fossil') | (Inventory['FossilType'].isna()) ]
    #if 'Level' in inventory.columns:inventory.drop('Level', axis=1, inplace=True)

    Inventory = Inventory.rename(columns={'POLLUTANT': 'POLLUTANT'})
    #inventory.drop('POLLUTANT', axis=1, inplace=True)
    POLLUTANT_list = ['CH4', 'CO2', 'N2O', 'F-gases']
    Inventory.loc[Inventory['POLLUTANT'].isin (["GWP_100_AR4_N2O",'N2O']), 'POLLUTANT'] = "N2O"
    Inventory.loc[Inventory['POLLUTANT'].isin ([ "GWP_100_AR4_CH4",'CH4']), 'POLLUTANT'] = "CH4"
    Inventory.loc[Inventory['POLLUTANT'] == "CO2", 'POLLUTANT'] = "CO2"
    Inventory.loc[Inventory['POLLUTANT'].isin (["GWP_100_AR4_F-gases","F-gases"]), 'POLLUTANT'] = "F-gases"

    # Rename the variable=variable to TIME_PERIOD and substring the variable
    # TIME_PERIOD to remove the leading "Y_"
    #Inventory.columns = Inventory.columns.str.replace('Y_', '')

    # Step 1.1: Transpose the dataset

    Inventoryt = pd.melt(Inventory, id_vars=['Data_Source',
    'IPCC_annex',
    'CountryRegion',
    'REF_AREA',
    'CountryName',
    'POLLUTANT',
    'Source_Code',
    'Source_Description',
    'FossilType'],
                         var_name='TIME_PERIOD', value_name='OBS_VALUE')

    Inventoryt['EMISSIONS_SOURCE'] ='Zach'

    OECD_IPCC = None

    # Bring OECD transportation
    if Use_OECD!='Do Not Use OECD International Transport Emissions':
        if Type_Inventory == "EDGAR":
            # return(list(EDGAR.loc[EDGAR['Comment'].isin(['Domestic Aviation']), 'NFR_Sector']))
            OECD_Air_IPCC = list(EDGAR.loc[EDGAR['Comment'].isin(['Domestic Aviation']), 'NFR_Sector'])[0]
            OECD_Air_IPCCDesc = list(EDGAR.loc[EDGAR['Comment'].isin(['Domestic Aviation']), 'NFR_Description'])[0]

            OECD_Sea_IPCC = list(EDGAR.loc[EDGAR['Comment'].isin(['Domestic Navigation']), 'NFR_Sector'])[0]
            OECD_Sea_IPCCDesc = list(EDGAR.loc[EDGAR['Comment'].isin(['Domestic Navigation']), 'NFR_Description'])[0]

        elif Type_Inventory == "UNFCCC":
            OECD_Air_IPCC = list(UNFCCC.loc[UNFCCC['Comment'].isin(['Domestic Aviation']), 'Code'])[0]
            OECD_Air_IPCCDesc = \
            list(UNFCCC.loc[UNFCCC['Comment'].isin(['Domestic Aviation']), 'Description'])[0]

            OECD_Sea_IPCC = list(UNFCCC.loc[UNFCCC['Comment'].isin(['Domestic Navigation']), 'Code'])[0]
            OECD_Sea_IPCCDesc = \
                list(UNFCCC.loc[UNFCCC['Comment'].isin(['Domestic Navigation']), 'Description'])[0]

        OECD_IPCC = [OECD_Air_IPCC,OECD_Sea_IPCC]
        OECD_Air = pd.DataFrame(OECD_Air)
        if len(OECD_Air)>0:
        
            OECD_Air.columns = OECD_Air.iloc[0]
            OECD_Air = OECD_Air[1:].reset_index(drop=True)

            OECD_Air = OECD_Air[OECD_Air['REF_AREA'] == Inventoryt.loc[0, 'REF_AREA']]

            if len(OECD_Air)>0:

                if 'OBS_VALUE_Alpha' in OECD_Air.columns: OECD_Air.drop('OBS_VALUE_Alpha', axis=1, inplace=True)
                if 'OBS_VALUE' not in OECD_Air.columns:
                    OECD_Air = pd.melt(OECD_Air, id_vars=("REF_AREA","REF_AREA_Mapped","FREQ","MEASURE","UNIT_MEASURE",
                                            "ADJUSTMENT","POLLUTANT","FLIGHT_TYPE","EMISSIONS_SOURCE",
                                            "METHODOLOGY","OBS_STATUS","UNIT_MULT",
                                            "CLASSIFICATION","DECIMALS"),
                            var_name='TIME_PERIOD', value_name='OBS_VALUE')

                OECD_Air = OECD_Air[OECD_Air['TIME_PERIOD'].astype(int).isin(Inventoryt['TIME_PERIOD'].astype(int).unique())]

                OECD_Air['CountryName'] = Inventoryt.loc[0, 'CountryName']

                OECD_Air.loc[OECD_Air['EMISSIONS_SOURCE'].isin(['RES_DOM_OUT', 'RES_INT_FROM', 'RES_INT_TO', 'RES_INT_OUT']),'EMISSIONS_SOURCE'] = 'RES_ABROAD'


                OECD_Air['Source_Code'] =  OECD_Air_IPCC
                OECD_Air['Source_Description'] = OECD_Air_IPCCDesc

                OECD_Air = OECD_Air[['REF_AREA','TIME_PERIOD','POLLUTANT', 'OBS_VALUE',
                                    'CountryName', 'Source_Code', 'Source_Description', 'EMISSIONS_SOURCE']]

                OECD_Air['OBS_VALUE'] = OECD_Air['OBS_VALUE'].fillna(0) / 1000 #000
                OECD_Air = OECD_Air.reset_index(drop=True)
                # Exclude from


                if 'match gases' in Use_OECD:
                #return(Inventoryt['Source_Code'].str[:len(OECD_Air_IPCC)] + Inventoryt['POLLUTANT'])
                    Inventoryt = Inventoryt[~ (Inventoryt['Source_Code'].str[:len(OECD_Air_IPCC)] + Inventoryt['POLLUTANT']).isin(
                        list((OECD_Air['Source_Code'] + OECD_Air['POLLUTANT']).unique()[0]))]

                #else:
                #   Inventoryt = Inventoryt[Inventoryt['Source_Code'].str[:len(OECD_Air.loc[0, 'Source_Code'])]  !=OECD_Air_IPCC]

                Inventoryt = pd.concat([Inventoryt, OECD_Air], ignore_index=True)


        OECD_Sea = pd.DataFrame(OECD_Sea)
        if len(OECD_Sea) > 0:
            OECD_Sea.columns = OECD_Sea.iloc[0]
            OECD_Sea = OECD_Sea[1:].reset_index(drop=True)
            OECD_Sea = OECD_Sea[OECD_Sea['REF_AREA'] == Inventoryt.loc[0, 'REF_AREA']]

            if len(OECD_Sea) > 0:

                if 'OBS_VALUE_Alpha' in OECD_Sea.columns: OECD_Sea.drop('OBS_VALUE_Alpha', axis=1, inplace=True)

                if 'OBS_VALUE' not in OECD_Sea.columns:
                    OECD_Sea =pd.melt(OECD_Sea, id_vars=("REF_AREA","REF_AREA_Mapped","FREQ","MEASURE",
                                            "UNIT_MEASURE","ADJUSTMENT","POLLUTANT","SOURCE",
                                            "VESSEL","OBS_STATUS",
                                            "UNIT_MULT","DECIMALS"),
                            var_name='TIME_PERIOD', value_name='OBS_VALUE')

                OECD_Sea = OECD_Sea[OECD_Sea['TIME_PERIOD'].astype(int).isin(Inventoryt['TIME_PERIOD'].astype(int).unique())]

                OECD_Sea['CountryName'] = Inventoryt.loc[0, 'CountryName']

                OECD_Sea['Source_Code'] = OECD_Sea_IPCC
                OECD_Sea['Source_Description'] = OECD_Sea_IPCCDesc

                OECD_Sea.rename(columns={'VESSEL':'EMISSIONS_SOURCE'}, inplace=True)


                OECD_Sea = OECD_Sea[['REF_AREA', 'TIME_PERIOD', 'POLLUTANT', 'OBS_VALUE',
                                    'CountryName', 'Source_Code', 'Source_Description', 'EMISSIONS_SOURCE']]

                OECD_Sea['OBS_VALUE'] = OECD_Sea['OBS_VALUE'].fillna(0) / 1000 #000
                # Exclude from
                OECD_Sea = OECD_Sea.reset_index(drop=True)

                if 'match gases' in Use_OECD:
                    Inventoryt = Inventoryt[~ (Inventoryt['Source_Code'].str[:len(OECD_Sea_IPCC)] + Inventoryt['POLLUTANT']).isin(
                        list((OECD_Sea['Source_Code'] + OECD_Sea['POLLUTANT']).unique()[0]))]
                else:
                    if 1==2:
                        Inventoryt = Inventoryt[Inventoryt['Source_Code'].str[:len(OECD_Sea.loc[0, 'Source_Code'])] != OECD_Sea_IPCC]

                Inventoryt = pd.concat([Inventoryt, OECD_Sea], ignore_index=True)

    # Step 1.2 Rename the variable=value to 'OBS_VALUE' and convert
    # the variable to numeric

    Inventoryt["OBS_VALUE"] = pd.to_numeric(Inventoryt["OBS_VALUE"])
   # Inventoryt.rename(columns={'value': 'OBS_VALUE'}, inplace=True)
    #Inventoryt.rename(columns={0: 'TIME_PERIOD'}, inplace=True)
    
    # remove the leading "Y_" from TIME_PERIOD

    if 'Y_' in str(Inventoryt.loc[0,'TIME_PERIOD']): #.astype(str) :
        #Inventoryt['TIME_PERIOD'] = Inventoryt['TIME_PERIOD'].str[2:]
        Inventoryt["TIME_PERIOD"] =    Inventoryt["TIME_PERIOD"].str.replace('Y_', '', )

    Inventoryt["TIME_PERIOD"] = pd.to_numeric(Inventoryt["TIME_PERIOD"])
    

    #inventoryt.rename(columns={'variable': 'TIME_PERIOD'}, inplace=True)


    # Group by fossil fuel type (the inventory data distingish between
    # fossil fuel and bio fuel - this split is not needed for the
    # Air Emissions Account and therefore the data are grouped together

    Inventoryt = Inventoryt.groupby(['REF_AREA', 'POLLUTANT', 'CountryName',
                             'Source_Code', 'Source_Description', 'TIME_PERIOD',  'EMISSIONS_SOURCE'])['OBS_VALUE'].sum().reset_index()


    Inventoryt['OBS_VALUE'] =Inventoryt['OBS_VALUE'].fillna(0) / 1000


  #  Inventoryt['TIME_PERIOD'] = Inventoryt['TIME_PERIOD'].astype('int')

    # Step 2:  Merge the inventory Data with the ISIC Allocation Table

    # Step 2.1 Read in the Allocation Factors


    if 'Level' in af0.columns: af0.drop('Level', axis=1, inplace=True)
    af0 = af0[1:]
    
    #Standarsize allocation factor to 100
    variable_names = list(af0.drop(columns=['POLLUTANT' , 'Source_Code' ,  'Source_Description' , 'Check']))
    
    #run twice for accuracy
    for i0 in range(0,1):
        af0['Check'] = af0[variable_names].sum(axis=1)
        af0.loc[af0['Check'] == 0 | af0['Check'].isna(), 'Check'] = 100

        for i in variable_names:
        #    af0[i] =1
            af0[i] = 100 * af0[i] / af0['Check']
         #   return (af0)

    #Duplicate for missing POLLUTANT
    af_Temp = af0[(af0['POLLUTANT']=="") | (af0['POLLUTANT']==0) | af0['POLLUTANT'].isna()]
    if not af_Temp.empty:        
        af0=af0[ ((af0['POLLUTANT']!="") & (af0['POLLUTANT']!=0)) & (af0['POLLUTANT'].notna())]
        for i_POLLUTANT in POLLUTANT_list:
            af_Temp['POLLUTANT']=i_POLLUTANT
            af0 = pd.concat([af0, af_Temp], ignore_index = True)

    if 1==2:
        TIME_PERIODs = list(range( min(Inventoryt["TIME_PERIOD"]),   max(Inventoryt["TIME_PERIOD"])))
        for i in TIME_PERIODs:
            if i==  min(Inventoryt["TIME_PERIOD"]):
                af1 = af0.copy()
                af1['TIME_PERIOD'] = i
            else:            
                af2 = af0.copy()
                af2['TIME_PERIOD'] = i
                af1 = pd.concat([af1,af2], ignore_index=True)

    af0.drop(columns='Source_Description', inplace=True)


    # Step 2.2 Merge the correspondence table with the GHG table by POLLUTANT and Source_Code.

    Inventoryt.drop(columns='Source_Description', inplace=True)

    Account_GHG = pd.merge(Inventoryt,af0,  on=['POLLUTANT', 'Source_Code'], how='left')

    #af1.drop(columns=['POLLUTANT', 'Source_Code', 'Check', 'TIME_PERIOD'], inplace=True)

    # Activity

    variable_names = list(Account_GHG.drop(columns=['REF_AREA', 'CountryName', 'POLLUTANT', 'Source_Code', 'Check', 'TIME_PERIOD', 'OBS_VALUE', 'EMISSIONS_SOURCE']))

    #variable_names=variable_names[s for s in variable_names if  s in ['REF_AREA', 'CountryName', 'POLLUTANT', 'Source_Code', 'Check', 'TIME_PERIOD', 'OBS_VALUE']]

    Account_GHG = Account_GHG.fillna(0)

    #Account_GHG['OBS_VALUE'] = pd.to_numeric(Account_GHG['OBS_VALUE'])

    for i in variable_names:
        Account_GHG[i] = Account_GHG[i] * Account_GHG['OBS_VALUE']/100

    Account_GHG.drop(columns=['OBS_VALUE','Check'], inplace=True)

    Account_GHG = pd.melt(Account_GHG,id_vars=('REF_AREA', 'CountryName', 'POLLUTANT', 'Source_Code', 'TIME_PERIOD', 'EMISSIONS_SOURCE'),
                      var_name='Activity', value_name='OBS_VALUE')
    
    Account_GHG = Account_GHG[Account_GHG['OBS_VALUE']!=0]

    # handle level and description

    if IPCC_Level=='Section': 
        if Type_Inventory=="EDGAR": 
            Account_GHG = Account_GHG.merge(right=EDGAR.rename(columns={'NFR_Sector':'Source_Code', 'CRT_Sector':'Sector'})[['Source_Code','Sector']],  
                               on='Source_Code',  how='left') 
        elif Type_Inventory=="UNFCCC": 
            Account_GHG = Account_GHG.merge(right=UNFCCC.rename(columns={'Code':'Source_Code'})[['Source_Code','Sector']],  
                               on='Source_Code' , how='left')

        Account_GHG['Source_Code']=Account_GHG['Sector']
        Account_GHG.drop(columns=['Sector'], inplace=True)
        Account_GHG = Account_GHG.merge(right=UNFCCC.rename(columns={'Description': 'Source_Description', 'Code':'Source_Code'})[['Source_Code','Source_Description']],  
                           on='Source_Code' , how='left')

        #Adjusted Source_Code Sector
        OECD_Air_IPCC = list(UNFCCC.loc[UNFCCC['Comment'].isin(['Domestic Aviation']), 'Sector'])[0]
        OECD_Air_IPCCDesc = \
            list(UNFCCC.loc[UNFCCC['Code'].isin([OECD_Air_IPCC]), 'Description'])[0]

        OECD_Sea_IPCC = list(UNFCCC.loc[UNFCCC['Comment'].isin(['Domestic Navigation']), 'Sector'])[0]
        OECD_Sea_IPCCDesc = \
            list(UNFCCC.loc[UNFCCC['Code'].isin([OECD_Air_IPCC]), 'Description'])[0]
        OECD_IPCC = [OECD_Air_IPCC, OECD_Sea_IPCC]

    else:
    #Add description
        if Type_Inventory=="EDGAR": 
            Account_GHG = Account_GHG.merge(right=EDGAR.rename(columns={'NFR_Description': 'Source_Description' , 'NFR_Sector':'Source_Code'})[['Source_Code','Source_Description']],  
                               on='Source_Code',  how='left') 
        elif Type_Inventory=="UNFCCC": 
            Account_GHG = Account_GHG.merge(right=UNFCCC.rename(columns={'Description': 'Source_Description', 'Code':'Source_Code'})[['Source_Code','Source_Description']],  
                               on='Source_Code' , how='left')

    Activity.reset_index(drop=True, inplace=True)
    if Activity_Level == 'Section':
        #Add Code_Sector to Activity
        Activity2 = Activity.loc[Activity['Level1'].notna(), ['Code', 'Level1']]

        Activity = Activity.merge(right=Activity2.rename(columns={'Level1':'Code_Sector', 'Code':'Level2' }),
                                on='Level2', how='left')

        Activity.loc[(Activity['Code_Sector'].isna()) & (Activity['Ignore_Total'].isna()), 'Code_Sector'] = Activity.loc[(Activity['Code_Sector'].isna()) & (Activity['Ignore_Total'].isna()), 'Level1']
        Activity.loc[(Activity['Code_Sector'].isna()) & (Activity['Ignore_Total'].isna()), 'Code_Sector'] = Activity.loc[
            (Activity['Code_Sector'].isna()) & (Activity['Ignore_Total'].isna()), 'Level2']
        Activity.loc[(Activity['Code_Sector'].isna()) & (Activity['Ignore_Total'].isna()), 'Code_Sector'] = Activity.loc[
            (Activity['Code_Sector'].isna()) & (Activity['Ignore_Total'].isna()), 'Code']

        Account_GHG = Account_GHG.merge(right=Activity.rename(columns={'Code': 'Activity'})[['Activity','Code_Sector']],
                               on='Activity' , how='left')
        Account_GHG['Activity']=Account_GHG['Code_Sector']
        Account_GHG.drop(columns=['Code_Sector'], inplace=True)

    Account_GHG = Account_GHG.merge(right=Activity.rename(columns={'Code': 'Activity'})[['Activity','Description']],
                           on='Activity' , how='left')

    # Work out Bridging item

    if (OECD_IPCC  is not None) & (len(Account_GHG['EMISSIONS_SOURCE'].unique())>2):
        #
        Account_GHG1 = Account_GHG[Account_GHG['Source_Code'].isin(OECD_IPCC)]
        Account_GHG1 =Account_GHG1.fillna('Zach')
        Account_GHG1 =Account_GHG1.pivot_table(index=('REF_AREA', 'CountryName', 'POLLUTANT', 'Source_Code', 'Source_Description', 'Activity', 'Description',
               'TIME_PERIOD'), columns='EMISSIONS_SOURCE', values='OBS_VALUE', aggfunc=np.sum) \
            .replace('Zach', None) \
            .reset_index()

        Account_GHG = Account_GHG[Account_GHG['EMISSIONS_SOURCE'].isin(['Zach'])]
        variable_names = list(Account_GHG1.drop(columns=['REF_AREA', 'CountryName', 'POLLUTANT', 'Source_Code', 'Source_Description',
                                                     'Activity', 'Description','TIME_PERIOD', 'Zach']))

        Account_GHG1['Zach'] = Account_GHG1['Zach'].fillna(0)

        for i in list(variable_names):
            Account_GHG1[i] = Account_GHG1[i].fillna(0)

            if i == 'ALL_VESSELS':
                Account_GHG2 = Account_GHG1[Account_GHG1['Source_Code'] == OECD_Sea_IPCC]
                Account_GHG2['OBS_VALUE'] = Account_GHG2[i] - Account_GHG2['Zach']
                Account_GHG2['EMISSIONS_SOURCE'] = 'ALL_VESSELS'

                Account_GHG3 = Account_GHG2[Account_GHG2['OBS_VALUE'] > 0]
                if len(Account_GHG3) > 0:
                    Account_GHG3['Source_Code'] = 'ALL_VESSELS'
                    Account_GHG3['Source_Description'] = 'ALL_VESSELS International'
                    Account_GHG3 = Account_GHG3.drop(columns=variable_names)
                    Account_GHG = pd.concat([Account_GHG, Account_GHG3], ignore_index=True)
                    #Bridging items
                    if ('NRA-WATER' in Activity['Code']) & ('NATRESABROAD' in Activity['Code']):
                        if 'NRA-WATER' in Activity['Code']:
                            Account_GHG3['Activity'] = 'NRA-WATER'
                            Account_GHG3['Description'] = list(Activity.loc[Activity['Code'] == 'NRA-WATER', 'Description'])[0]
                        elif 'NATRESABROAD' in Activity['Code']:
                            Account_GHG3['Activity'] = 'NATRESABROAD'
                            Account_GHG3['Description'] = list(Activity.loc[Activity['Code'] == 'NATRESABROAD', 'Description'])[0]

                        Account_GHG = pd.concat([Account_GHG, Account_GHG3], ignore_index=True)

                Account_GHG3 = Account_GHG2[Account_GHG2['OBS_VALUE'] < 0]
                if len(Account_GHG3) > 0:
                    Account_GHG3 = Account_GHG3.drop(columns=variable_names +['Zach'])
                    # To reduce allocation to resident
                    Account_GHG = pd.concat([Account_GHG, Account_GHG3], ignore_index=True)

                    # To add allocation non-resident
                    Account_GHG3['OBS_VALUE'] = - Account_GHG3['OBS_VALUE']

                    if ('NRT-WATER' in list(Activity['Code'])) | ('NONRESTERR' in list(Activity['Code'])):
                        if 'NRT-WATER' in list(Activity['Code']):
                            Account_GHG3['Activity'] = 'NRT-WATER'
                            Account_GHG3['Description'] = list(Activity.loc[Activity['Code'] == 'NRT-WATER', 'Description'])[0]

                        elif 'NONRESTERR' in list(Activity['Code']):
                            Account_GHG3['Activity'] = 'NONRESTERR'
                            Account_GHG3['Description'] = list(Activity.loc[Activity['Code'] == 'NONRESTERR', 'Description'])[0]

                        Account_GHG = pd.concat([Account_GHG, Account_GHG3], ignore_index=True)

            elif i == 'RES_DOM_IN':
                Account_GHG2 = Account_GHG1[Account_GHG1['Source_Code'] == OECD_Air_IPCC]
                Account_GHG2['OBS_VALUE'] = Account_GHG2[i] - Account_GHG2['Zach']
                Account_GHG2['EMISSIONS_SOURCE'] = 'RES_DOM_IN'

                Account_GHG3 = Account_GHG2[Account_GHG2['OBS_VALUE'] > 0]
                if len(Account_GHG3) > 0:
                    Account_GHG3['Source_Code'] = 'RES_DOM_IN'
                    Account_GHG3['Source_Description'] = 'Domestic Aviation Ajustment'
                    Account_GHG3 = Account_GHG3.drop(columns=variable_names+['Zach'])
                    Account_GHG = pd.concat([Account_GHG, Account_GHG3], ignore_index=True)

                    # To add allocation non-resident
                    Account_GHG3['OBS_VALUE'] = -Account_GHG3['OBS_VALUE']

                    if 'OTHER' in list(Activity['Code']) :
                        Account_GHG3['Activity'] = 'OTHER'
                        Account_GHG3['Description'] = list(Activity.loc[Activity['Code']=='OTHER', 'Description'])[0]

                        Account_GHG = pd.concat([Account_GHG, Account_GHG3], ignore_index=True)

                Account_GHG3 = Account_GHG2[Account_GHG2['OBS_VALUE'] < 0]
                if len(Account_GHG3) > 0:
                    Account_GHG3 = Account_GHG3.drop(columns=variable_names+['Zach'])
                    # To reduce allocation to resident
                    Account_GHG = pd.concat([Account_GHG, Account_GHG3], ignore_index=True)

                    # To add allocation non-resident
                    Account_GHG3['OBS_VALUE'] = -Account_GHG3['OBS_VALUE']

                    if ('NRT-AIR' in list(Activity['Code'])) | ('NONRESTERR' in list(Activity['Code'])):
                        if 'NRT-AIR' in list(Activity['Code']):
                            Account_GHG3['Activity'] = 'NRT-AIR'
                            Account_GHG3['Description'] = list(Activity.loc[Activity['Code']=='NRT-AIR', 'Description'])[0]
                        elif 'NONRESTERR' in list(Activity['Code']):
                            Account_GHG3['Activity'] = 'NONRESTERR'
                            Account_GHG3['Description'] = list(Activity.loc[Activity['Code']=='NONRESTERR', 'Description'])[0]

                        Account_GHG = pd.concat([Account_GHG, Account_GHG3], ignore_index=True)

            elif i == 'RES_ABROAD':

                Account_GHG2 = Account_GHG1[Account_GHG1['Source_Code'] == OECD_Air_IPCC]
                Account_GHG2['OBS_VALUE'] = Account_GHG2[i]
                Account_GHG2['EMISSIONS_SOURCE'] = 'RES_ABROAD'
                Account_GHG2['Source_Code'] = 'RES_ABROAD'
                Account_GHG2['Source_Description'] = 'International Aviation Ajustment'
                Account_GHG2 = Account_GHG2.drop(columns=variable_names+['Zach'])

                Account_GHG = pd.concat([Account_GHG, Account_GHG2], ignore_index=True)
                # Bridging items
                if ('NRA-AIR' in list(Activity['Code'])) | ('NATRESABROAD' in list(Activity['Code'])):
                    if 'NRA-AIR' in list(Activity['Code']):
                        Account_GHG2['Activity'] = 'NRA-AIR'
                        Account_GHG2['Description'] = list(Activity.loc[Activity['Code'] == 'NRA-AIR', 'Description'])[0]
                    elif 'NATRESABROAD' in list(Activity['Code']):
                        Account_GHG2['Activity'] = 'NATRESABROAD'
                        Account_GHG2['Description'] = list(Activity.loc[Activity['Code'] == 'NATRESABROAD', 'Description'])[0]

                    Account_GHG = pd.concat([Account_GHG, Account_GHG2], ignore_index=True)

    Account_GHG = Account_GHG[~(Account_GHG['OBS_VALUE']==0)]

    # Calculate TOTAL
    #Air emissions account

    Activity.loc[Activity['Sign'].isna(),'Sign']=1
    Activity.loc[Activity['Sign']=='-', 'Sign'] = -1
    Account_GHG = Account_GHG.merge(right=Activity.rename(columns={'Code': 'Activity'})[['Activity','Sign']], on='Activity', how='left')
    Account_GHG['OBS_VALUE2'] = Account_GHG['OBS_VALUE'] * Account_GHG['Sign']

    # TOTAL Air Emission Accounts

    if 'AEA-TOTAL' in list(Activity['Code']):
        Account_GHG1  = Account_GHG[#(Account_GHG['Activity']!='AEA-TOTAL') &
                            (Account_GHG['Activity'].isin(Activity.iloc[range(Activity.index[Activity['Code']=='AEA-TOTAL'][0])]['Code']))]
        Account_GHG1['Source_Code']='Total AEA'
        Account_GHG1['Source_Description'] = 'Total AEA'

        Account_GHG1['Activity'] = 'AEA-TOTAL'
        Account_GHG1['Description'] = list(Activity.loc[Activity['Code'] == 'AEA-TOTAL', 'Description'])[0]

        Account_GHG1['EMISSIONS_SOURCE'] = 'Zach'

        Account_GHG = pd.concat([Account_GHG, Account_GHG1], ignore_index=True)

        # TOTAL Inventories

        if 'INV-TOTAL' in list(Activity['Code']):
            Account_GHG1 = Account_GHG[(Account_GHG['Activity']!='INV-TOTAL') &
                                (Account_GHG['Activity'].isin(
                Activity.iloc[range(Activity.index[Activity['Code'] == 'AEA-TOTAL'][0]  ,
                                    Activity.index[Activity['Code'] == 'INV-TOTAL'][0] )]['Code']))]

            Account_GHG1['Source_Code'] = 'Total Inventories'
            Account_GHG1['Source_Description'] = 'Total Inventories'

            Account_GHG1['Activity'] = 'INV-TOTAL'
            Account_GHG1['Description'] = list(Activity.loc[Activity['Code'] == 'INV-TOTAL', 'Description'])[0]

            Account_GHG1['EMISSIONS_SOURCE'] = 'Zach'

            Account_GHG = pd.concat([Account_GHG, Account_GHG1], ignore_index=True)

    Account_GHG=Account_GHG.groupby(['REF_AREA', 'CountryName', 'POLLUTANT', 'Source_Code', 'Source_Description','Activity', 'Description',
                             'TIME_PERIOD'],  as_index=False)['OBS_VALUE'].sum()#.reset_index()
    Account_GHG['rank']=1

    # Add total GHG 
    Account_GHG1=Account_GHG.copy()
    Account_GHG1['POLLUTANT'] = "GHG"
    
    Account_GHG1=Account_GHG1.groupby(['REF_AREA', 'CountryName',  'POLLUTANT', 'Source_Code', 'Source_Description','Activity', 'Description',
                               'TIME_PERIOD'],  as_index=False)['OBS_VALUE'].sum()#.reset_index()
    Account_GHG1['rank']=2
    
    Account_GHG = pd.concat([Account_GHG,Account_GHG1], ignore_index=True)

    #Default is         'Megatonnes CO2Eq'
    if Unit =='Gigatonnes CO2Eq':
        Account_GHG['OBS_VALUE'] = Account_GHG['OBS_VALUE'] /1000
    elif Unit == 'Thousand tonnes CO2Eq':
        Account_GHG['OBS_VALUE'] = Account_GHG['OBS_VALUE'] * 1000
    elif Unit == 'Tonnes CO2Eq':
        Account_GHG['OBS_VALUE'] = Account_GHG['OBS_VALUE'] * 1000000


    Account_GHG =Account_GHG \
        .fillna('Zach') \
        .pivot_table(index=('rank','REF_AREA', 'CountryName', 'POLLUTANT', 'Source_Code', 'Source_Description','Activity',
                                  'Description'), columns='TIME_PERIOD', values='OBS_VALUE', aggfunc=np.sum) \
        .replace('Zach', None) \
        .reset_index()
    
    Account_GHG.drop(columns=['rank'], inplace=True)
    Account_GHG = Account_GHG.reset_index(drop=True)

    if 1==2:
        # Add upper level of activity
        Activity_ = Activity.copy()
        # return(list(Activity_.columns))

        if not 'Level' in Activity_.columns:
            Activity_['Level'] = 1

            Activity_.loc[~Activity_['Level1'].isna(), 'Level'] = 2
            Activity_.loc[~Activity_['Level2'].isna(), 'Level'] = 3

        
        Account_GHG.rename(columns={'Source_Code': 'Source_Temp',
                                'Activity': 'Source_Code',
                                'Description': 'Source_Description',
                                'POLLUTANT':'POLLUTANT'}, inplace=True)


        Account_GHG = F_Aggregation_Consistent_Level(Account_GHG, 'Source_Code', Activity_, False)

        Account_GHG.rename(columns={'Source_Temp': 'Source_Code',
                                'Source_Code': 'Activity',
                                'Source_Description': 'Description',
                                'POLLUTANT': 'POLLUTANT'}, inplace=True)

    return (Account_GHG)
   


@xw.func
def GID(Output_Source_Activity, Activity):

    Output_Source_Activity=pd.DataFrame(Output_Source_Activity)
    Output_Source_Activity.columns = Output_Source_Activity.iloc[0]
    Output_Source_Activity = Output_Source_Activity[1:]
    #Remove GHG Output_Source_Activity[Output_Source_Activity['POLLUTANT']== POLLUTANT].reset_index(drop=True)
    Output_Source_Activity=Output_Source_Activity[Output_Source_Activity['POLLUTANT']!='GHG']
    
    Activity=pd.DataFrame(Activity)
    Activity.columns = Activity.iloc[0]
    Activity = Activity[1:]

    Output_Source_Activity0 =  Output_Source_Activity.copy()
    # Add upper level of activity
    Activity_ = Activity.copy()
    # return(list(Activity_.columns))

    if not 'Level' in Activity_.columns:
        Activity_['Level'] = 1

        Activity_.loc[~Activity_['Level1'].isna(), 'Level'] = 2
        Activity_.loc[~Activity_['Level2'].isna(), 'Level'] = 3

    Source_cl = Output_Source_Activity[['Source_Code', 'Source_Description']].drop_duplicates()

    Output_Source_Activity_Agg = Output_Source_Activity.copy()
    
    if 'Source_Description' in list(Output_Source_Activity_Agg.columns): 
        Output_Source_Activity_Agg = Output_Source_Activity_Agg.drop('Source_Description', axis=1)


    Output_Source_Activity_Agg = Output_Source_Activity_Agg.rename(columns={'Source_Code': 'Source_Temp',
                            'Activity': 'Source_Code',
                            'Description': 'Source_Description',
                            'POLLUTANT':'POLLUTANT'}) #, inplace=True)

    
    Output_Source_Activity_Agg = F_Aggregation_Consistent_Level(Data=Output_Source_Activity_Agg,
        Source_Classif= 'Source_Code',
        Hierar_Class= Activity_,
       # Selection='Lowest Level',
        Check_Heading=False,
        Check_Consistency=False,
        If_EDGAR_Stop=False)

    
    
    Output_Source_Activity_Agg.rename(columns={'Source_Temp': 'Source_Code',
                            'Source_Code': 'Activity',
                            'Source_Description': 'Description'}, inplace=True)

    Output_Source_Activity_Agg = Output_Source_Activity_Agg.merge( Source_cl, on='Source_Code', how='left')
    
    Output_Source_Activity = Output_Source_Activity.fillna(0)
    Output_Source_Activity_Agg = Output_Source_Activity_Agg.fillna(0)

    Output_Source_Activity = pd.melt(Output_Source_Activity,id_vars=('REF_AREA', 'CountryName', 'POLLUTANT',
                                                         'Source_Code', 'Source_Description','Activity', 'Description'),
                      var_name='TIME_PERIOD', value_name='OBS_VALUE')

    Output_Source_Activity_Agg = pd.melt(Output_Source_Activity_Agg.drop(columns={'Source_Code', 'Source_Description'}),
                               id_vars=('REF_AREA', 'CountryName', 'POLLUTANT', # 'Source_Code', 'IPCC_Desc',
                                        'Activity', 'Description'),
                               var_name='TIME_PERIOD', value_name='OBS_VALUE')
   
    Output_Source_Activity0=Output_Source_Activity.copy()
    Output_Source_Activity0_Agg = Output_Source_Activity_Agg.copy()

    Output_Source_Activity=Output_Source_Activity.groupby(['REF_AREA', 'CountryName', 'POLLUTANT', 'Activity', 'Description', 'TIME_PERIOD'],
                                              as_index=False)['OBS_VALUE'].sum().reset_index()
    Output_Source_Activity_Agg=Output_Source_Activity_Agg.groupby(['REF_AREA', 'CountryName', 'POLLUTANT', 'Activity', 'Description', 'TIME_PERIOD'],
                                                      as_index=False)['OBS_VALUE'].sum().reset_index()

    Output_Source_Activity['Rank']=1
    Output_Source_Activity_Agg['Rank']=1
    
    #Total by POLLUTANT
    Output_Source_Activity1=Output_Source_Activity0.groupby(['REF_AREA', 'CountryName', 'POLLUTANT','TIME_PERIOD'],  as_index=False)['OBS_VALUE'].sum().reset_index()
    Output_Source_Activity1['Activity']="Total"
    Output_Source_Activity1['Description']="Total"
    Output_Source_Activity1['Rank']=2
    Output_Source_Activity_Agg = pd.concat([Output_Source_Activity_Agg,Output_Source_Activity1], ignore_index=True)
 
    #Total by Activty
    Output_Source_Activity1=Output_Source_Activity0_Agg.groupby(['REF_AREA', 'CountryName', 'Activity','Description', 'TIME_PERIOD'],  as_index=False)['OBS_VALUE'].sum().reset_index()
    Output_Source_Activity1['POLLUTANT']="GHG"
    Output_Source_Activity1['Rank']=3
    Output_Source_Activity_Agg = pd.concat([Output_Source_Activity_Agg,Output_Source_Activity1], ignore_index=True)

    #Total by POLLUTANT and Activty
    Output_Source_Activity1=Output_Source_Activity0.groupby(['REF_AREA', 'CountryName',  'TIME_PERIOD'],  as_index=False)['OBS_VALUE'].sum().reset_index()
    Output_Source_Activity1['POLLUTANT']="GHG"
    Output_Source_Activity1['Activity']="Total"
    Output_Source_Activity1['Description']="Total"
    Output_Source_Activity1['Rank']=4
    Output_Source_Activity_Agg = pd.concat([Output_Source_Activity_Agg,Output_Source_Activity1], ignore_index=True)

    #Output_Source_Activity_Agg = Output_Source_Activity_Agg.groupby(['Rank', 'REF_AREA', 'CountryName', 'POLLUTANT', 'Activity', 'Description', 'TIME_PERIOD']).agg({'OBS_VALUE': 'sum'}).reset_index()
    Output_Source_Activity_Agg = Output_Source_Activity_Agg \
        .fillna('Zach') \
        .pivot_table(
        index=('Rank', 'REF_AREA', 'CountryName', 'POLLUTANT', 'Activity', 'Description'),
        columns='TIME_PERIOD',
        values='OBS_VALUE',
        aggfunc=np.sum) \
        .replace('Zach', None) \
        .reset_index()

    #Output_Source_Activity1=pd.DataFrame(Output_Source_Activity)
    #return( Output_Source_Activity1.columns)
    #return(Output_Source_Activity)
    #Output_Source_Activity=Output_Source_Activity.drop(Output_Source_Activity.columns[1], axis=1)
    Output_Source_Activity_Agg.drop(columns=['Rank'], inplace=True)
    
    return(Output_Source_Activity_Agg)

##Check consistency
@xw.func
def F_Aggregation_Consistent_Level(Data,
                                   Source_Classif, #UNFCCC  code adjustment to add a . For EDGAR, No aggregation is acarries out
                                    Hierar_Class,
                                   #Selection = 'Lowest Level' ,
                                   Check_Heading=True,
                                   Check_Consistency = False,
                                   If_EDGAR_Stop = False,
                                   Correct_Categories=True):

    Key0 = ['POLLUTANT', 'REF_AREA' ] #, 'Source_Temp', 'Source_Description'
    Code0 = 'Source_Code'
    Folder = None
    Text_to_Identify_Lowest_Level = "Most detailed Component"
    Tolerance_Percent0 = 50
    round_digit0 = 2

     #True
    First_Period_Check_Consistency = None
    Level_Exclude_Deletion_Min = 0
    Prefix_File_Name = "Data_"
    Run_By_Country = False
    Run_By_Period = False

    Data_Keep_ = None
    Data_Discrepancy_ = None

    Source_Classif = str(Source_Classif)

    Data = pd.DataFrame(Data)
    #return ('Data')
    if Check_Heading:
        Data.columns = Data.iloc[0]
        Data = Data[1:]

    Hierar_Class = pd.DataFrame(Hierar_Class)
    if Check_Heading:
        Hierar_Class.columns = Hierar_Class.iloc[0]
        Hierar_Class = Hierar_Class[1:]


    #Write a code to remove UNFCCC_
    if 'UNFCCC_' in list(Hierar_Class.columns)[0]:
        Hierar_Class.columns = [s[7:] if 'UNFCCC_' in s else s  for s in list(Hierar_Class.columns)]   #['Rank', 'Code', 'Description', 'Category', 'Level', 'Level5', 'Level4', 'Level3', 'Level2', 'Level1', 'Sector']

    if "Rank" not in Hierar_Class.columns: Hierar_Class['Rank'] = 'Zach'


    if (Source_Classif == "UNFCCC"):
        # Add . to categories with one digit

        Data['IPCC_count'] = Data['Source_Code'].astype(str).str.len()

        Data.loc[(Data['IPCC_count']==1) |
                 ((Data['Source_Code'].astype(str).str[2]=='0') & (Data['IPCC_count']==3)), 'Source_Code'] = Data.loc[(Data['IPCC_count']==1) |
                 ((Data['Source_Code'].astype(str).str[2]=='0') & (Data['IPCC_count']==3)), 'Source_Code'].astype(str).str[0] + "."
        Data.drop(columns=['IPCC_count'], inplace=True)
        
        Hierar_Class['IPCC_count'] = Hierar_Class['Code'].astype(str).str.len()

        Hierar_Class.loc[(Hierar_Class['IPCC_count']==1) |
                 ((Hierar_Class['Code'].astype(str).str[2]=='0') & (Hierar_Class['IPCC_count']==3)), 'Code'] = Hierar_Class.loc[(Hierar_Class['IPCC_count']==1) |
                 ((Hierar_Class['Code'].astype(str).str[2]=='0') & (Hierar_Class['IPCC_count']==3)), 'Code'].astype(str).str[0] + "."
        Hierar_Class.drop(columns=['IPCC_count'], inplace=True)


    #Convert obsTime into numeric   

    Data.loc[Data['POLLUTANT'].isin(["GWP_100_AR4_N2O", 'N2O']), 'POLLUTANT'] = "N2O"
    Data.loc[Data['POLLUTANT'].isin(["GWP_100_AR4_CH4", 'CH4']), 'POLLUTANT'] = "CH4"
    Data.loc[Data['POLLUTANT'] == "CO2", 'POLLUTANT'] = "CO2"
    Data.loc[Data['POLLUTANT'].isin(["GWP_100_AR4_F-gases", "F-gases"]), 'POLLUTANT'] = "F-gases"

    #Exclude Total GHG
    Data = Data[Data['POLLUTANT'] != 'GHG']

    Data_columns = list(Data.columns)

    #'REF_AREA	CountryName	POLLUTANT	Activity	Description	2024	Source_Code	Source_Description
    Data_columns_Missing  =  [x for x in ['CountryRegion', 'FossilType', 'Source_Description',
                  'IPCC_annex', 'Data_Source', 'Source_Temp']
      if x not in Data.columns]

    if len(Data_columns_Missing)>0:
        for i_Dim in Data_columns_Missing:
            Data[i_Dim] = 'Zach'
    
    Data = pd.melt(Data, id_vars=['Data_Source',
                                  'IPCC_annex',
                                  'CountryRegion',
                                  'REF_AREA',
                                  'CountryName',
                                  'POLLUTANT',
                                  'Source_Code',
                                  'Source_Description',
                                  'FossilType',
                                  'Source_Temp'
                                  ],
                   var_name='obsTime', value_name='obsValue')

     
    # Correct TIME_PERIOD
    Data['obsTime'] = Data['obsTime'].replace('Y_','')

    Data['obsTime'] = pd.to_numeric(Data['obsTime'])

    if Check_Heading: Data = Data[Data['FossilType']=='fossil']
    
    if Source_Classif == 'EDGAR':
        #Data['Selection'] = Text_to_Identify_Lowest_Level
        Data.insert(0, 'Info', Text_to_Identify_Lowest_Level) #Data['Selection'] = Text_to_Identify_Lowest_Level
        #Write to convert pivot_wider

        if If_EDGAR_Stop:
            Data = (Data \
                    .fillna('Zach') \
                    .pivot_table(columns ='obsTime',
                        index=['Info',
                                   'Data_Source',
                                   'IPCC_annex',
                                   'CountryRegion',
                                   'REF_AREA',
                                   'CountryName',
                                   'POLLUTANT',
                                   'Source_Code',
                                   'Source_Description',
                                   'FossilType' #,
                                 # 'Source_Temp',
                                  #'Source_Description'
                                 ],
                        values='obsValue',
                        aggfunc=np.sum)) \
                    .replace('Zach', None)
            return (Data)

    

    #Data=Data.rename(columns={'REF_AREA': 'REF_AREA'})

    #Convert obsTime into numeric

    #Data = Data.reset_index(drop=True).to_string(index=False) #.to_dict(orient='records')
    Data['obsValue'] = Data['obsValue'].where(Data['obsValue'].notna() & (Data['obsValue'] != 0), None)
    Data_ = Data[Data['obsValue'].notnull()].reset_index(drop=True)
    

    if Check_Consistency and First_Period_Check_Consistency is not None:
        Iter_Consistency_Period = ['After_First_Period', 'Before_First_Period']
    else:
        Iter_Consistency_Period = ['No_Condition']

    for i_Const_Period in Iter_Consistency_Period:

        Data_0 = Data_.copy()

        if i_Const_Period == 'After_First_Period':
            Data_0 = Data_0[Data_0['obsTime'] >= First_Period_Check_Consistency]
        elif i_Const_Period == 'Before_First_Period':
            Data_0 = Data_0[Data_0['obsTime'] < First_Period_Check_Consistency]
            Check_Consistency = False
            Folder = None
            Run_By_Country = False
            Run_By_Period = True

        List_Country = sorted(Data_0['REF_AREA'].unique()) if Run_By_Country else ['']

        for i_ISO in List_Country:

            if '' in List_Country:
                i_ISO = sorted(Data_0['REF_AREA'].unique())

            Data_00 = Data_0[Data_0['REF_AREA'].isin(i_ISO)].copy()

            if Data_00.shape[0] == 0:
                continue

            List_Period = sorted(Data_00['obsTime'].unique()) if Run_By_Period else ['']

            for i_obsTime in List_Period:

                if '' in List_Period:
                    i_obsTime = sorted(Data_00['obsTime'].unique())

                Data = Data_00[Data_00['obsTime'].isin(i_obsTime)].copy()

                if  '' not  in Key0:
                    Text0 = f'Data.rename(columns={{"{Code0}": "Code"}})' #.assign(Key=Data[{" , ".join(Key0)}])'

                    Data = eval(Text0)

                    Data = Data.rename(columns={"Source_Code": "Code"})
                    for i_Key in Key0:
                        if i_Key == Key0[0]:
                            Data['Key'] = Data[i_Key]
                        else:
                            Data['Key'] = Data['Key'] + Data[i_Key]

                    Data0 = Data


                Data = Data.groupby(['Key', 'Code', 'obsTime']).agg({'obsValue': 'sum'}).reset_index()

                Data['obsValueOld'] = Data['obsValue']

                Data_Discrepancy = None

                #bring level

                Data = Data.merge(Hierar_Class[['Code', 'Level']],
                                  on='Code', how='left')

                Data = Data[Data['Level'].notna()]

                Data_Keep = Data[Data['Level'] == Data['Level'].max()].copy()

                Data_Keep['Info'] = Text_to_Identify_Lowest_Level

                if Data['Level'].max() > 1:

                    for i in range(int(Data['Level'].max()) - 1, -1, -1):

                        if f'Level{i}' not in Hierar_Class.columns:
                            continue

                        Hierar_Class0 = Hierar_Class[[f'Level{i}', 'Code']].rename(columns={f'Level{i}': 'LevelXX'})

                        Lower_Code = pd.concat([Hierar_Class0.loc[~Hierar_Class0['LevelXX'].isna(),'Code'],
                            Hierar_Class.loc[Hierar_Class['Level'] == (i+1), 'Code']]).unique()

                        Higher_Code = pd.concat([Hierar_Class0.loc[~Hierar_Class0['LevelXX'].isna(), 'LevelXX'],
                                                Hierar_Class.
                                                rename(columns={'Code' : 'LevelXX' }).
                                                loc[Hierar_Class['Level'] == i , 'LevelXX']]).unique()

                        # Add missing lower level
                        Temp_Existing_Code = Data_Keep[~Data_Keep['Code'].isin(Lower_Code)] #.copy()
                        Temp_Existing_Code['Key_Code'] = Temp_Existing_Code['Key'].astype(str) + Temp_Existing_Code['Code'].astype(str)

                        Data_Keep = pd.concat([
                            Data_Keep,
                            Data[(Data['Code'].isin(set(Lower_Code) - set(Data_Keep['Code'].unique()))) &
                                 ( ~(Data['Key'].astype(str) + Data['Code'].astype(str)).isin(
                                Temp_Existing_Code['Key_Code'].unique()))]
                        ])

                        Data_Upper_Aggregation = Data_Keep[Data_Keep['Code'].isin(Lower_Code)].copy()
                        Data_Upper_Aggregation = Data_Upper_Aggregation.merge(
                            Hierar_Class[[f'Level{i}', 'Code']], on='Code', how='left')
                        Data_Upper_Aggregation['Code'] = Data_Upper_Aggregation[f'Level{i}']
                        Data_Upper_Aggregation = Data_Upper_Aggregation[Data_Upper_Aggregation['Code'].notna()] \
                            .groupby(['Key', 'Code', 'obsTime']).agg({
                                'obsValue': 'sum',
                                'obsValueOld': 'sum'
                            }).reset_index() \
                            .merge(
                                    Hierar_Class[['Level', 'Code']], on='Code', how='left'
                                )

                        #return(Data_Upper_Aggregation)


                        Data_Keep = Data_Keep[~(Data_Keep['Key'].astype(str) + Data_Keep['Code'].astype(str)).isin(
                            (Data_Upper_Aggregation['Key'].astype(str) + Data_Upper_Aggregation['Code'].astype(str)).unique()
                        )]
                        

                        Data_Control = Data[Data['Code'].isin(Higher_Code)].copy()                      
                        

                        Data_Control = Data_Control.merge(
                            Data_Upper_Aggregation.drop(columns=['obsValueOld', 'Level']).rename(
                                columns={'obsValue': 'Sum_of_Components'}),
                            on=['Key', 'Code', 'obsTime'], how='left'
                        )
                        Data_Control['Discrepancy'] = Data_Control['Sum_of_Components'].fillna(0) - Data_Control[
                            'obsValue'].fillna(0)
                        Data_Control = Data_Control[
                            ['Key', 'Code', 'Level', 'obsTime', 'obsValue', 'Sum_of_Components', 'Discrepancy',
                             'obsValueOld']]
                        

                        Data_Control0 = None

                        if Data_Control.shape[0] > 0:
                            Data_Discrepancy = pd.concat(
                                [Data_Discrepancy,
                                 Data_Control[Data_Control['Sum_of_Components'].notnull() &
                                    (Data_Control['Discrepancy'].round(6) != 0)]])

                            Data_Control0 = Data_Control[['Key', 'Code', 'Level', 'obsTime', 'obsValue', 'obsValueOld']].copy()
                            Data_Control0 = Data_Control0[
                                ~((Data_Control0['Key'].astype(str) + Data_Control0['Code'].astype(str)).isin(
                                    (Data_Keep['Key'].astype(str) + Data_Keep['Code'].astype(str)).unique().tolist() +
                                      (Data_Upper_Aggregation['Key'].astype(str) + Data_Upper_Aggregation['Code'].astype(str)).unique().tolist())
                                )]


                        if Check_Consistency:
                            if Folder is not None:
                                Data_Keep.to_csv(f'{Folder}/{Prefix_File_Name}Keep_{i}.csv', index=False)
                                Data_Upper_Aggregation.to_csv(f'{Folder}/{Prefix_File_Name}Upper_Aggregation_{i}.csv',
                                                              index=False)
                                Temp = Data_Keep[Data_Keep['Code'].isin(Lower_Code)]
                                Temp = Temp.merge(
                                Hierar_Class[[f'Level{i}', 'Code']], on='Code', how='left')
                                Temp.to_csv(
                                    f'{Folder}/{Prefix_File_Name}Lower_To_Upper_Aggregation_{i}.csv', index=False
                                )


                            if Data_Control.shape[0] > 0:

                                if (Folder is not None) & (Data_Control0.shape[0]>0):
                                    Data_Control0.to_csv(f'{Folder}/{Prefix_File_Name}Data_Control_To_Add_{i}.csv',
                                                         index=False)
                                if Folder is not None:
                                    Data_Control.to_csv(f'{Folder}/{Prefix_File_Name}Data_Control_{i}.csv', index=False)

                                if i > Level_Exclude_Deletion_Min:

                                    Data_Inconsistent = Data_Control.copy()
                                    Data_Inconsistent['Discrepancy_Perc'] = 100* Data_Inconsistent['Discrepancy'] / Data_Inconsistent['obsValue']

                                    Data_Inconsistent['Discrepancy_Perc']= Data_Inconsistent['Discrepancy_Perc'].fillna(0).round(round_digit0)

                                    Data_Inconsistent =  Data_Inconsistent[Data_Inconsistent['Sum_of_Components'].notna() &
                                                                           (Data_Inconsistent['Discrepancy_Perc'].fillna(0).abs() > Tolerance_Percent0)]

                                 #   Data_Inconsistent = Data_Control.assign(
                                 #       Discrepancy_Perc=lambda x: 100 * round(x['Discrepancy'], round_digit0) / x['obsValue']
                                 #   ).query('Sum_of_Components.notnull() & abs(Discrepancy_Perc) > @Tolerance_Percent0')

                                    if Data_Inconsistent.shape[0] > 0:
                                        if Folder is not None:
                                            Data_Inconsistent.to_csv(
                                                f'{Folder}/{Prefix_File_Name}Data_inconsistent_To_delete_lower_level_{i}.csv',
                                                index=False)
                                        Data_Deleted = None

                                        for i_Level in Data_Inconsistent['Code'].unique():
                                            Key_Level = Data_Inconsistent[Data_Inconsistent['Code'] == i_Level]['Key'].unique()
                                            Set_Level = i_Level

                                            for i_Sub_n in range(i + 1, int(Data_Keep['Level'].max()) + 1):

                                                Set_SubLevel = \
                                                Hierar_Class.rename(columns={f'Level{i_Sub_n - 1}': 'Level_Temp'}).query(
                                                    'Level_Temp in @Set_Level')['Code'].unique()

                                                for i_SubLevel in Set_SubLevel:

                                                    Data_Deleted = pd.concat([ Data_Deleted,
                                                                               Data_Keep[
                                                        (Data_Keep['Key'].astype(str) + Data_Keep['Code'].astype(str)).isin(
                                                            Key_Level + i_SubLevel)]
                                                        ])

                                                    Data_Keep = Data_Keep[
                                                        ~(Data_Keep['Key'].astype(str) + Data_Keep['Code'].astype(str)).isin(
                                                            Key_Level + i_SubLevel)
                                                        ]


                                                Set_Level = Set_SubLevel



                                        if (Folder is not None) & (Data_Deleted is not None) :
                                            Data_Deleted.to_csv(f'{Folder}/{Prefix_File_Name}Data_inconsistent_deleted_{i}.csv',
                                                                index=False)

                                        Data_Upper_Aggregation = Data_Upper_Aggregation[~(
                                                Data_Upper_Aggregation['Key'].astype(str) + Data_Upper_Aggregation[
                                            'Code'].astype(str)).isin(
                                            (Data_Inconsistent['Key'].astype(str) + Data_Inconsistent[
                                                'Code'].astype(str)).unique()
                                        )]

                                        Data_Keep = pd.concat([Data_Keep,
                                                               Data_Upper_Aggregation,
                                                               Data_Control[
                                                                   ~(Data_Control['Key'].astype(str) + Data_Control[
                                                                       'Code'].astype(
                                                                       str)).isin(
                                                                       (Data_Keep['Key'].astype(str) + Data_Keep[
                                                                           'Code'].astype(str)).unique()
                                                                   )]])
                                        Data_Keep = Data_Keep.drop(columns=['Level'])
                                        Data_Keep = Data_Keep.merge(
                                            Hierar_Class[['Level', 'Code']],
                                            on='Code',
                                            how='left'
                                        )

                                    else:
                                        Data_Keep = pd.concat([Data_Keep,
                                                               Data_Upper_Aggregation,
                                                               Data_Control0])


                                else:
                                    Data_Keep = pd.concat([Data_Keep,
                                                           Data_Upper_Aggregation,
                                                           Data_Control0])

                            else:
                                Data_Keep = pd.concat([Data_Keep,
                                                   Data_Upper_Aggregation,
                                                   Data_Control0])
                        else:                          

                            Data_Keep = pd.concat([Data_Keep,
                                                   Data_Upper_Aggregation,
                                                   Data_Control0])


            Data_Keep = Data_Keep[['Key', 'Code', 'Level', 'obsTime', 'obsValue', 'obsValueOld']]
            Data_Keep['Info'] =Text_to_Identify_Lowest_Level

            if len(Data_Keep['Level']) > 1:

                for i in range(int(Data_Keep['Level'].max())-1, int(Data_Keep['Level'].min())-1, -1, ):
                    # add upper level of level i-1

                    Data_Keep = Data_Keep.merge(
                        Hierar_Class[['Code', f'Level{i}']].rename(columns={f'Level{i}':'Level_Temp'}),
                        on='Code', how='left')
                    # Check if upper level exists
                    Data_Keep.loc[(Data_Keep['Key'].astype(str) + Data_Keep['Code'].astype(str)).isin(
                        (Data_Keep['Key'].astype(str) + Data_Keep['Level_Temp'].astype(str)).unique()), 'Info']=None

                    Data_Keep = Data_Keep.drop(columns=['Level_Temp'])

            # Check Level0
            if ('Level0'  in Hierar_Class.columns):
                Data_Keep = Data_Keep.merge(
                    Hierar_Class[['Code', 'Level0']], on='Code', how='left')

                # Check if upper level exists
                Data_Keep.loc[(Data_Keep['Key'].astype(str) + Data_Keep['Code'].astype(str)).isin(
                    (Data_Keep['Key'].astype(str) + Data_Keep['Level0'].astype(str)).unique()), 'Info'] = None
                Data_Keep = Data_Keep.drop(columns=['Level0'])

                #  message('Bringing Key dimensions')

            # Eliminate duplicate (Further check why they appear
            # Data_Keep = Data_Keep.groupby(['Key', 'Code', 'obsTime']).['Temp'].rank(ascending=False, method='first') #transform(rank)

            Data_Keep = Data_Keep.sort_values(by=['Key', 'Code', 'obsTime', 'Info'],
                                              ascending=[True, True, True, False])
            
            Data_Keep = (Data_Keep.sort_values(by=['Key', 'Code', 'obsTime'], ascending=[True, True, True])
                         .assign(Rank0=Data_Keep.groupby(['Key', 'Code', 'obsTime']).cumcount() + 1)) \
                .query('Rank0 == 1') \
                .drop(columns=['Rank0'])

            if "Rank" in Hierar_Class.columns:
                Data_Keep = Data_Keep.merge(Hierar_Class[['Code', 'Rank']], on='Code', how='left') \
                    .sort_values(by=['Key', 'obsTime', 'Rank']) \
                    .drop(columns=['Rank'])


            if '' not in Key0:  # revert to initial setting
                Text0 = ''
                for i in range(len(Key0)):
                    if i == 0:
                        Text0 += Key0[i]
                    else:
                        Text0 += ',' + Key0[i]

                if len(Data_Keep) > 0:
                    Data_Keep = Data_Keep.merge(Data0[['Key'] + list(set(Text0.split(',')))].drop_duplicates(),
                                                on='Key', how='left')
                    Data_Keep = Data_Keep.rename(columns={'Code': Code0}).drop(columns=['Key', 'Level'])

                if (Data_Discrepancy is not None) and (len(Data_Discrepancy) > 0):
                    Data_Discrepancy = Data_Discrepancy.merge(
                        Data0[['Key'] + list(set(Text0.split(',')))].drop_duplicates(), on='Key', how='left')
                    Data_Discrepancy = Data_Discrepancy.rename(columns={'Code': Code0}).drop(columns=['Key'])

                if Folder is not None and Check_Consistency and len(i_ISO) == 1 and '' not in List_Country:
                    FileName = os.path.join(Folder, f"{Prefix_File_Name}Discrepancy_{i_ISO}.csv")
                    if os.path.exists(FileName):
                        os.remove(FileName)
                    if Data_Discrepancy_ is not None and Data_Discrepancy_.shape[0] > 0:
                        print(f"Save Discrepancy between total and sum of components in {FileName}")
                        Data_Discrepancy_.to_csv(FileName, index=False, header=True)

                Data_Keep_ = pd.concat([Data_Keep_, Data_Keep], ignore_index=True)

                if isinstance(Data_Discrepancy, pd.DataFrame):
                    Data_Discrepancy_ = pd.concat([Data_Discrepancy_, Data_Discrepancy], ignore_index=True)

    
    

    for i in Data_.columns: #['Data_Source','IPCC_annex', 'CountryRegion', 'CountryName','FossilType']:
        if (i not in Data_Keep_.columns) & (i!='Source_Description'):
            Data_Keep_[i] = Data_.loc[0, i]


   # Data_Keep = Data_Keep[['Info'] + list(Data_.columns)].reset_index()
    
    Data_Keep_.drop(columns='Source_Description', errors='ignore', inplace=True)
    Data_Keep_ = Data_Keep_.merge(
        Hierar_Class[['Code', 'Description', 'Rank']].rename(columns={'Code': 'Source_Code', 'Description':'Source_Description'}),
        on='Source_Code',
        how='left')
    
    Data_Keep_['obsTime']=Data_Keep_['obsTime'].astype(int)  
         
    Data_columns = Data_columns + Data_Keep_['obsTime'].astype(str).unique().tolist()

    Data_Keep_ = Data_Keep_.sort_values(by=['obsTime']) \
        .fillna('Zach')\
        .pivot_table(columns='obsTime',
                index=['Info',
                         'Data_Source',
                         'IPCC_annex',
                         'CountryRegion',
                         'REF_AREA',
                         'CountryName',
                         'POLLUTANT',
                         'Source_Code',
                         'Source_Description',
                         'FossilType',
                         'Rank',
                         'Source_Temp'
                         ],
                values='obsValue',
                aggfunc=np.sum) \
        .reset_index() \
        .sort_values(by=['REF_AREA', 'POLLUTANT', 'Rank' , 'FossilType']) \
        .replace('Zach', None)
    #return(Data_columns)
    Data_columns = [x for x in Data_Keep_.columns if str(x) in ['Info']+ Data_columns]
    #return(Data_columns)
    Data_Keep_ = Data_Keep_[Data_columns]
    
    # ddd Data_Keep_.drop(columns=['Rank', 'Source_Temp'], errors='ignore', inplace=True)

    # Data_Source	IPCC_annex	CountryRegion	REF_AREA	CountryName	POLLUTANT	Source_Code	Source_Description	FossilType
    #Data_Keep_.drop(columns=['Rank','Source_Temp'], inplace=True)# , 'Source_Description'

    Data_Keep_ = Data_Keep_.reset_index(drop=True)
    return(Data_Keep_)



@xw.func
def SANKEY(Output_Source_Activity, sankey_type, POLLUTANT, TIME_PERIOD, Invent_Det, Source_Invent, CRT, NFR, Activity,
           Unit='Megatonnes CO2Eq'):


    Output_Source_Activity=pd.DataFrame(Output_Source_Activity)
    Output_Source_Activity.columns = Output_Source_Activity.iloc[0]
    Output_Source_Activity = Output_Source_Activity[1:]

    Output_Source_Activity = pd.melt(Output_Source_Activity,
                               id_vars=['REF_AREA',
                                        'CountryName',
                                        'POLLUTANT',
                                        'Source_Code',
                                        'Source_Description',
                                        'Activity',
                                        'Description'],
                         var_name='TIME_PERIOD', value_name='OBS_VALUE')

    #Output_Source_Activity.rename(columns={TIME_PERIOD: 'value'}, inplace=True)

    Output_Source_Activity = Output_Source_Activity[(Output_Source_Activity['POLLUTANT']== POLLUTANT) & (Output_Source_Activity['TIME_PERIOD']==TIME_PERIOD)].reset_index(drop=True)
    if len(Output_Source_Activity)>0:
        # Classifications
        if (Invent_Det=='Section') | (Source_Invent=='UNFCCC'):
            Classif_Invent = pd.DataFrame(CRT)
            Classif_Invent.columns = Classif_Invent.iloc[0]
            Classif_Invent = Classif_Invent[1:][['Code' ,'Description']]

            Classif_Invent.rename(columns={'Code':'Code'}, inplace=True)

        else:
            Classif_Invent = pd.DataFrame(NFR)
            Classif_Invent.columns = Classif_Invent.iloc[0]
            Classif_Invent = Classif_Invent[1:][['NFR_Sector', 'NFR_Description']]
            Classif_Invent.rename(columns={'NFR_Sector':'Code', 'NFR_Description':'Description'}, inplace=True)

        Activity = pd.DataFrame(Activity)
        Activity.columns = Activity.iloc[0]
        Activity = Activity[1:][['Code', 'Description']]

        if 'AEA-TOTAL' in list(Activity['Code']):
            Activity_AEA = Activity.iloc[range(Activity.index[Activity['Code'] == 'AEA-TOTAL'][0] - 1)]

        else:
            Activity_AEA =Activity[ ~Activity['Code'].isin(['AEA-TOTAL', "INV-TOTAL",
                                                       "NATRESABROAD","NRA-AIR","NRA-FISH","NRA-LAND","NRA-WATER",
                                                       "NONRESTERR","NRT-AIR","NRT-LAND","NRT-WATER",
                                                       "OTHER", #"RA","NRT",
                                                        "LULUCF"])]
        if 'LULUCF' in list(Output_Source_Activity['Activity']):
            LULUCF_Code = list(Output_Source_Activity.loc[Output_Source_Activity['Activity'].isin(['LULUCF']), 'IPCC'])[0] [:2]

        else:
            LULUCF_Code = '4.'
        #Exclude LULUCF
       # Output_Source_Activity = Output_Source_Activity[Output_Source_Activity['IPCC'].str[:2]!=LULUCF_Code ].reset_index(drop=True)

        # Exclude National Resident abroad and OTHER
        #Output_Source_Activity = Output_Source_Activity[~Output_Source_Activity['Activity'].isin(['OTHER',"NATRESABROAD","NRA-AIR","NRA-FISH","NRA-LAND","NRA-WATER"])].reset_index(drop=True)

        #Folder
        folder0 = os.path.dirname(os.path.realpath(__file__))
        folder = os.path.join (folder0, "Sankey") #os.getcwd()
        folder0 = os.path.join(folder0, "I2A_Data")

        if not os.path.exists(folder) : os.makedirs(folder)

        # Read CID
        filename0 = ""

        if sankey_type in ["Level Comparison", "Share Comparison"]:

            try:
                compar_file = pd.read_csv(os.path.join(folder0, 'All_Regions_And_Countries_Annual_AEA_Pivot.csv'))
            except:
                filename0 = ". Cannot find " + os.path.join(folder0,
                                                             'All_Regions_And_Countries_Annual_AEA_Pivot.csv') + " for comparison."
                compar_file = None
                if sankey_type == "Level Comparison": sankey_type = "Level"
                if sankey_type == "Share Comparison": sankey_type = "Share"

            if compar_file is not None:
                filename0 = ".     Used " + os.path.join(folder0,
                                                            'All_Regions_And_Countries_Annual_AEA_Pivot.csv') + " for comparison."
                if str(int(TIME_PERIOD)) in compar_file.columns:
                    compar_file.rename(columns={str(int(TIME_PERIOD)): 'compar_value'}, inplace=True)

                    if 'ACTIVITY' in compar_file.columns: compar_file.rename(columns={'ACTIVITY': 'Activity'},
                                                                             inplace=True)
                    if 'ISO3CODE' in compar_file.columns: compar_file.rename(columns={'ISO3CODE': 'REF_AREA'},
                                                                             inplace=True)
                    compar_file = compar_file[compar_file['REF_AREA'] == Output_Source_Activity.loc[0, 'REF_AREA']]
                    if len(compar_file) > 0:
                        if 'GHG' not in compar_file['POLLUTANT'].unique():
                            compar_file = compar_file.groupby(['Activity'], as_index=False)[
                                'compar_value'].sum().reset_index(drop=True)
                        else:
                            compar_file = compar_file[compar_file['POLLUTANT'] == POLLUTANT][
                                ['Activity', 'compar_value']].reset_index(drop=True)
                        
                        if len(compar_file) > 0:
                            # recode
                            compar_file.loc[compar_file['Activity'] == 'H Other', 'Activity'] = 'H-NS'
                            compar_file.loc[compar_file[
                                                'Activity'] == 'Other Services', 'Activity'] = 'Services, Transport excl.' #''Other services excl. Transport and Storage'
                            if 'H' in Output_Source_Activity['Activity'].unique():
                                compar_file.loc[compar_file['Activity'].isin(['H49','H50','H51','H52','H53','H-NS']), 'Activity'] = 'H'

                            compar_file = compar_file.groupby(['Activity'], as_index=False)[
                                'compar_value'].sum().reset_index(drop=True)

                            # Default is         'Megatonnes CO2Eq'
                            if Unit == 'Gigatonnes CO2Eq':
                                compar_file['compar_value'] = compar_file['compar_value'] / 1000
                            elif Unit == 'Thousand tonnes CO2Eq':
                                compar_file['compar_value'] = compar_file['compar_value'] * 1000
                            elif Unit == 'Tonnes CO2Eq':
                                compar_file['compar_value'] = compar_file['compar_value'] * 1000000


                        else:
                                filename0 = ".    No suitable data for POLLUTANT " + POLLUTANT + ' from ' + os.path.join(
                                    folder0,
                                    'All_Regions_And_Countries_Annual_AEA_Pivot.csv') + " for comparison."
                                if sankey_type == "Level Comparison": sankey_type = "Level"
                                if sankey_type == "Share Comparison": sankey_type = "Share"
                    else:
                        filename0 = ".       No suitable data for REF_AREA " + Output_Source_Activity.loc[0, 'REF_AREA'] + ' ' + \
                                    Output_Source_Activity.loc[0, 'CountryName'] + ' from ' + os.path.join(folder0,
                                                                                                     'All_Regions_And_Countries_Annual_AEA_Pivot.csv') + " for comparison."
                        if sankey_type == "Level Comparison": sankey_type = "Level"
                        if sankey_type == "Share Comparison": sankey_type = "Share"
                else:
                    filename0 = ".      No suitable data for TIME_PERIOD " + TIME_PERIOD + ' from ' + os.path.join(folder0,
                                                                                                              'All_Regions_And_Countries_Annual_AEA_Pivot.csv') + " for comparison."
                    if sankey_type == "Level Comparison": sankey_type = "Level"
                    if sankey_type == "Share Comparison": sankey_type = "Share"


        title_sankey = Output_Source_Activity.at[
                           0, 'CountryName'] + ": " + POLLUTANT + ' emissions from Source of inventories to ISIC in ' + str(
            int(TIME_PERIOD)) + ' [' + Unit  + ']' #' [EqCO2]'
        filename = "Level_" + Output_Source_Activity.at[0, 'REF_AREA'] + '_' + POLLUTANT + '_' + str(
            int(TIME_PERIOD)) + '.html'

        Output_Source_Activity['OBS_VALUE_Inv'] =  Output_Source_Activity['OBS_VALUE']
        if sankey_type in ["Share", "Share Comparison"]:
            title_sankey = Output_Source_Activity.at[
                               0, 'CountryName'] + ": " + POLLUTANT + ' emissions from Source of inventories to ISIC in ' + str(
                int(TIME_PERIOD)) + ' [Percentage]'
            filename = "Share_" + Output_Source_Activity.at[0, 'REF_AREA'] + '_' + POLLUTANT + '_' + str(
                int(TIME_PERIOD)) + '.html'

            #return(Output_Source_Activity[(Output_Source_Activity['Source_Code'].isin(Classif_Invent['Code'].unique())) & (Output_Source_Activity['Source_Code'].str[:2] != LULUCF_Code)])
            Output_Source_Activity2 = Output_Source_Activity.copy()
            
            Output_Source_Activity2.loc[Output_Source_Activity['Source_Code'].str[:2]==LULUCF_Code, 'OBS_VALUE'] = - Output_Source_Activity2.loc[Output_Source_Activity['Source_Code'].str[:2]==LULUCF_Code, 'OBS_VALUE']
            Output_Source_Activity['OBS_VALUE_Inv'] =\
                100 * Output_Source_Activity['OBS_VALUE'] / Output_Source_Activity2.loc[(Output_Source_Activity2['Activity'].isin(['INV-TOTAL'])) |
                                                                            (Output_Source_Activity2['Source_Code'].str[:2]==LULUCF_Code) , 'OBS_VALUE'].sum()
            #&            (Output_Source_Activity['Activity'].isin(list(Activity_AEA['Code']) + ["NONRESTERR", "NRT-AIR", "NRT-LAND", "NRT-WATER"]))

            if 1==2:  Output_Source_Activity['OBS_VALUE_Inv'] = 100 * Output_Source_Activity['OBS_VALUE_Inv']/ Output_Source_Activity.loc[Output_Source_Activity['Activity'].isin(['INV-TOTAL']), 'OBS_VALUE'].sum()

            Output_Source_Activity['OBS_VALUE'] = 100 * Output_Source_Activity['OBS_VALUE'] / Output_Source_Activity.loc[Output_Source_Activity['Activity'].isin(Activity_AEA['Code'].unique()), 'OBS_VALUE'].sum()

            if sankey_type in [ "Share Comparison"]:
                compar_file['compar_value'] = 100 * compar_file['compar_value'] / compar_file.loc[compar_file['Activity'].isin(Activity_AEA['Code'].unique()), 'compar_value'].sum()

        Output_Source_Activity = Output_Source_Activity[
            ['Source_Code', 'Source_Description', 'Activity', 'Description', 'OBS_VALUE', 'OBS_VALUE_Inv']]

        Output_Source_Activity1 = Output_Source_Activity.groupby(['Activity', 'Description'], as_index=False)[
                'OBS_VALUE'].sum()  # .reset_index(drop=True)

        # Target
        if sankey_type in ["Level Comparison", "Share Comparison"]:
            Output_Source_Activity1 = Output_Source_Activity1.merge(right=compar_file, on='Activity', how='left')

            Output_Source_Activity1['target'] = '[' + Output_Source_Activity1['OBS_VALUE'].astype(float).round(1).astype(str) + ' VS CID:' + \
                     Output_Source_Activity1['compar_value'].astype(float).round(1).astype(str) + '] ' + \
                                      Output_Source_Activity1['Activity'] + ' ' + Output_Source_Activity1['Description']

            Output_Source_Activity = Output_Source_Activity.merge(
                right=Output_Source_Activity1.drop(columns=['Description', 'OBS_VALUE', 'compar_value']),
                on='Activity', how='left')
        else:
            Output_Source_Activity1['target'] = '[' + Output_Source_Activity1['OBS_VALUE'].astype(float).round(1).astype(str) + '] ' + \
                                      Output_Source_Activity1[
                                          'Activity'] + ' ' + Output_Source_Activity1['Description']

            Output_Source_Activity = Output_Source_Activity.merge(right=Output_Source_Activity1.drop(columns=['Description', 'OBS_VALUE']),
                                                  on='Activity', how='left')

        ## Total AEA

        if 1==2:
            Output_Source_Activity_tot = Output_Source_Activity.iloc[:1]
            #Output_Source_Activity_tot['source'] = 'Total [' + str(round(Output_Source_Activity1['OBS_VALUE'].sum(), 1)) + ']'
            #Output_Source_Activity_tot['source'] = None
            Output_Source_Activity_tot['Source_Code'] = None
            Output_Source_Activity_tot['Source_Description'] = None
            Output_Source_Activity_tot['Activity'] = 'AEA-TOTAL'
            Output_Source_Activity_tot['Description'] = 'Total emissions'
            if sankey_type in ["Level Comparison", "Share Comparison"]:
                Output_Source_Activity_tot['target'] =   '[' + str(round(Output_Source_Activity.loc[Output_Source_Activity['Activity'].isin(Activity_AEA['Code'].unique()), 'OBS_VALUE'].sum(), 1)) + \
                                               ' VS CID:' + \
                         str(round(compar_file.loc[compar_file['Activity'].isin(Activity_AEA['Code'].unique()), 'compar_value'].sum(), 1))  + '] Total'
            else:
                Output_Source_Activity_tot['target'] = '[' + str(round(Output_Source_Activity.loc[Output_Source_Activity['Activity'].isin(
                    Activity_AEA['Code'].unique()), 'OBS_VALUE'].sum(), 1)) +  '] Total'

            Output_Source_Activity_tot['OBS_VALUE'] = Output_Source_Activity1['OBS_VALUE'].min() / 100000

            Output_Source_Activity = pd.concat([Output_Source_Activity, Output_Source_Activity_tot], ignore_index=True)

        # Source
        Output_Source_Activity1 = Output_Source_Activity[Output_Source_Activity['Activity'].isin(Activity_AEA['Code'])]
        Output_Source_Activity1 = pd.concat([Output_Source_Activity1, Output_Source_Activity[~Output_Source_Activity['Source_Code'].isin(Output_Source_Activity1['Source_Code'].unique())]])

        Output_Source_Activity1 = Output_Source_Activity1.groupby(['Source_Code', 'Source_Description'], as_index=False)[
            'OBS_VALUE_Inv'].sum().reset_index(drop=True).rename(columns={'OBS_VALUE_Inv': 'OBS_VALUE'})

        Output_Source_Activity1['source'] = Output_Source_Activity1['Source_Code'] + ' ' + Output_Source_Activity1[
            'Source_Description'] + ' [' + Output_Source_Activity1['OBS_VALUE'].astype(float).round(1).astype(str) + ']'

        Output_Source_Activity1.loc[Output_Source_Activity1['Source_Code']=='Total Inventories','source'] = Output_Source_Activity1.loc[Output_Source_Activity1['Source_Code']=='Total Inventories','Source_Code'] + ' [' + Output_Source_Activity1.loc[Output_Source_Activity1['Source_Code']=='Total Inventories','OBS_VALUE'].round(1).astype(str) + ']'

        Output_Source_Activity = Output_Source_Activity.merge(
            right=Output_Source_Activity1.drop(columns=['Source_Description', 'OBS_VALUE']),
            on='Source_Code', how='left')

        ## Total Invent

        Output_Source_Activity.loc[Output_Source_Activity['Activity'] == 'AEA-TOTAL', 'source']=\
            'Total excluding LULUCF [' + str(round(Output_Source_Activity.loc[(Output_Source_Activity['Source_Code'].isin(Classif_Invent['Code'].unique())) &
               (Output_Source_Activity['Source_Code'].str[:2]!=LULUCF_Code)  , 'OBS_VALUE_Inv'].sum(), 1)) + ']'

        Output_Source_Activity.loc[Output_Source_Activity['Activity'] == 'AEA-TOTAL', 'Source_Code'] = '_T'
        Output_Source_Activity.loc[Output_Source_Activity['Activity'] == 'AEA-TOTAL', 'Source_Description'] = 'Total emissions excluding LULUCF'



        #Sort Source
        Classif_Invent['Rank_Inv']=Classif_Invent.index

        Classif_Invent.loc[Classif_Invent['Code']=='_T', 'Rank_Inv'] = Classif_Invent['Rank_Inv'].max()+1
        Classif_Invent.loc[Classif_Invent['Code'].str[:2] == LULUCF_Code, 'Rank_Inv'] = Classif_Invent['Rank_Inv'].max() + \
                                                                                Classif_Invent.loc[Classif_Invent['Code'].str[:2] == LULUCF_Code, 'Rank_Inv']
        Classif_Invent.loc[Classif_Invent['Code'] == 'T_LULU', 'Rank_Inv'] = Classif_Invent['Rank_Inv'].max() + 1

        #Add missing Invent
        Add_Missing_Claf = Output_Source_Activity[~Output_Source_Activity['Source_Code'].isin(Classif_Invent['Code'])][['Source_Code','Source_Description']].drop_duplicates().reset_index(drop=True)

        if len(Add_Missing_Claf)>0:
            Add_Missing_Claf['Rank_Inv']=None
            Add_Missing_Claf.loc[Add_Missing_Claf['Source_Code'].isin(['Total Inventories']),'Rank_Inv'] = Classif_Invent['Rank_Inv'].max() + 1
            Add_Missing_Claf.rename(columns={'Source_Code':'Code','Source_Description':'Description'}, inplace=True)
            Classif_Invent =  pd.concat( [Classif_Invent, Add_Missing_Claf],  ignore_index=True)
            Classif_Invent.loc[Classif_Invent['Rank_Inv'].isna(), 'Rank_Inv'] = Classif_Invent['Rank_Inv'].max() + \
                                                                                    Classif_Invent[Classif_Invent[
                                                                                        'Rank_Inv'].isna()].index

        Output_Source_Activity = Output_Source_Activity.merge(right=Classif_Invent.drop(columns=['Description']).rename(columns={'Code':'Source_Code'}) ,
                                                      on='Source_Code', how='left')

        # Sort target
        Activity['Rank_Act'] = Activity.index

        # Add missing AEA
        Add_Missing_Claf = Output_Source_Activity[~Output_Source_Activity['Activity'].isin(Activity['Code'])][
            ['Activity', 'Description']].drop_duplicates().reset_index(drop=True)

        if len(Add_Missing_Claf) > 0:
            Add_Missing_Claf['Rank_Act'] = None
            Add_Missing_Claf.rename(columns={'Code': 'Activty'}, inplace=True)
            Classif_Invent = pd.concat([Activity, Add_Missing_Claf], ignore_index=True)
            Activity.loc[Activity['Rank_Act'].isna(), 'Rank_Act'] = Activity['Rank_Act'].max() + \
                                                                                Activity[Activity[
                                                                                    'Rank_Act'].isna()].index

        Output_Source_Activity = Output_Source_Activity.merge(
            right=Activity.drop(columns=['Description']).rename(columns={'Code': 'Activity'}),
            on='Activity', how='left')

        Output_Source_Activity = Output_Source_Activity.sort_values(by=['Rank_Inv','Rank_Act']).reset_index(drop=True)


        unique_source = Output_Source_Activity.groupby(['source', 'Rank_Inv'], as_index=False)[
                'OBS_VALUE'].sum().reset_index(drop=True)
        
        unique_source = unique_source.sort_values(by='Rank_Inv').reset_index(drop=True)
        
        unique_source['Rank_Inv']=unique_source.index
        unique_source['CSum'] = np.cumsum(unique_source['OBS_VALUE'].abs())

        #unique_target= Output_Source_Activity.sort_values(by='Rank_Act')[['target']].drop_duplicates().reset_index(drop=True)

        unique_target = Output_Source_Activity.groupby(['target', 'Rank_Act'], as_index=False)[
            'OBS_VALUE'].sum().reset_index(drop=True)

        unique_target = unique_target.sort_values(by='Rank_Act').reset_index(drop=True)

        unique_target['Rank_Act'] = unique_target.index + unique_source['Rank_Inv'].max()+1

        unique_target['CSum'] = np.cumsum(unique_target['OBS_VALUE'].abs())

        Output_Source_Activity = Output_Source_Activity.drop(columns=[ 'Rank_Inv']).merge(right=unique_source.drop(columns=['OBS_VALUE','CSum']),
            on='source', how='left')
        Output_Source_Activity = Output_Source_Activity.drop(columns=['Rank_Act']).merge(right=unique_target.drop(columns=['OBS_VALUE','CSum']),
                                                                                         on='target', how='left')
        # Convert ABSVALUE to positive value and Nil Total
        # Output_Source_Activity['OBS_VALUE0'] = Output_Source_Activity['OBS_VALUE']
        #Output_Source_Activity['OBS_VALUE'] = Output_Source_Activity['OBS_VALUE'].abs()

        Output_Source_Activity.loc[(Output_Source_Activity['Source_Code'].isin(['T_LULU', '_T', 'Total Inventories'])) |
                             (Output_Source_Activity['Source_Code'].str[:2] == LULUCF_Code) |
                             (Output_Source_Activity['Activity'].isin(['AEA-TOTAL', 'INV-TOTAL', 'OTHER', "NATRESABROAD",
                                                                 "NRA-AIR", "NRA-FISH", "NRA-LAND",
                                                                 "NRA-WATER"])), 'OBS_VALUE'] = 0.000001

        labels = list(unique_source['source']) + list(unique_target['target'])
        label_to_index ={}
        for index, label in enumerate(labels):
            label_to_index[label]=index

        source = list(Output_Source_Activity['Rank_Inv'])
        target = list(Output_Source_Activity['Rank_Act'])
        value  = list(Output_Source_Activity['OBS_VALUE'].abs())
        #return(labels)
        #x_axis = Output_Source_Activity['Rank_Inv2']/(Output_Source_Activity['Rank_Inv2'].max()+1)
        x_axis=[0.001] * len(unique_source) + [0.99] * len(unique_target)

        if 1==1:

            if 1==1:
                y_axis = list((unique_source['Rank_Inv']-unique_source['Rank_Inv'].min())/ (unique_source['Rank_Inv'].max()-unique_source['Rank_Inv'].min())) + \
                 list((unique_target['Rank_Act']-unique_target['Rank_Act'].min())/ (unique_target['Rank_Act'].max()-unique_target['Rank_Act'].min()))
            else:
                Factor = 2
                unique_source['CSum'] = np.cumsum(unique_source['OBS_VALUE'].abs() + Factor * unique_source['Rank_Inv'])
                unique_target['CSum'] = np.cumsum(unique_target['OBS_VALUE'].abs() + Factor * unique_target['Rank_Act'])

                y_axis = list((unique_source['CSum'] - unique_source['CSum'].min()/10) / (
                        unique_source['CSum'].max() - unique_source['CSum'].min())/10) + \
                         list((unique_target['CSum'] - unique_target['CSum'].min()/10) / (
                        unique_target['CSum'].max() - unique_target['CSum'].min())/10)

                if 1==1:
                    y_axis[1:len(unique_source)]=y_axis[:(len(unique_source)-1)]
                    y_axis[0] = 0

                    y_axis[(len(unique_source)+1):] = y_axis[len(unique_source):(len(unique_source)+len(unique_target) - 1)]

                    y_axis[len(unique_source)] = 0


        else:
            unique_source['Temp'] = (unique_source['Rank_Inv'] - unique_source['Rank_Inv'].min()) /  (unique_source['Rank_Inv'].max() - unique_source['Rank_Inv'].min()) + \
                (unique_source['CSum'] - unique_source['CSum'].min()) /  (unique_source['CSum'].max() - unique_source['CSum'].min())
            unique_source['Temp'] =np.cumsum(unique_source['Temp'])
            
            unique_target['Temp'] = (unique_target['Rank_Act'] - unique_target['Rank_Act'].min()) / (unique_target['Rank_Act'].max() - unique_target['Rank_Act'].min()) + \
                (unique_target['CSum'] - unique_target['CSum'].min()) /  (unique_target['CSum'].max() - unique_target['CSum'].min())

            unique_target['Temp'] = np.cumsum(unique_target['Temp'])

            y_axis = list((unique_source['Temp'] - unique_source['Temp'].min()) / (unique_source['Temp'].max() - unique_source['Temp'].min())) + \
                     list((unique_target['Temp'] - unique_target['Temp'].min()) / ( unique_target['Temp'].max() - unique_target['Temp'].min()))


        #all_min_indices = [i for i, val in enumerate(y_axis) if val == min(y_axis)]
        #y_axis0 = [None if x == min(y_axis) else x for x in y_axis]
        temp0 = min(0.000001, min(x for x in y_axis if x!=min(y_axis))/2)

        if min(y_axis)==0: y_axis = [temp0 if x == min(y_axis) else x for x in y_axis]
        temp0 = (max(x for x in y_axis if x != max(y_axis)) +1)/ 2
        if max(y_axis)==1: y_axis = [temp0 if x == max(y_axis) else x for x in y_axis]

        if 1==2:

            df = pd.DataFrame({'label':labels,
                        'x' : x_axis,
                        'y' : y_axis,
                        'OBS_VALUE': list(unique_source['OBS_VALUE'])+list(unique_target['OBS_VALUE']),
                        'Cumsum':  list(unique_source['CSum'])+list(unique_target['CSum'])
            })
            return(df)

        node = dict(label=labels,
                    x=x_axis,
                    y=y_axis,
                    pad=15,
                    thickness=20,
                    line=dict(color="black", width=0.5)
                    )
        link = dict(source=source,
                    target=target,
                    value=value)
        fig = go.Figure(data=[go.Sankey(arrangement="snap",  ##Note - added snap
                                        node=node, link=link
                                        )])


        fig.update_layout(title_text=title_sankey, font_size=14, width=1200, height=800)

        # fig.show()
        # Directory

        filename = os.path.join(folder, filename)
        fig.write_html(filename)
        return (filename + filename0)
    else:
        return("No Data. Check Output_Source_Activity Tab")

@xw.func
def Read_OECD(File_Type, Country, OECD_Type):

    script_dir = os.path.dirname(os.path.realpath(__file__))
    if 'AIR' in OECD_Type:
        file_name = 'DSD_AIR_TRANSPORT.csv'
    elif 'SEA' in OECD_Type:
        file_name = 'DSD_MARITIME_TRANSPORT.csv'

    if  'IMF imputations' in File_Type: file_name = 'Tool_DSD_' + file_name

    file_name = script_dir.replace('\\','/') + '/I2A_Data/' + file_name

    Data = pd.read_csv(file_name)
    if 'AIR' in OECD_Type:
        Data = Data[(Data['REF_AREA']==Country) & (Data['FREQ']=='A') & (Data['FLIGHT_TYPE']=='_T') &
                    ((Data['EMISSIONS_SOURCE']=='RES_DOM_IN') | (Data['EMISSIONS_SOURCE']=='RES_DOM_OUT') |
                     (Data['EMISSIONS_SOURCE']=='RES_INT_FROM') | (Data['EMISSIONS_SOURCE']=='RES_INT_TO') | (Data['EMISSIONS_SOURCE']=='RES_INT_OUT'))]
    elif 'SEA' in OECD_Type:
        Data = Data[(Data['REF_AREA'] == Country) & (Data['FREQ'] == 'A') & (Data['VESSEL'] == 'ALL_VESSELS')]

    return(Data)




@xw.func
def Read_Inventory(Country, Data_Source):

    script_dir = os.path.dirname(os.path.realpath(__file__))
    file_name = 'Tool_EDGAR.csv' if 'EDGAR' in Data_Source else 'Tool_UNFCCC.csv'

    file_name = script_dir.replace('\\', '/') + '/I2A_Data/' + file_name

    Data = pd.read_csv(file_name)

    Data = Data[(Data['REF_AREA'] == Country)]# & (Data['IPCC_annex'] == Annex) ]

    return (Data)