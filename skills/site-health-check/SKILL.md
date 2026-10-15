---
name: site-health-check
description: "Use to check whether a WordPress site is healthy: uptime and response time, SSL expiry, WordPress core/plugin/theme updates versus wordpress.org, the REST Site Health tests, and failed cron or missed-schedule posts. Read-only; updates are offered, never applied without approval."
---

# Site health check

```bash
source scripts/wp-env.sh && python3 scripts/wpsa.py health
```

## What it checks and how to read it
| Field | Source | Flag when |
|---|---|---|
| `uptime` | GET homepage | not 200, or `slow` (>2 s) |
| `rest_api` | GET /wp-json/ | not ok (bot is blind) |
| `core` | feed generator vs api.wordpress.org version-check | `update: true` |
| `plugins` / `themes` | /wp/v2/plugins, /wp/v2/themes vs wordpress.org info API | `update: true`. Premium plugins (no wp.org entry) show `latest: null`: say "can't verify; check Dashboard → Updates" |
| `ssl` | TLS handshake | `days_left` < 14 urgent, < 30 warn; `https: false` on a live site is a problem |
| `site_health` | /wp-site-health/v1/tests/* | `critical` first, then `recommended` |
| `missed_schedule`, `cron_suspect` | future posts dated in the past; loopback test | any missed post means WP-Cron isn't firing |

## Interpreting common results
- **loopback-requests critical** + missed schedules: WP-Cron can't call itself. Fixes: host firewall/basic-auth blocking loopback, or set a real cron (`DISABLE_WP_CRON` + server cron hitting `wp-cron.php` every 5 min). On local/dev sites this is expected.
- **authorization-header recommended**: header passes poorly; app passwords may break. See connect-site troubleshooting.
- **Security-relevant plugin update** (e.g. a forms plugin several major versions behind): rank as "waiting on you", note changelog risk, recommend a backup first.

## Actions (need approval)
| Action | REST (after yes) | Owner does it at |
|---|---|---|
| Update a plugin, theme, or core | use the **updates** skill (WP-CLI over SSH, companion bridge, or wp-admin; one at a time, backup first, verify after) | **Dashboard → Updates**, or **Plugins → Installed Plugins → update now** |
| Activate/deactivate plugin | `bash scripts/wp-api.sh POST /wp-json/wp/v2/plugins/<file> '{"status":"inactive"}'` | **Plugins → Installed Plugins** |
| Publish a missed post | see content-audit | **Posts → All Posts → Scheduled → Quick Edit** |
| Review all health items | — | **Tools → Site Health** (Status and Info tabs) |

Always recommend a backup (host snapshot or **UpdraftPlus/Jetpack Backup**) before core or major plugin updates.
