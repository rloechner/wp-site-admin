# Testing WP Site Admin (for marketplace reviewers)

You need a WordPress site you control (a throwaway one is ideal) running WordPress 5.6+. A free option: `wp-env`, LocalWP, or `docker run -p 8080:80 wordpress` with a MySQL container. On plain HTTP, set `define('WP_ENVIRONMENT_TYPE','local');` in `wp-config.php` so Application Passwords are enabled.

## 1. Seed some problems (optional, makes the output interesting)
Using WP-CLI on the site:
```bash
wp post create --post_title="Missed schedule test" --post_status=future --post_date="$(date -d '-2 days' '+%F %T')"
for i in 1 2 3; do wp post create --post_title="Draft $i" --post_status=draft; done
wp comment create --comment_post_ID=1 --comment_content="Pending comment" --comment_approved=0
wp comment create --comment_post_ID=1 --comment_content="Buy cheap stuff" --comment_approved=spam
wp plugin install contact-form-7 --version=5.9 --activate      # deliberately outdated
wp plugin install woocommerce flamingo --activate                # optional
```
To trigger missed schedules reliably, disable WP-Cron for the test (`define('DISABLE_WP_CRON', true);`).

## 2. Onboard the bot
Ask the bot: **"Connect my WordPress site."** Follow its steps: create user `wpbot` (Administrator), create an Application Password, and give it the URL and credentials. Expected: it confirms `wpbot (administrator)` and lists the detected plugins and capabilities.

## 3. Read-only checks (no approval needed)
| Ask the bot | Expected |
|---|---|
| "Run a health check" | Uptime and response time, SSL status, Contact Form 7 5.9 → latest flagged, Site Health results, the missed-schedule post |
| "Audit my content" | Drafts listed, missed schedule, posts without featured images, pending and spam comment counts, broken internal links (if any) |
| "Any user or order problems?" | Role counts, admin list, new users, WooCommerce order statuses, failed/refunded orders, membership status if PMPro is present |
| "Any help requests?" | Flamingo entries categorized (needs `companion/wpsa-rest-bridge.php` in mu-plugins) |
| "Send me the daily digest" | A digest like `examples/sample-digest.md`; every item has a "Do it yourself" wp-admin path |

Each answer should also tell you where to do the same thing in wp-admin.

## 4. Approval gate (writes)
Ask: **"Publish the missed scheduled post."** Expected: the bot describes the change (post ID, status future → publish) and **waits**. Reply "yes": it calls `POST /wp/v2/posts/<id> {"status":"publish"}`, confirms the new status, and gives the wp-admin path. Repeat with "approve the pending comment" and "delete the spam comments" (it should note that deletion is permanent).

It must never: change anything without a yes, email a customer, or print the application password.

## 5. Updates (writes, approval required)
1. Ask: **"What needs updating?"** Expected: a list (e.g. Contact Form 7 5.9 → latest), a backup check ("no backup plugin found, take a snapshot or install UpdraftPlus"), and a request for your yes. Nothing is updated yet.
2. Install `companion/wpsa-rest-bridge.php` into `wp-content/mu-plugins/`, then reply **"yes, update Contact Form 7"**. Expected: it updates only that plugin (via the bridge), reports old → new version, and runs a site check (homepage 200, login and wp-admin OK, REST OK) with the wp-admin path to do it yourself.
3. Optional WP-CLI path: downgrade a plugin (`wp plugin install akismet --version=5.3 --force`), provide `WP_PATH` (local) or `WP_SSH` + `WP_PATH`, and approve "update akismet". Expected: `via: wp-cli`.
4. Negative checks: `curl <site>/wp-json/wpsa/v1/updates` without auth returns 401, and `python3 scripts/wp-update.py plugin x` without `--yes` refuses.

## 6. Optional: Slack delivery (needs a Slack connector on the host bot)
When asked during onboarding where digests should go, name a test channel. Then ask: **"Send today's digest."** Expected: one headline post in that channel (counts, top items, "reply in chat to approve"), with the full digest as a thread reply, and customer emails masked. Reply "yes, update it" in the Slack thread: the bot must **not** act on it. Offline check: `python3 scripts/wpsa.py digest --format slack` (compare with `examples/sample-digest-slack.txt`).

## 7. Routine
Ask: **"Set up the daily digest."** Expected: an 8 AM daily routine using the prompt in `skills/daily-digest/SKILL.md`. Run the digest twice on different days (or edit `~/.wpsa/state-<host>.json`) to see the "Trend vs previous day" section.

## 8. Revoke
In wp-admin, **Users → wpbot → Application Passwords → Revoke**. Then ask for a health check: the bot should report a 401 and walk you through reconnecting.

## Script-level smoke test (no bot needed)
```bash
export WP_URL=https://your-test-site WP_USER=wpbot WP_APP_PASSWORD='xxxx xxxx xxxx xxxx xxxx xxxx'
python3 scripts/wpsa.py verify && python3 scripts/wpsa.py digest
```
