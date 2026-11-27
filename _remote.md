# Files kept outside the repository (maintainer only)

These instructions are for the repository owner (Renato Vargas) only. They rely on a private rclone remote that nobody else can access. Other users can run the pipeline and render the site without any of these files.

`AGENTS.md`, `STRUCTURE.md` and `refs/` are not tracked by git. Their reference copy lives on the rclone remote `OneDrive:`, in `_WORK/2026-12-IMF-Tunisia/gitignored-files/`. No mount is needed.

At the start of a session, fetch the latest version:

```bash
rclone copy "OneDrive:_WORK/2026-12-IMF-Tunisia/gitignored-files" . --update \
  --filter "- .DS_Store" --filter "+ /AGENTS.md" --filter "+ /STRUCTURE.md" --filter "+ /refs/**" --filter "- *"
```

After changing any of these files, send the changes back:

```bash
rclone copy . "OneDrive:_WORK/2026-12-IMF-Tunisia/gitignored-files" --update \
  --filter "- .DS_Store" --filter "+ /AGENTS.md" --filter "+ /STRUCTURE.md" --filter "+ /refs/**" --filter "- *"
```

`--update` never replaces a file that is newer on the other side. `rclone copy` never deletes anything: a deletion has to be made by hand on both sides. If `rclone listremotes` does not show `OneDrive:`, the remote has to be configured first with `rclone config`.
