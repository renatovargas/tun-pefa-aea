# Synchronisation des fichiers hors dépôt

`AGENTS.md`, `STRUCTURE.md` et `refs/` ne sont pas dans git. Leur copie de référence est sur le remote rclone `OneDrive:`, dans `_WORK/2026-12-IMF-Tunisia/gitignored-files/`. Aucun montage n'est nécessaire.

Au début d'une session, récupérer la version la plus récente :

```bash
rclone copy "OneDrive:_WORK/2026-12-IMF-Tunisia/gitignored-files" . --update \
  --filter "- .DS_Store" --filter "+ /AGENTS.md" --filter "+ /STRUCTURE.md" --filter "+ /refs/**" --filter "- *"
```

Après avoir modifié l'un de ces fichiers, renvoyer les changements :

```bash
rclone copy . "OneDrive:_WORK/2026-12-IMF-Tunisia/gitignored-files" --update \
  --filter "- .DS_Store" --filter "+ /AGENTS.md" --filter "+ /STRUCTURE.md" --filter "+ /refs/**" --filter "- *"
```

`--update` ne remplace jamais un fichier plus récent de l'autre côté. `rclone copy` ne supprime rien : une suppression se fait à la main des deux côtés. Si `rclone listremotes` ne montre pas `OneDrive:`, demander à l'utilisateur de configurer le remote (`rclone config`).
