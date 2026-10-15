#!/usr/bin/env python3
"""WP Site Admin helper. Read-only checks over the WordPress REST API.

Env: WP_URL, WP_USER (bot admin login, e.g. wpbot), WP_APP_PASSWORD (Application Password).
Usage: wpsa.py <verify|detect|health|content|users|help|digest|state>
State (trends, known-admin baseline) lives in $WPSA_STATE_DIR (default ~/.wpsa)/state-<host>.json; digest updates it.
Never prints credentials. Performs only GET requests (plus public wordpress.org lookups).
"""
import base64, json, os, re, socket, ssl, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone, timedelta

URL = os.environ.get("WP_URL", "").rstrip("/")
USER = os.environ.get("WP_USER", "")
PW = os.environ.get("WP_APP_PASSWORD", "")
TIMEOUT = 20

def die(msg):
    print(json.dumps({"error": msg})); sys.exit(2)

def req(path, auth=True, raw=False, absolute=False):
    u = path if absolute else URL + path
    r = urllib.request.Request(u, headers={"User-Agent": "WP-Site-Admin-Bot/0.1"})
    if auth and not absolute:
        r.add_header("Authorization", "Basic " + base64.b64encode(f"{USER}:{PW}".encode()).decode())
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=TIMEOUT) as resp:
            body = resp.read(); hdr = dict(resp.headers); code = resp.status
    except urllib.error.HTTPError as e:
        body = e.read(); hdr = dict(e.headers); code = e.code
    except Exception as e:
        return {"ok": False, "code": None, "error": str(e), "ms": int((time.time()-t0)*1000)}
    out = {"ok": 200 <= code < 300, "code": code, "ms": int((time.time()-t0)*1000), "headers": hdr}
    if raw: out["text"] = body.decode("utf-8", "replace")
    else:
        try: out["data"] = json.loads(body)
        except Exception: out["text"] = body.decode("utf-8", "replace")[:500]
    return out

def get(path, **kw):
    r = req(path, **kw); return r.get("data") if r["ok"] else None

def get_all(path, cap=500):
    items, page = [], 1
    sep = "&" if "?" in path else "?"
    while len(items) < cap:
        r = req(f"{path}{sep}per_page=100&page={page}")
        if not r["ok"] or not isinstance(r.get("data"), list): break
        items += r["data"]
        if page >= int(r["headers"].get("X-WP-TotalPages", 1)): break
        page += 1
    return items

def total(path):
    r = req(path + ("&" if "?" in path else "?") + "per_page=1")
    return int(r["headers"].get("X-WP-Total", 0)) if r["ok"] else None

# ---------------- state (day-over-day trends, known admins) ----------------
def state_path():
    host = urllib.parse.urlparse(URL).netloc.replace(":", "_") or "site"
    d = os.environ.get("WPSA_STATE_DIR", os.path.expanduser("~/.wpsa"))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"state-{host}.json")

def load_state():
    try: return json.load(open(state_path()))
    except Exception: return {}

def save_state(st):
    json.dump(st, open(state_path(), "w"), indent=2)

