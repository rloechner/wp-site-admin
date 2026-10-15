#!/usr/bin/env bash
# Thin authenticated REST wrapper. Usage: wp-api.sh METHOD /wp-json/path ['json-body']
# GET is free. Any other METHOD is a WRITE: only call it after the owner approved that exact change.
set -euo pipefail
. "$(dirname "$0")/wp-env.sh"
m="${1:-GET}"; p="$2"; body="${3:-}"
args=(-sS -u "$WP_USER:$WP_APP_PASSWORD" -X "$m" -H 'Content-Type: application/json' -w '\n[HTTP %{http_code}]\n')
[ -n "$body" ] && args+=(--data "$body")
curl "${args[@]}" "$WP_URL$p"
