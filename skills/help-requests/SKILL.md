---
name: help-requests
description: "Use to triage support requests for a WordPress site: contact form entries (Flamingo, Gravity Forms, WPForms) and support emails, categorize them (login/password, access to paid content, billing, bug, content question, spam), draft replies for the owner to send, and handle common fixes after approval. Never sends a reply unasked."
---

# Help requests

## Sources
```bash
. scripts/wp-env.sh && python3 scripts/wpsa.py help
```
- **Contact Form 7** stores nothing; entries only exist as notification emails. Recommend **Flamingo** (Plugins → Add New → Flamingo) so entries land in **Flamingo → Inbound Messages** and are REST-readable.
- **Flamingo** has no REST API of its own. Install the optional companion `companion/wpsa-rest-bridge.php` into `wp-content/mu-plugins/` (owner uploads it via SFTP/host file manager; one file, delete to revoke). It exposes `/wp/v2/flamingo_inbound` with subject, sender and fields to users who can already read messages in wp-admin. The helper then lists entries with a `category` (login, access, billing, bug, spam, question); spam entries are excluded from the digest.
- **Gravity Forms** (`/wp-json/gf/v2/entries`), **WPForms Pro** entries (**WPForms → Entries**), **Flamingo** (`/wp/v2/flamingo_inbound`).
- **Support email**: read the owner's support mailbox through the connected email tool (Gmail etc.), search for recent unanswered threads to the support address and form notification subjects.

## Triage
For each request: who, what they want, category, urgency, and the evidence you checked on the site (does the user exist? subscription status? order status?). Categories and the usual fix:
| Category | Check | Fix (approval) | Owner path |
|---|---|---|---|
| Can't log in / reset | user exists by email (`/wp/v2/users?search=`) | send reset link | **Users → All Users → Send password reset** |
| Paid but no access | order/subscription status, user role | complete order or set role | **WooCommerce → Orders**; **Users → edit → Role** |
| Billing / cancel | subscription status | owner decides; draft reply | **WooCommerce → Subscriptions** |
| Broken page / bug | fetch the URL; site-health-check | report; propose fix | depends |
| Content question | — | draft answer | — |
| Spam / sales pitch | — | suggest ignore | — |

## Replies
Draft in the owner's voice: short, warm, specific (what you checked, what happens next). Present each draft with recipient and subject. **Never send** email or reply to a form unless the owner explicitly says to send that reply. Never paste passwords or reset links into a draft; WordPress sends reset links itself.
