---
name: content-audit
description: "Use to audit WordPress content: stuck or stale drafts, posts pending review, missed scheduled posts, published posts missing a featured image or excerpt, pending and spam comments, and broken internal links. Read-only; fixes (publish, moderate, empty spam) need the owner's approval."
---

# Content audit

```bash
source scripts/wp-env.sh && python3 scripts/wpsa.py content
```
Returns `drafts` (with `days_since_edit`, `stale` ≥30 days), `pending_review`, `missed_schedule`, `no_featured_image`, `no_manual_excerpt`, `comments` (pending/spam counts) with samples, and `broken_internal_links` (links to the site's own host returning 4xx/5xx or no response).

## Reporting
Lead with what costs readers or revenue (missed schedules, broken links), then the queue the owner must act on (pending comments, pending review), then hygiene (images, excerpts). Name posts by title, up to 5, then "and N more". The default "Hello world!" post often shows up in hygiene lists; suggest deleting it.

If an SEO plugin is active, also check meta: Yoast exposes `yoast_head_json` on posts; Rank Math and AIOSEO store meta that may need their own REST routes. Flag posts with no meta description.

## Fixes (each needs a yes; say exactly what will change)
| Fix | REST call after approval | Owner path |
|---|---|---|
| Publish missed post | `bash scripts/wp-api.sh POST /wp-json/wp/v2/posts/<id> '{"status":"publish"}'` | **Posts → All Posts → Scheduled → hover → Quick Edit → Status: Published → Update** |
| Approve comment | `POST /wp-json/wp/v2/comments/<id> '{"status":"approved"}'` | **Comments → Pending → Approve** |
| Mark spam | `POST /wp-json/wp/v2/comments/<id> '{"status":"spam"}'` | **Comments → hover → Spam** |
| Delete spam permanently | `DELETE /wp-json/wp/v2/comments/<id>?force=true` (irreversible) | **Comments → Spam → Empty Spam** |
| Set featured image | `POST /wp-json/wp/v2/posts/<id> '{"featured_media":<media_id>}'` | edit post → **Post** sidebar → **Featured image → Set** |
| Add excerpt | `POST /wp-json/wp/v2/posts/<id> '{"excerpt":"..."}'` (show draft first) | edit post → **Post** sidebar → **Excerpt** |
| Trash a stale draft | `DELETE /wp-json/wp/v2/posts/<id>` (to Trash; recoverable 30 days) | **Posts → Drafts → Trash** |
| Fix a broken link | edit content; show before/after | edit post → select link → edit URL. Many: **Redirection** plugin (**Tools → Redirection**) |

Missed schedules mean cron is broken; also run site-health-check.