def parse_dt(v):
    if not v: return None
    d = datetime.fromisoformat(v.replace("Z", "+00:00").replace(" ", "T"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

# ---------------- checks ----------------
KNOWN = {
  "woocommerce": "WooCommerce", "woocommerce-subscriptions": "WooCommerce Subscriptions",
  "memberpress": "MemberPress", "memberful-wp": "Memberful", "paid-memberships-pro": "Paid Memberships Pro",
  "restrict-content-pro": "Restrict Content Pro", "restrict-content": "Restrict Content", "newspack": "Newspack",
  "wordpress-seo": "Yoast SEO", "seo-by-rank-math": "Rank Math", "all-in-one-seo-pack": "AIOSEO",
  "contact-form-7": "Contact Form 7", "wpforms-lite": "WPForms", "wpforms": "WPForms Pro", "gravityforms": "Gravity Forms",
  "ninja-forms": "Ninja Forms", "formidable": "Formidable", "flamingo": "Flamingo (CF7 entries)",
  "jetpack": "Jetpack", "wordfence": "Wordfence", "akismet": "Akismet", "wp-mail-smtp": "WP Mail SMTP",
}
CATEGORY = {"woocommerce": "commerce", "woocommerce-subscriptions": "subscriptions", "memberpress": "membership",
  "memberful-wp": "membership", "paid-memberships-pro": "membership", "restrict-content-pro": "membership",
  "restrict-content": "membership", "newspack": "publishing", "wordpress-seo": "seo", "seo-by-rank-math": "seo",
  "all-in-one-seo-pack": "seo", "contact-form-7": "forms", "wpforms-lite": "forms", "wpforms": "forms",
  "gravityforms": "forms", "ninja-forms": "forms", "formidable": "forms", "flamingo": "forms",
  "wordfence": "security", "akismet": "spam", "jetpack": "suite", "wp-mail-smtp": "email"}

def verify():
    r = req("/wp-json/wp/v2/users/me?context=edit")
    if not r["ok"]:
        return {"ok": False, "code": r["code"], "hint": "401 = wrong user/app password or auth header stripped by host; 404 = REST API disabled or wrong URL"}
    d = r["data"]
    return {"ok": True, "user": d.get("slug"), "name": d.get("name"), "roles": d.get("roles"),
            "is_admin": "administrator" in (d.get("roles") or [])}

def detect():
    plugins = get("/wp-json/wp/v2/plugins") or []
    root = get("/wp-json/", auth=False) or {}
    found = []
    for p in plugins:
        slug = p["plugin"].split("/")[0]
        found.append({"slug": slug, "file": p["plugin"], "name": p.get("name"), "version": p.get("version"),
                      "status": p.get("status"), "known": KNOWN.get(slug), "category": CATEGORY.get(slug)})
    ns = root.get("namespaces", [])
    caps = sorted({f["category"] for f in found if f["category"] and f["status"] == "active"})
    if "wc/v3" in ns: caps.append("wc-rest")
    if any(n.startswith("wc/v3") for n in ns) and any(f["slug"] == "woocommerce-subscriptions" and f["status"]=="active" for f in found):
        caps.append("wc-subscriptions-rest")
    return {"site": root.get("name"), "url": root.get("url"), "plugins": found, "namespaces": ns, "capabilities": sorted(set(caps))}

def wporg_plugin_latest(slug):
    d = req(f"https://api.wordpress.org/plugins/info/1.2/?action=plugin_information&request[slug]={slug}&request[fields][sections]=0", absolute=True)
    return (d.get("data") or {}).get("version") if d["ok"] else None

def wporg_theme_latest(slug):
    d = req(f"https://api.wordpress.org/themes/info/1.2/?action=theme_information&request[slug]={slug}", absolute=True)
    return (d.get("data") or {}).get("version") if d["ok"] else None

def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "0")[:4])

def core_version():
    r = req("/feed/", auth=False, raw=True)
    m = re.search(r"wordpress\.org/\?v=([\d.]+)", r.get("text", "") or "")
    if m: return m.group(1)
    r = req("/", auth=False, raw=True)
    m = re.search(r'content="WordPress ([\d.]+)', r.get("text", "") or "")
    return m.group(1) if m else None

