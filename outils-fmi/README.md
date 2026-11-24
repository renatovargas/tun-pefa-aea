# Outils du FMI

Ce dossier contient les outils du Département des statistiques du Fonds monétaire international (FMI) utilisés par la mission. Leur auteur est Achille Pegoue, économiste principal à la Division du secteur réel. Ils sont publiés ici avec l'accord de la mission ; ils seront retirés si le FMI le demande.

| Dossier | Contenu |
|:--|:--|
| `pefa-converter/` | PEFA Converter : classeur `PEFA_Converter.xlsm`, fonction xlwings `PEFA_Converter.py` et manuel (version 0.0, novembre 2024). Il convertit un bilan énergétique au format de l'AIE en tableaux physiques des ressources et des emplois d'énergie (PEFA). |
| `i2a/` | Air Emissions Account Converter (I2A) : classeur `I2A.xlsm`, fonction xlwings `I2A.py` et manuel (version 0.0, mars 2026). Il convertit un inventaire des gaz à effet de serre en comptes des émissions atmosphériques (AEA). Le dossier `I2A_Data/` ne contient que les lignes de la Tunisie des fichiers de l'OCDE `DSD_AIR_TRANSPORT.csv` et `DSD_MARITIME_TRANSPORT.csv` livrés avec l'outil (suffixe `_TUN`) ; les autres fichiers de données de l'outil ne sont pas utilisés. |

Les pages de traitement du site appellent les fonctions `EB2PEFA` et `I2A` sans les modifier, par le module `scripts/outils_fmi.py`, et refont chaque étape en polars pour la documenter. Toute partie de code reprise ou adaptée de ces outils cite l'outil et son auteur.

## Colonne « Total » du bilan

La plage `Energy_Balance` du classeur d'exemple comprend la colonne « Total ». La matrice de concordance par défaut a des lignes pour ce produit dans les quatre flux d'usages non énergétiques. Avec cette colonne, la fonction `EB2PEFA` compte deux fois les usages non énergétiques, une fois par produit et une fois par le total. Les ressources et les emplois de l'exemple ne sont alors pas égaux (24 197,846 PJ et 24 386,288 PJ) ; sans la colonne, ils le sont (24 009,40 PJ).

L'outil reste tel quel dans ce dossier. Les pages de traitement transmettent la plage `Energy_Balance` sans la colonne « Total », pour l'exemple comme pour la Tunisie. La vérification se trouve sur la page « Tableaux PEFA » (`fr/traitement/13-tableaux-pefa/`). Le point est signalé à l'auteur de l'outil.

## Points relevés dans l'outil I2A

L'outil reste tel quel dans ce dossier. Les pages de traitement des comptes AEA (`fr/traitement/20-inventaire-aea/` à `23-passage-export-aea/`) contournent les points suivants par la préparation des données d'entrée, et les montrent sur des chiffres. Ils sont signalés à l'auteur de l'outil.

- Les feuilles actives du classeur portent des facteurs de démonstration ; les tables par défaut sont dans les feuilles `Conversion_Matrix_CRT_Def`, `Activity_Def` et `CRT_Def`.
- La matrice par défaut n'a aucun facteur pour les sols agricoles (3.D) ni pour le transport et le stockage du CO2 (1.C). Leurs émissions disparaissent sans message.
- L'outil regroupe ses lignes par code et par libellé de catégorie (lignes 257 et 559 de `I2A.py`). Une catégorie sans libellé, par exemple un code de la matrice absent de la table `CRT_Def` (4.D.2.c.ii), disparaît.
- Le total `INV-TOTAL` additionne les éléments de passage sans leur signe : il dépasse l'inventaire de deux fois les émissions des résidents à l'étranger.
- L'écart positif du transport maritime n'est pas inscrit dans l'élément de passage `NRA-WATER`, car le test de la ligne 425 porte sur l'index de la table des activités et non sur ses codes.
- Les fichiers `Tool_DSD_*.csv` (imputations du FMI) sont en kilotonnes, alors que la fonction traite les données de l'OCDE comme des tonnes. Les pages utilisent les fichiers d'origine de l'OCDE, en tonnes.
- Le fichier `data/sources/inventaire-ges/Tunisia_UNFCCC.xlsx`, préparé pour l'outil, est en kilotonnes de chaque gaz et non en équivalent CO2, écrit le N2O « N20 » et omet des sous-catégories ; les pages partent des tableaux CRT.
