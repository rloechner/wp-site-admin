---
name: users-and-subscriptions
description: "Use to triage WordPress users and revenue: new signups, suspicious accounts, role audit (who is an administrator), WooCommerce orders and failed payments, and failed, on-hold or expiring subscriptions (WooCommerce Subscriptions, MemberPress, Memberful, Paid Memberships Pro, Newspack). Read-only; role changes, deletions, refunds need approval."
---

# Users and subscriptions

```bash
. scripts/wp-env.sh && python3 scripts/wpsa.py users
```
Returns totals, `site_age_days`, `admin_baseline`, `roles`, `administrators`, `new_users` (last 7 days), `suspicious` (disposable email, random-looking username, new administrators other than the bot), and, when WooCommerce is present, products, `orders_by_status`, `failed_orders`, and `subscriptions` (by status, on-hold/pending-cancel, ending within 14 days).

## New-admin flag (low noise)
An administrator is flagged only if (a) a known-admin baseline exists (saved by the first digest in the state file, or `WPSA_KNOWN_ADMINS=alice,bob`) and they're not in it, or (b) no baseline yet and they were created more than 24 h after the site's first account (setup window) and within the last 7 days. The bot's own account is never flagged. When the owner confirms a new admin is legitimate, add it to `known_admins` in the state file.

## Role audit rules
- Every administrator should be a person the owner recognizes, plus the bot. An unknown or freshly created admin is **urgent** (possible compromise): tell the owner immediately and suggest **Users → All Users → filter Administrator**.
- Too many admins: suggest Editor for writers, Shop Manager for store staff.
- Spam signups: many subscribers with disposable domains → suggest turning off **Settings → General → Membership: Anyone can register** if not needed, or adding a captcha/Akismet.

## Revenue checks
- **Failed orders** (`status=failed`): list order #, amount, customer email. Owner path: **WooCommerce → Orders → Failed**. Suggest a polite payment-retry email (draft only).
- **WooCommerce Subscriptions** (`/wc/v3/subscriptions`): `on-hold` usually = failed renewal; `pending-cancel` = ending at period end. Path: **WooCommerce → Subscriptions**.
- **Paid Memberships Pro** (`pmpro` block, tested): reads `/pmpro/v1/membership_levels`, `recent_memberships`, `recent_orders`, and `get_membership_level_for_user` for end dates. Reports `active_by_level`, `expiring_soon` (≤14 days), `expired_or_lapsed` (paid before, no active level now = win-back), `failed_payments` (order status error/failed), `refunded`. Needs PMPro 3.x (older 3.2-era builds have a REST permission bug that returns 403 to admins; PMPro is no longer on wordpress.org, so sites update from paidmembershipspro.com). Paths: **Memberships → Members**, **Memberships → Orders**, **Memberships → Members → Old Members**.
  - Fixes (approval): change/cancel level `POST /wp-json/pmpro/v1/change_membership_level {"user_id":N,"level_id":L}` / `cancel_membership_level`. Owner: **Users → edit user → Membership Levels**.
- **MemberPress** (`memberpress` block, untested, paid plugin): `/wp-json/mp/v1/members|subscriptions|transactions` from the MemberPress Developer Tools add-on; some sites require the `MEMBERPRESS-API-KEY` header (**MemberPress → Developer**). Paths: **MemberPress → Members / Subscriptions / Transactions**.
- **Memberful** is hosted: use its dashboard or webhooks. **Newspack** uses WooCommerce Subscriptions under the hood.

## Common user fixes (need approval)
| Task | REST after yes | Owner path |
|---|---|---|
| Send password reset | no core REST; tell owner, or use WP-CLI `wp user reset-password <user>` | **Users → All Users → hover user → Send password reset** |
| Change role | `wp-api.sh POST /wp-json/wp/v2/users/<id> '{"roles":["editor"]}'` | **Users → All Users → edit → Role** |
| Delete user (reassign content!) | `DELETE /wp-json/wp/v2/users/<id>?force=true&reassign=<id>` (irreversible) | **Users → All Users → Delete → Attribute content to** |
| Retry/complete order | `PUT /wp-json/wc/v3/orders/<id> '{"status":"processing"}'` | **WooCommerce → Orders → open → Status** |
| Refund | never without explicit amount + yes | **WooCommerce → Orders → open → Refund** |

Never expose customer emails outside the owner's chat.
