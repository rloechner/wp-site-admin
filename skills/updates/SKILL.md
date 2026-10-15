---
name: updates
description: "Use when the owner wants WordPress plugins, themes, or core updated, or when a health check or digest shows pending updates. Lists pending updates, checks for a backup, then updates ONE approved item at a time via WP-CLI over SSH, the optional companion bridge, or wp-admin in the browser, verifying the site after each and giving rollback steps if anything breaks. Never auto-updates."
---

# Updates (plugins, themes, core)

## Safety rules (non-negotiable)
1. **List first.** `python3 scripts/wp-update.py list` and show the owner each item: name, installed → new version, active or not, "tested up to" and required PHP when known. Flag major-version jumps (e.g. 5.x → 6.x) and WooCommerce/membership/payment plugins as higher risk.
2. **Backup first.** `python3 scripts/wp-update.py backup-check`. If an active backup plugin exists, ask the owner to run (or approve you running) a fresh backup. If none exists, recommend a host snapshot or UpdraftPlus (**Plugins → Add New Plugin → UpdraftPlus → Backup Now**) before continuing. The owner may knowingly skip; record that they did.
3. **Explicit yes per update**, or per batch the owner names ("update CF7 and Akismet"). "Update everything" still means: list what that covers, confirm once, then go one at a time.
4. **One at a time.** Never bulk-update. Order: low-risk plugins → high-risk plugins → themes → core (core last, alone).
5. **Verify after each.** The update commands run `verify` automatically: homepage 200 with no fatal-error text, wp-login loads, wp-admin responds, authenticated REST works. Report the result before the next item. **Stop the batch at the first failure.**
6. **Rollback when broken** (the script prints this when verification fails):
   - Site down with a critical error → disable the plugin by renaming `wp-content/plugins/<slug>` to `<slug>.off` (SFTP or host file manager), or `wp plugin deactivate <slug>`.
   - Reinstall the previous version: `wp plugin install <slug> --version=<old> --force`, or download it from `https://wordpress.org/plugins/<slug>/advanced/` (Previous versions) and upload via **Plugins → Add New Plugin → Upload Plugin → Replace current with uploaded**.
   - Or restore the pre-update backup.
7. **No auto-updates.** Don't enable them yourself. Tell the owner they can, per plugin, at **Plugins → Installed Plugins → Enable auto-updates**, and for core at **Dashboard → Updates**.

## Paths, in order of preference
`--via auto` (the default) picks (a) when WP-CLI is configured, otherwise (b), otherwise it prints (c).

### (a) WP-CLI over SSH (best: fastest, clearest output, works with file permissions locked)
Needs host shell access (most managed hosts: WP Engine, Kinsta, SiteGround, Cloudways...). Store `WP_SSH=user@host` and `WP_PATH=/path/to/wordpress` as secrets, with an SSH key for the bot that the owner adds in the host panel.
```bash
source scripts/wp-env.sh
python3 scripts/wp-update.py list --via cli
python3 scripts/wp-update.py plugin <slug> --via cli --yes     # runs: wp plugin update <slug>
python3 scripts/wp-update.py theme <slug> --via cli --yes
python3 scripts/wp-update.py core --via cli --yes              # wp core update && wp core update-db
```

### (b) Companion bridge (no SSH needed)
The owner installs `companion/wpsa-rest-bridge.php` in `wp-content/mu-plugins/`. It adds admin-only endpoints that run WordPress's own `Plugin_Upgrader`, `Theme_Upgrader` and `Core_Upgrader`:
| Endpoint | Capability |
|---|---|
| `GET /wp-json/wpsa/v1/updates` | update_plugins, update_themes or update_core |
| `POST /wp-json/wpsa/v1/update/plugin {"plugin":"dir/file.php"}` | update_plugins |
| `POST /wp-json/wpsa/v1/update/theme {"theme":"slug"}` | update_themes |
| `POST /wp-json/wpsa/v1/update/core` | update_core |

Authentication is standard WordPress REST auth: the bot's Application Password, or a cookie plus `X-WP-Nonce` from a logged-in browser. Unauthenticated calls get 401. The endpoints refuse (409) when `DISALLOW_FILE_MODS` is set or the host needs FTP credentials. Use path (a) or (c) then. A plugin that was active is reactivated after the update.
```bash
python3 scripts/wp-update.py plugin contact-form-7 --via bridge --yes
```

### (c) Browser fallback (no SSH, no bridge)
Using your browser, log into `<site>/wp-admin` as the bot admin (`wpbot`; its login password, not the application password, from secrets). Go to **Dashboard → Updates**, tick **only** the approved item, click **Update Plugins** / **Update Themes** / **Update to version X**, and wait for "All updates have been completed." Then run `python3 scripts/wp-update.py verify`. A single plugin can also be updated from **Plugins → Installed Plugins → "update now"**. If a 2FA or security plugin blocks the login, hand the step to the owner.

## Report template (after each item)
"Updated **Contact Form 7** 5.9 → 6.2.2 (via bridge). Site check: homepage 200 (144 ms), login and wp-admin OK, no errors. *To do this yourself: Dashboard → Updates.*"
