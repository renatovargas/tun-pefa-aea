# Outils du FMI

Ce dossier contient les outils du Département des statistiques du Fonds monétaire international (FMI) utilisés par la mission. Leur auteur est Achille Pegoue, économiste principal à la Division du secteur réel. Ils sont publiés ici avec l'accord de la mission ; ils seront retirés si le FMI le demande.

| Dossier | Contenu |
|:--|:--|
| `pefa-converter/` | PEFA Converter : classeur `PEFA_Converter.xlsm`, fonction xlwings `PEFA_Converter.py` et manuel (version 0.0, novembre 2024). Il convertit un bilan énergétique au format de l'AIE en tableaux physiques des ressources et des emplois d'énergie (PEFA). |

Les pages de traitement du site appellent la fonction `EB2PEFA` sans la modifier, par le module `scripts/outils_fmi.py`, et refont chaque étape en polars pour la documenter. Toute partie de code reprise ou adaptée de ces outils cite l'outil et son auteur.

## Colonne « Total » du bilan

La plage `Energy_Balance` du classeur d'exemple comprend la colonne « Total ». La matrice de concordance par défaut a des lignes pour ce produit dans les quatre flux d'usages non énergétiques. Avec cette colonne, la fonction `EB2PEFA` compte deux fois les usages non énergétiques, une fois par produit et une fois par le total. Les ressources et les emplois de l'exemple ne sont alors pas égaux (24 197,846 PJ et 24 386,288 PJ) ; sans la colonne, ils le sont (24 009,40 PJ).

L'outil reste tel quel dans ce dossier. Les pages de traitement transmettent la plage `Energy_Balance` sans la colonne « Total », pour l'exemple comme pour la Tunisie. La vérification se trouve sur la page « Tableaux PEFA » (`fr/traitement/13-tableaux-pefa/`). Le point est signalé à l'auteur de l'outil.