def ssl_info():
    p = urllib.parse.urlparse(URL)
    if p.scheme != "https": return {"https": False, "note": "Site is not served over HTTPS"}
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((p.hostname, p.port or 443), timeout=10) as s:
            with ctx.wrap_socket(s, server_hostname=p.hostname) as ss:
                c = ss.getpeercert()
        exp = datetime.strptime(c["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        return {"https": True, "expires": exp.date().isoformat(), "days_left": (exp - datetime.now(timezone.utc)).days,
                "issuer": dict(x[0] for x in c["issuer"]).get("organizationName")}
    except Exception as e:
        return {"https": True, "error": str(e)}

def missed_schedule():
    now = datetime.now(timezone.utc)
    out = []
    for p in get_all("/wp-json/wp/v2/posts?status=future&context=edit&_fields=id,title,date_gmt,link"):
        d = datetime.fromisoformat(p["date_gmt"]).replace(tzinfo=timezone.utc)
        if d < now: out.append({"id": p["id"], "title": p["title"]["raw"], "scheduled_gmt": p["date_gmt"], "late_hours": round((now-d).total_seconds()/3600, 1)})
    return out

def health():
    res = {"checked_at": datetime.now().isoformat(timespec="minutes")}
    home = req("/", auth=False, raw=True)
    res["uptime"] = {"up": home["ok"], "code": home["code"], "response_ms": home["ms"], "slow": home["ms"] > 2000}
    api = req("/wp-json/", auth=False)
    res["rest_api"] = {"ok": api["ok"], "response_ms": api["ms"]}
    cv = core_version(); latest = None
    vc = req("https://api.wordpress.org/core/version-check/1.7/", absolute=True)
    if vc["ok"]: latest = vc["data"]["offers"][0]["current"]
    res["core"] = {"installed": cv, "latest": latest, "update": bool(cv and latest and vtuple(cv) < vtuple(latest))}
    ups = []
    for p in get("/wp-json/wp/v2/plugins") or []:
        slug = p["plugin"].split("/")[0]
        if "/" not in p["plugin"]: slug = p["plugin"]
        lv = wporg_plugin_latest({"hello": "hello-dolly"}.get(slug, slug))
        ups.append({"slug": slug, "name": p["name"], "status": p["status"], "installed": p["version"], "latest": lv,
                    "update": bool(lv and vtuple(p["version"]) < vtuple(lv))})
    res["plugins"] = ups
    th = []
    for t in get("/wp-json/wp/v2/themes") or []:
        lv = wporg_theme_latest(t["stylesheet"])
        th.append({"slug": t["stylesheet"], "status": t["status"], "installed": t["version"], "latest": lv,
                   "update": bool(lv and vtuple(t["version"]) < vtuple(lv))})
    res["themes"] = th
    res["ssl"] = ssl_info()
    sh = {}
    for test in ["background-updates", "loopback-requests", "dotorg-communication", "authorization-header", "page-cache"]:
        r = req(f"/wp-json/wp-site-health/v1/tests/{test}")
        if r["ok"] and isinstance(r.get("data"), dict):
            sh[test] = {"status": r["data"].get("status"), "label": r["data"].get("label")}
        else: sh[test] = {"status": "unavailable", "code": r["code"]}
    res["site_health"] = sh
    res["missed_schedule"] = missed_schedule()
    res["cron_suspect"] = bool(res["missed_schedule"]) or sh.get("loopback-requests", {}).get("status") == "critical"
    return res

def content(link_check=True, stale_days=30):
    now = datetime.now(timezone.utc)
    f = "id,title,date_gmt,modified_gmt,featured_media,excerpt,link,status,content"
    pub = get_all(f"/wp-json/wp/v2/posts?status=publish&context=edit&_fields={f}")
    drafts = get_all(f"/wp-json/wp/v2/posts?status=draft&context=edit&_fields=id,title,modified_gmt")
    pending = get_all("/wp-json/wp/v2/posts?status=pending&context=edit&_fields=id,title,modified_gmt")
    res = {"published_posts": len(pub), "drafts": [], "pending_review": [{"id": p["id"], "title": p["title"]["raw"]} for p in pending]}
    for d in drafts:
        age = (now - datetime.fromisoformat(d["modified_gmt"]).replace(tzinfo=timezone.utc)).days
        res["drafts"].append({"id": d["id"], "title": d["title"]["raw"] or "(no title)", "days_since_edit": age, "stale": age >= stale_days})
    res["missed_schedule"] = missed_schedule()
    res["no_featured_image"] = [{"id": p["id"], "title": p["title"]["raw"]} for p in pub if not p.get("featured_media")]
    res["no_manual_excerpt"] = [{"id": p["id"], "title": p["title"]["raw"]} for p in pub if not (p.get("excerpt", {}).get("raw") or "").strip()]
    res["comments"] = {"pending": total("/wp-json/wp/v2/comments?status=hold&context=edit"),
                       "spam": total("/wp-json/wp/v2/comments?status=spam&context=edit")}
    res["pending_comment_samples"] = [{"id": c["id"], "post": c["post"], "author": c["author_name"], "excerpt": re.sub("<[^>]+>", "", c["content"]["rendered"])[:80].strip()}
        for c in (get("/wp-json/wp/v2/comments?status=hold&context=edit&per_page=10") or [])]
    broken = []
    if link_check:
        host = urllib.parse.urlparse(URL).netloc
        seen = {}
        for p in pub:
            html = p.get("content", {}).get("rendered") or p.get("content", {}).get("raw") or ""
            for href in set(re.findall(r'href=["\']([^"\'#]+)', html)):
                full = urllib.parse.urljoin(URL + "/", href)
                if urllib.parse.urlparse(full).netloc != host: continue
                if full not in seen:
                    seen[full] = req(full, absolute=True)["code"]
                if seen[full] is None or seen[full] >= 400:
                    broken.append({"post_id": p["id"], "title": p["title"]["raw"], "url": full, "code": seen[full]})
        res["internal_links_checked"] = len(seen)
    res["broken_internal_links"] = broken
    return res

SUSPICIOUS_DOMAINS = ("mailinator", "tempmail", "guerrillamail", "10minutemail", "yopmail", "sharklasers", "trashmail")
def users(days=7):
    now = datetime.now(timezone.utc)
    us = get_all("/wp-json/wp/v2/users?context=edit&_fields=id,username,name,email,roles,registered_date")
    roles = {}
    for u in us:
        for r in u.get("roles") or []: roles[r] = roles.get(r, 0) + 1
    new, sus = [], []
    regs = [parse_dt(u.get("registered_date")) for u in us if u.get("registered_date")]
    site_born = min(regs) if regs else now
    site_age_days = (now - site_born).days
    setup_window = site_born + timedelta(hours=24)
    st = load_state()
    known_admins = set(st.get("known_admins") or []) | set(filter(None, os.environ.get("WPSA_KNOWN_ADMINS", "").split(",")))
    for u in us:
        reg = datetime.fromisoformat(u["registered_date"].replace("Z", "+00:00")) if u.get("registered_date") else None
        if reg and reg.tzinfo is None: reg = reg.replace(tzinfo=timezone.utc)
        if reg and (now - reg).days <= days: new.append({"id": u["id"], "username": u["username"], "roles": u["roles"], "registered": u["registered_date"]})
        flags = []
        em = (u.get("email") or "").lower()
        if any(d in em for d in SUSPICIOUS_DOMAINS): flags.append("disposable email")
        if re.fullmatch(r"[a-z]{0,3}\d{5,}|[a-z0-9]{14,}", u["username"] or ""): flags.append("random-looking username")
        if "administrator" in (u.get("roles") or []) and u["username"] != USER:
            if known_admins:
                if u["username"] not in known_admins: flags.append("administrator not in known-admin baseline")
            elif reg and reg > setup_window and (now - reg).days <= days:
                flags.append("NEW administrator (created after site setup)")
        if flags: sus.append({"id": u["id"], "username": u["username"], "flags": flags})
    res = {"total_users": len(us), "roles": roles, "site_age_days": site_age_days,
           "admin_baseline": sorted(known_admins) or "none yet (setup-window rule used; digest saves one)",
           "administrators": [u["username"] for u in us if "administrator" in (u.get("roles") or [])],
           "new_last_days": days, "new_users": new, "suspicious": sus}
    ns = (get("/wp-json/", auth=False) or {}).get("namespaces", [])
    if "wc/v3" in ns:
        wc = {"products": total("/wp-json/wc/v3/products?status=any")}
        r = req("/wp-json/wc/v3/orders?per_page=100")
        orders = r.get("data") if r["ok"] else []
        st = {}
        for o in orders or []: st[o["status"]] = st.get(o["status"], 0) + 1
        wc["orders_by_status"] = st
        wc["failed_orders"] = [{"id": o["id"], "total": o["total"], "email": o["billing"].get("email")} for o in orders or [] if o["status"] == "failed"]
        wc["refunded_orders"] = [{"id": o["id"], "total": o["total"], "email": o["billing"].get("email")} for o in orders or [] if o["status"] == "refunded"]
        wc["on_hold_orders"] = [{"id": o["id"], "total": o["total"]} for o in orders or [] if o["status"] == "on-hold"]
        wc["orders_total_seen"] = len(orders or [])
        s = req("/wp-json/wc/v3/subscriptions?per_page=100")
        if s["ok"]:
            subs = s["data"]; soon = now + timedelta(days=14); sst = {}
            for x in subs: sst[x["status"]] = sst.get(x["status"], 0) + 1
            wc["subscriptions"] = {"by_status": sst,
                "on_hold_or_failed": [{"id": x["id"], "status": x["status"], "email": x["billing"].get("email")} for x in subs if x["status"] in ("on-hold", "pending-cancel")],
                "ending_14d": [{"id": x["id"], "end": x.get("end_date_gmt")} for x in subs if x.get("end_date_gmt") and x["end_date_gmt"][:4] != "0000" and datetime.fromisoformat(x["end_date_gmt"]).replace(tzinfo=timezone.utc) < soon]}
        else:
            wc["subscriptions"] = "WooCommerce Subscriptions not installed (no /wc/v3/subscriptions)"
        res["woocommerce"] = wc
    if "pmpro/v1" in ns: res["pmpro"] = pmpro()
    if "mp/v1" in ns: res["memberpress"] = memberpress()
    return res

def pmpro(expiring_days=14):
    """Paid Memberships Pro via its REST API (needs PMPro 3.x+; admin needs pmpro_edit_members / pmpro_orders)."""
    now = datetime.now(timezone.utc)
    out = {"levels": {}}
    lv = get("/wp-json/pmpro/v1/membership_levels") or {}
    out["levels"] = {k: v.get("name") for k, v in lv.items()} if isinstance(lv, dict) else {}
    rm = req("/wp-json/pmpro/v1/recent_memberships?limit=100")
    ro = req("/wp-json/pmpro/v1/recent_orders?limit=100")
    if not rm["ok"] or not ro["ok"]:
        out["error"] = f"members/orders endpoints returned HTTP {rm['code']}/{ro['code']}; PMPro older than 3.x has a REST permission bug, or the bot lacks pmpro_edit_members"
        return out
    members = rm["data"] or []; orders = ro["data"] or []
    active, expiring = [], []
    for m in members:
        if m.get("status") != "active": continue
        lvl = get(f"/wp-json/pmpro/v1/get_membership_level_for_user?user_id={m['id']}") or {}
        end = lvl.get("enddate")
        endd = datetime.fromtimestamp(int(end), timezone.utc) if str(end or "").isdigit() and int(end) > 0 else None
        row = {"user_id": m["id"], "user": m["user_nicename"], "level": m["membership_name"], "ends": endd.date().isoformat() if endd else None}
        active.append(row)
        if endd and endd < now + timedelta(days=expiring_days): expiring.append(row)
    active_ids = {str(a["user_id"]) for a in active}
    paid_users = {}
    for o in orders:
        if o["status"] == "success": paid_users[str(o["user_id"])] = o
    lapsed = [{"user_id": int(uid), "user": o["user_nicename"], "last_paid": o["timestamp"][:10]} for uid, o in paid_users.items() if uid not in active_ids]
    failed = [{"order": o["code"], "user": o["user_nicename"], "total": o["total"], "date": o["timestamp"][:10]} for o in orders if o["status"] in ("error", "failed", "review")]
    refunded = [{"order": o["code"], "user": o["user_nicename"], "total": o["total"]} for o in orders if o["status"] == "refunded"]
    by = {}
    for a in active: by[a["level"]] = by.get(a["level"], 0) + 1
    out.update({"active_by_level": by, "active_members": len(active), "expiring_soon": expiring, "expired_or_lapsed": lapsed,
                "failed_payments": failed, "refunded": refunded, "orders_seen": len(orders)})
    return out

def memberpress():
    """MemberPress Developer Tools REST (mp/v1). Untested: MemberPress is a paid plugin. Some sites require the MEMBERPRESS-API-KEY header instead of Basic auth."""
    out = {}
    for key, path in [("members", "/wp-json/mp/v1/members?per_page=100"), ("subscriptions", "/wp-json/mp/v1/subscriptions?per_page=100"), ("transactions", "/wp-json/mp/v1/transactions?per_page=100")]:
        r = req(path)
        out[key] = r["data"] if r["ok"] else f"HTTP {r['code']} (Developer Tools add-on / API key may be required)"
    subs = out.get("subscriptions")
    if isinstance(subs, list):
        by = {}
        for x in subs: by[x.get("status")] = by.get(x.get("status"), 0) + 1
        out["subscriptions_by_status"] = by
    tx = out.get("transactions")
    if isinstance(tx, list):
        out["failed_transactions"] = [{"id": t.get("id"), "amount": t.get("amount"), "member": t.get("member")} for t in tx if t.get("status") == "failed"]
    return out

CATS = [("login", r"password|reset|log ?in|locked out|can.?t sign"), ("access", r"access|members only|premium|paywall|can.?t see|upgrade"),
        ("billing", r"charg|bill|refund|invoice|payment|cancel|subscription"), ("bug", r"error|broken|404|not working|crash|blank"),
        ("spam", r"seo|rank #?1|guarantee|backlink|crypto|casino")]
def categorize(text):
    t = (text or "").lower()
    for name, rx in CATS:
        if re.search(rx, t): return name
    return "question"

def plugs_active():
    return {p["plugin"].split("/")[0] for p in (get("/wp-json/wp/v2/plugins") or []) if p.get("status") == "active"}

def help_requests():
    """Form entries available via REST. CF7 stores nothing by default; Flamingo/WPForms/Gravity do."""
    ns = (get("/wp-json/", auth=False) or {}).get("namespaces", [])
    res = {"sources": []}
    if "contact-form-7/v1" in ns:
        forms = get("/wp-json/contact-form-7/v1/contact-forms") or []
        res["sources"].append({"plugin": "Contact Form 7", "forms": [f.get("title") for f in forms],
            "entries": "CF7 stores no entries itself; read via Flamingo" if "flamingo" in plugs_active() else "not stored by CF7; install Flamingo to keep entries, otherwise triage from the notification inbox"})
    plugs = {p["plugin"].split("/")[0]: p["status"] for p in (get("/wp-json/wp/v2/plugins") or [])}
    if plugs.get("flamingo") == "active":
        fl = req("/wp-json/wp/v2/flamingo_inbound?context=edit&per_page=50&_fields=id,date_gmt,wpsa")
        if fl["ok"]:
            entries = []
            for e in fl["data"]:
                w = e.get("wpsa") or {}
                msg = (w.get("fields") or {}).get("your-message") or " ".join(str(v) for v in (w.get("fields") or {}).values())
                entries.append({"id": e["id"], "date_gmt": e["date_gmt"], "from": f"{w.get('from_name')} <{w.get('from_email')}>",
                                "subject": w.get("subject"), "message": msg[:400], "category": categorize((w.get("subject") or "") + " " + msg)})
            res["sources"].append({"plugin": "Flamingo", "entries": entries})
        else:
            res["sources"].append({"plugin": "Flamingo", "entries": "Flamingo is active but not exposed to REST; install companion/wpsa-rest-bridge.php as an mu-plugin, or triage in Flamingo → Inbound Messages"})
    if "gf/v2" in ns:
        g = req("/wp-json/gf/v2/entries?paging[page_size]=50")
        res["sources"].append({"plugin": "Gravity Forms", "entries": g.get("data") if g["ok"] else f"HTTP {g['code']}"})
    if not res["sources"]: res["note"] = "No form plugin with REST-readable entries; use the support mailbox."
    return res

def digest():
    v = verify(); h = health(); c = content(); u = users(); hr = help_requests()
    site = (get("/wp-json/", auth=False) or {}).get("name", URL)
    L = [f"# WP Site Admin daily digest: {site}", f"_{URL} · {datetime.now().strftime('%a %b %d, %Y %I:%M %p')} (site-local box time)_", ""]
    urgent, waiting, fyi = [], [], []
    if not h["uptime"]["up"]: urgent.append(f"Site is DOWN (HTTP {h['uptime']['code']})")
    if h["ssl"].get("days_left") is not None and h["ssl"]["days_left"] < 14: urgent.append(f"SSL certificate expires in {h['ssl']['days_left']} days")
    for m in h["missed_schedule"]: urgent.append(f"Missed scheduled post: \"{m['title']}\" (ID {m['id']}), {m['late_hours']} h late. *Do it yourself:* Posts → All Posts → filter Scheduled → Quick Edit → set status Published.")
    pu = [p for p in h["plugins"] if p["update"]]
    for p in pu: waiting.append(f"Plugin update: {p['name']} {p['installed']} → {p['latest']} ({p['status']}). Say \"update {p['slug']}\" and I'll back up, update it alone, and check the site (updates skill). *Do it yourself:* Dashboard → Updates.")
    if h["core"]["update"]: waiting.append(f"WordPress core {h['core']['installed']} → {h['core']['latest']}. Approve and I'll update it last, on its own (updates skill). *Do it yourself:* Dashboard → Updates.")
    for t in h["themes"]:
        if t["update"]: waiting.append(f"Theme update: {t['slug']} {t['installed']} → {t['latest']}. Approve and I'll update it (updates skill). *Do it yourself:* Dashboard → Updates or Appearance → Themes.")
    cm = c["comments"]
    if cm["pending"]: waiting.append(f"{cm['pending']} comments awaiting moderation. *Do it yourself:* Comments → Pending.")
    if cm["spam"]: fyi.append(f"{cm['spam']} comments in spam (safe to empty). *Do it yourself:* Comments → Spam → Empty Spam.")
    if c["drafts"]: waiting.append(f"{len(c['drafts'])} drafts ({sum(d['stale'] for d in c['drafts'])} untouched 30+ days): " + ", ".join(f"\"{d['title']}\"" for d in c["drafts"][:5]) + ". *Do it yourself:* Posts → All Posts → Drafts.")
    if c["no_featured_image"]: fyi.append(f"{len(c['no_featured_image'])} published posts have no featured image. *Do it yourself:* edit the post → Post settings sidebar → Featured image.")
    if c["no_manual_excerpt"]: fyi.append(f"{len(c['no_manual_excerpt'])} published posts have no manual excerpt.")
    if c["broken_internal_links"]: waiting.append(f"{len(c['broken_internal_links'])} broken internal links, e.g. {c['broken_internal_links'][0]['url']} in \"{c['broken_internal_links'][0]['title']}\".")
    for s in u["suspicious"]: urgent.append(f"Suspicious user {s['username']}: {', '.join(s['flags'])}. *Do it yourself:* Users → All Users.")
    crit = [k for k, x in h["site_health"].items() if x.get("status") == "critical"]
    if crit: waiting.append("Site Health critical: " + ", ".join(crit) + ". *Do it yourself:* Tools → Site Health.")
    if "woocommerce" in u:
        w = u["woocommerce"]
        for o in w["failed_orders"]: urgent.append(f"Failed WooCommerce order #{o['id']} ({o['total']}, {o['email']}). *Do it yourself:* WooCommerce → Orders → Failed.")
        if w["on_hold_orders"]: waiting.append(f"{len(w['on_hold_orders'])} order(s) on hold awaiting payment confirmation. *Do it yourself:* WooCommerce → Orders → On hold.")
        for o in w["refunded_orders"]: fyi.append(f"Order #{o['id']} refunded ({o['total']}).")
    pm = u.get("pmpro") or {}
    for f in pm.get("failed_payments", []): urgent.append(f"Failed membership payment: {f['user']} ({f['total']}, order {f['order']}, {f['date']}). *Do it yourself:* Memberships → Orders → filter Error.")
    for e in pm.get("expiring_soon", []): waiting.append(f"Membership expiring: {e['user']} ({e['level']}) ends {e['ends']}. *Do it yourself:* Memberships → Members → edit member.")
    for e in pm.get("expired_or_lapsed", []): fyi.append(f"Lapsed member: {e['user']} paid last on {e['last_paid']}, no active level now (win-back candidate). *Do it yourself:* Memberships → Members → Old Members.")
    if pm.get("error"): fyi.append("Paid Memberships Pro: " + pm["error"])
    helps = [e for s_ in hr["sources"] if isinstance(s_.get("entries"), list) for e in s_["entries"]]
    real = [e for e in helps if e.get("category") != "spam"]
    if real:
        waiting.append(f"{len(real)} help request(s) need replies (drafts ready on request): " + "; ".join(f"{e['from'].split(' <')[0]}: \"{e['subject']}\" [{e['category']}]" for e in real[:5]) + ". *Do it yourself:* Flamingo → Inbound Messages.")
    # trends
    st = load_state()
    today = datetime.now().strftime("%Y-%m-%d")
    w = u.get("woocommerce", {})
    counts = {"published": c["published_posts"], "drafts": len(c["drafts"]), "pending_comments": cm["pending"] or 0, "users": u["total_users"],
              "orders": w.get("orders_total_seen", 0), "failed_orders": len(w.get("failed_orders", [])), "active_members": pm.get("active_members", 0),
              "plugin_updates": len(pu), "help_requests": len(real), "homepage_ms": h["uptime"]["response_ms"]}
    hist = st.get("history", {})
    prev_day = max([d for d in hist if d < today], default=None)
    trend = []
    if prev_day:
        for k, cv in counts.items():
            pv = hist[prev_day].get(k)
            if pv is not None and pv != cv and k != "homepage_ms": trend.append(f"{k.replace('_', ' ')} {pv} → {cv}")
        pms = hist[prev_day].get("homepage_ms")
        if pms: trend.append(f"homepage {pms} → {counts['homepage_ms']} ms")
    hist[today] = counts
    st["history"] = dict(sorted(hist.items())[-60:])
    if not st.get("known_admins"): st["known_admins"] = u["administrators"]
    save_state(st)
    L += ["## 🔴 Needs attention now"] + ([f"- {x}" for x in urgent] or ["- Nothing urgent."]) + [""]
    L += ["## 🟡 Waiting on you (approve and I'll do it)"] + ([f"- {x}" for x in waiting] or ["- Nothing."]) + [""]
    L += ["## 🔵 FYI"] + ([f"- {x}" for x in fyi] or ["- Nothing."]) + [""]
    L += ["## Vital signs",
          f"- Uptime: {'up' if h['uptime']['up'] else 'DOWN'}, homepage {h['uptime']['response_ms']} ms, REST API {h['rest_api']['response_ms']} ms",
          f"- SSL: " + (f"expires {h['ssl']['expires']} ({h['ssl']['days_left']} days)" if h['ssl'].get('expires') else h['ssl'].get('note', h['ssl'].get('error', 'n/a'))),
          f"- WordPress {h['core']['installed']} (latest {h['core']['latest']}); {len(pu)} plugin update(s)",
          f"- Site Health: " + ", ".join(f"{k} {x['status']}" for k, x in h["site_health"].items()),
          f"- Content: {c['published_posts']} published, {len(c['drafts'])} drafts, {len(c['missed_schedule'])} missed schedule; {c.get('internal_links_checked', 0)} internal links checked",
          f"- Users: {u['total_users']} total, roles {u['roles']}, {len(u['new_users'])} new in {u['new_last_days']} days, admins: {', '.join(u['administrators'])}"]
    if "woocommerce" in u:
        w = u["woocommerce"]
        L.append(f"- WooCommerce: {w['products']} products, orders {w['orders_by_status'] or 'none yet'}, {len(w['failed_orders'])} failed")
        L.append(f"- Subscriptions: {w['subscriptions'] if isinstance(w['subscriptions'], str) else w['subscriptions']['by_status']}")
    if pm and not pm.get("error"):
        L.append(f"- Memberships (PMPro): {pm['active_members']} active {pm['active_by_level']}, {len(pm['expiring_soon'])} expiring ≤14 days, {len(pm['expired_or_lapsed'])} lapsed, {len(pm['failed_payments'])} failed payment(s)")
    for s in hr["sources"]:
        L.append(f"- Help requests ({s['plugin']}): " + (s['entries'] if isinstance(s['entries'], str) else f"{len(s['entries'])} entries"))
    L += ["", "## Trend vs " + (prev_day or "previous run")] + ([f"- {t}" for t in trend] or ["- " + ("No changes." if prev_day else "First run: baseline saved; trends start tomorrow.")])
    L += ["", f"_Connected as `{v.get('user')}` ({', '.join(v.get('roles') or [])}). Read-only run; no changes were made._"]
    return "\n".join(L)

if __name__ == "__main__":
    if not (URL and USER and PW): die("Set WP_URL, WP_USER, WP_APP_PASSWORD")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "state": print(json.dumps({"path": state_path(), **load_state()}, indent=2)); sys.exit(0)
    fn = {"verify": verify, "detect": detect, "health": health, "content": content, "users": users, "help": help_requests, "digest": digest}.get(cmd)
    if not fn: die("unknown command " + cmd)
    out = fn()
    print(out if isinstance(out, str) else json.dumps(out, indent=2, default=str))
