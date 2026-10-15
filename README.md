# WP Site Admin: a WordPress expert on call

A Grok Bot / Cursor plugin that looks after a WordPress site the way a sharp WordPress admin would: health, updates, SSL, uptime, content, comments, users, WooCommerce orders, memberships and subscriptions, and help requests. Every morning it sends one digest. It can fix things itself **after you approve**, or walk you through doing it in wp-admin with exact menu paths.

## Install
1. Add the plugin from the Grok Bot marketplace (or point your bot at this repository). The manifests are `.cursor-plugin/plugin.json` and `.claude-plugin/plugin.json`; skills load from `skills/`.
2. The helper scripts need only `python3` (standard library) and `curl`. Nothing is installed on your WordPress site.

## Onboarding (5 minutes, `connect-site` skill)
1. In wp-admin, **Users → Add New User**: username `wpbot`, a mailbox you control, role **Administrator**.
2. Edit `wpbot` → **Application Passwords** → name it `WP Site Admin Bot` → **Add New Application Password**, and copy it.
3. Give the bot the site URL, `wpbot`, and the application password. They're saved as secrets (`WP_SITE_URL`, `WP_BOT_USER`, `WP_BOT_APP_PASSWORD`).
4. The bot verifies access (`/wp-json/wp/v2/users/me`), detects your stack (WooCommerce, Paid Memberships Pro, MemberPress, WooCommerce Subscriptions, SEO and form plugins) and offers the daily digest.

Why a dedicated account: every change shows up under the bot's name, you can revoke it in one click (**Users → Profile → Application Passwords → Revoke**), and because the bot sees the same screens you do, it can always tell you where to click to do something yourself.

Optional: to let the bot read **Flamingo** form entries (Flamingo has no REST API), upload `companion/wpsa-rest-bridge.php` to `wp-content/mu-plugins/`. It's a single file; delete it to revoke.

## Safety model
- **Read freely, write only with a yes.** All checks are GET requests. Any change (publishing, moderating, updating, changing roles or memberships, deleting) is described first (item, before → after) and runs only after you approve that exact change. Deletions and refunds are flagged as irreversible.
- **Never sends on your behalf.** Replies to customers are drafted for you; nothing is emailed unless you say "send this one".
- **Secrets stay secret.** Credentials live only in the secret store and are never printed or written to notes. The state file holds counts and admin usernames only.
- **Least surprise.** Revoke the application password and the bot loses access immediately.

## Skills
| Skill | What it does |
|---|---|
| `connect-site` | Onboarding: bot admin and Application Password, secrets, verification, plugin detection |
| `site-health-check` | Uptime and response time, SSL expiry, core/plugin/theme updates, Site Health tests, cron and missed schedules |
| `content-audit` | Stale drafts, pending review, missed schedules, missing featured images and excerpts, pending and spam comments, broken internal links |
| `users-and-subscriptions` | New and suspicious users, low-noise new-admin alerts, WooCommerce orders (failed, refunded, on hold), PMPro and MemberPress memberships, WooCommerce Subscriptions |
| `help-requests` | Triage of form entries and support email by category, reply drafts (never sent unasked), common fixes |
| `daily-digest` | One morning summary with trends vs the previous day, plus a suggested routine |
| `wp-admin-howto` | "Do it yourself" paths for every action, and the approval rule |

## Helper scripts
- `python3 scripts/wpsa.py verify|detect|health|content|users|help|digest|state`: GET-only checks. Env vars: `WP_URL`, `WP_USER`, `WP_APP_PASSWORD`; state goes in `$WPSA_STATE_DIR` (default `~/.wpsa`).
- `source scripts/wp-env.sh`: must be sourced (not run with bash) to map the secrets to env vars.
- `bash scripts/wp-api.sh METHOD /wp-json/... [json]`: authenticated call, used for approved writes only.

See `examples/sample-digest.md` for real output from the test site, and `TESTING.md` for reviewer instructions.

## Requirements and limits
WordPress 5.6+ (Application Passwords), a reachable REST API, and HTTPS (or a local environment). Core and plugin updates have no REST endpoint, so the bot reports them and you apply them (or it uses WP-CLI where shell access exists). Premium plugin versions can't be checked against wordpress.org. MemberPress support is written against its Developer Tools API but hasn't been tested yet.

## License
MIT
