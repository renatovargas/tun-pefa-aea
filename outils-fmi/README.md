# Outils du FMI

Ce dossier contient les outils du Département des statistiques du Fonds monétaire international (FMI) utilisés par la mission. Leur auteur est Achille Pegoue, économiste principal à la Division du secteur réel. Ils sont publiés ici avec l'accord de la mission ; ils seront retirés si le FMI le demande.

| Dossier | Contenu |
|:--|:--|
| `pefa-converter/` | PEFA Converter : classeur `PEFA_Converter.xlsm`, fonction xlwings `PEFA_Converter.py` et manuel (version 0.0, novembre 2024). Il convertit un bilan énergétique au format de l'AIE en tableaux physiques des ressources et des emplois d'énergie (PEFA). |

Les pages de traitement du site appellent la fonction `EB2PEFA` sans la modifier, par le module `scripts/outils_fmi.py`, et refont chaque étape en polars pour la documenter. Toute partie de code reprise ou adaptée de ces outils cite l'outil et son auteur.
