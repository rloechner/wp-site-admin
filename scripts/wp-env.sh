#!/usr/bin/env bash
# Source this to export WP_URL / WP_USER / WP_APP_PASSWORD from the bot's secret store.
# Expected secret names (set during connect-site): WP_SITE_URL, WP_BOT_USER, WP_BOT_APP_PASSWORD.
# Never echo these values.
export WP_URL="${WP_URL:-${WP_SITE_URL:-}}"
export WP_USER="${WP_USER:-${WP_BOT_USER:-wpbot}}"
export WP_APP_PASSWORD="${WP_APP_PASSWORD:-${WP_BOT_APP_PASSWORD:-}}"
[ -n "$WP_URL" ] && [ -n "$WP_APP_PASSWORD" ] || { echo "WP credentials missing: run the connect-site skill" >&2; return 1 2>/dev/null || exit 1; }
