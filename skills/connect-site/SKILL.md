---
name: connect-site
description: "Use when onboarding a new WordPress site or when credentials fail. Walks the owner through creating a dedicated bot administrator (e.g. wpbot) with its own Application Password, stores the URL and credentials as secrets, verifies access via /wp-json/wp/v2/users/me, and detects installed plugins (WooCommerce, subscriptions/membership, SEO, forms)."
---

# Connect a WordPress site

## Why a dedicated bot account
Use a separate administrator user for the bot, never the owner's own login. Every change shows under the bot's name in revisions and logs, the owner can revoke access in one click, and because the bot sees the same wp-admin screens, it can tell the owner exactly where to click to do anything themselves.

## Steps for the owner (send these, in plain words)
1. **Create the bot user**: wp-admin → **Users → Add New User**. Username `wpbot`, a real mailbox they control (e.g. `wpbot@theirdomain.com`), role **Administrator**, strong password (they keep it; the bot doesn't need it). Click **Add New User**.
   - Prefer least privilege? **Editor** works for content-only use, but update checks, plugin listing, users and WooCommerce need Administrator (or Shop Manager for orders).
2. **Create the Application Password**: log in as `wpbot` (or edit that user) → **Users → Profile** (or **Users → All Users → wpbot → Edit**) → scroll to **Application Passwords** → name it `WP Site Admin Bot` → **Add New Application Password**. Copy the 24-character password shown once (spaces are fine).
   - Section missing? The site needs HTTPS (or `WP_ENVIRONMENT_TYPE=local`), or a security plugin (Wordfence, iThemes, etc.) disabled it: re-enable Application Passwords there.
3. Give the bot: site URL, username, application password. **Ask them to paste it into the secret store, not chat**, when the host supports secrets.

## Store as secrets (never in notes, memory, or chat replies)
`WP_SITE_URL` (https://example.com, no trailing slash), `WP_BOT_USER` (wpbot), `WP_BOT_APP_PASSWORD`. Multi-site owners: suffix with a site key (`WP_SITE_URL_SHOP`). Never print the values; `source scripts/wp-env.sh` maps them to the helper's env vars.

## Verify
```bash
source scripts/wp-env.sh && python3 scripts/wpsa.py verify
```
Expect `"ok": true, "is_admin": true`. Troubleshooting:
- **401 `rest_not_logged_in`**: host strips the `Authorization` header (common on Apache/CGI). Owner fix: add `SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1` to `.htaccess`, or ask the host.
- **401 `incorrect_password`**: wrong user or password; regenerate.
- **403/blocked**: security plugin or WAF (Cloudflare, Wordfence) blocking REST; allowlist `/wp-json/`.
- **404 on /wp-json/**: pretty permalinks off. Try `?rest_route=/wp/v2/users/me`, or tell the owner **Settings → Permalinks → Post name → Save**.

## Detect the stack
```bash
python3 scripts/wpsa.py detect
```
Returns plugins (slug, version, active), REST namespaces, and `capabilities` (commerce, subscriptions, membership, seo, forms, security...). Save a short, non-secret site profile in notes (site name, URL, capabilities, plugin list) so other skills know what to check:
- `wc/v3` → WooCommerce checks in users-and-subscriptions. WooCommerce Subscriptions → `/wc/v3/subscriptions`.
- MemberPress / Memberful / PMPro / Restrict Content / Newspack → membership checks (see users-and-subscriptions).
- Yoast / Rank Math / AIOSEO → SEO fields in content-audit.
- CF7 / Flamingo / WPForms / Gravity Forms → help-requests sources.

## Finish
Tell the owner what you found in 4–6 lines, confirm the rules (read-only checks run freely; any change waits for their yes), and offer the daily digest routine (daily-digest skill).
