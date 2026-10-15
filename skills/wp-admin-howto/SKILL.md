---
name: wp-admin-howto
description: "Use whenever the bot takes or proposes an action, or the owner asks 'how do I...' in WordPress: gives exact wp-admin menu paths so the owner can do it themselves. Also defines the approval rule for writes."
---

# Do it yourself: wp-admin paths

**Rule:** after every action you take or propose, add one line: *"To do this yourself: Menu → Submenu → button."* Because the bot uses its own administrator account, its screens match the owner's (menus can vary with plugins and roles; say so if unsure).

**Approval rule:** GET requests run freely. Any POST/PUT/PATCH/DELETE, plugin update, email, or role change: describe the exact change (item, before → after), wait for an explicit yes, do it, then report and give the do-it-yourself path. Deletions and refunds: state that they're irreversible.

| Task | Path |
|---|---|
| Updates (core, plugins, themes) | Dashboard → Updates (bot: updates skill) |
| Auto-updates per plugin | Plugins → Installed Plugins → Enable auto-updates |
| Install/activate/deactivate plugin | Plugins → Installed Plugins / Add New Plugin |
| Site Health | Tools → Site Health (Status, Info) |
| Publish / schedule post | Posts → All Posts → Quick Edit, or editor → Publish panel |
| Drafts / pending | Posts → All Posts → Drafts / Pending |
| Featured image, excerpt | edit post → Post sidebar → Featured image / Excerpt |
| Moderate comments | Comments → Pending / Spam → Empty Spam |
| Discussion settings | Settings → Discussion |
| Users, roles, reset password | Users → All Users → hover → Edit / Send password reset |
| Application Passwords | Users → Profile → Application Passwords |
| Open/close registration | Settings → General → Membership |
| Permalinks | Settings → Permalinks |
| Site title, timezone | Settings → General |
| Menus | Appearance → Menus (classic) or Appearance → Editor → Navigation (block themes) |
| Theme / customize | Appearance → Themes; Appearance → Editor |
| Orders | WooCommerce → Orders |
| Subscriptions | WooCommerce → Subscriptions |
| Products | Products → All Products |
| Store settings, payments | WooCommerce → Settings → Payments |
| Forms (CF7) | Contact → Contact Forms; entries via Flamingo → Inbound Messages |
| SEO (Yoast / Rank Math) | Yoast SEO → Settings / Rank Math → Dashboard; per-post in editor sidebar |
| Redirects | Tools → Redirection (plugin) |
| Export / import | Tools → Export / Import |
| Media | Media → Library |
