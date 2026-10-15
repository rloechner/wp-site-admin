#!/usr/bin/env python3
"""WP Site Admin updater. Run as: python3 scripts/wp-update.py <command> ...

Read-only:
  list                      pending core/plugin/theme updates (bridge, else WP-CLI, else wordpress.org comparison)
  backup-check              detect backup plugins / host backup hints
  verify                    post-update checks: homepage 200, wp-admin/login loads, REST ok, no fatal-error text
Writes (owner must have approved THIS item; refuses without --yes):
  plugin <plugin-file-or-slug> --yes   update ONE plugin, then verify
  theme <slug> --yes                   update ONE theme, then verify
  core --yes                           update WordPress core, then verify
Path selection (--via auto|cli|bridge; auto = cli if available, else bridge):
  cli    WP-CLI. Over SSH when WP_SSH=user@host (and WP_PATH=/path/to/wordpress); locally when only WP_PATH is set.
  bridge companion/wpsa-rest-bridge.php endpoints (/wp-json/wpsa/v1/...).
  Neither available -> prints the wp-admin browser fallback.
Env: WP_URL, WP_USER, WP_APP_PASSWORD (+ optional WP_SSH, WP_PATH). Never prints credentials.
"""
import json, os, re, shlex, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wpsa

BACKUP_PLUGINS = {"updraftplus": "UpdraftPlus", "jetpack": "Jetpack (Backup/VaultPress)", "backwpup": "BackWPup", "duplicator": "Duplicator",
    "all-in-one-wp-migration": "All-in-One WP Migration", "wpvivid-backuprestore": "WPvivid", "blogvault-real-time-backup": "BlogVault",
    "backupbuddy": "BackupBuddy (Solid Backups)", "solid-backups": "Solid Backups", "vaultpress": "VaultPress", "wp-time-capsule": "WP Time Capsule",
    "backup-backup": "Backup Migration", "ithemes-security-pro": "iThemes/Solid Security"}
FALLBACK = """Browser fallback (no WP-CLI, no bridge): log into {url}/wp-admin as the bot admin, open Dashboard → Updates,
tick ONLY the approved item, click "Update Plugins" / "Update Themes" / "Update to version X", wait for "All updates have been completed",
then run: python3 scripts/wp-update.py verify"""

def out(x): print(json.dumps(x, indent=2, default=str))

def cli_available():
    return bool(os.environ.get("WP_SSH") or os.environ.get("WP_PATH"))

def run_wp(args):
    path = os.environ.get("WP_PATH")
    cmd = ["wp"] + ([f"--path={path}"] if path else []) + args
    if os.environ.get("WP_SSH"):
        cmd = ["ssh", "-o", "BatchMode=yes", os.environ["WP_SSH"], " ".join(shlex.quote(c) for c in cmd)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def bridge_available():
    r = wpsa.req("/wp-json/wpsa/v1/updates")
    return r["code"] not in (404, None), r

def list_updates(via):
    if via in ("auto", "cli") and cli_available():
        res = {"via": "wp-cli"}
        for kind in ("plugin", "theme"):
            rc, so, se = run_wp([kind, "list", "--update=available", "--fields=name,version,update_version,status", "--format=json"])
            res[kind + "s"] = json.loads(so or "[]") if rc == 0 else f"error: {se[:300]}"
        rc, so, se = run_wp(["core", "check-update", "--format=json"])
        res["core"] = (json.loads(so) if so.startswith("[") else []) if rc == 0 else f"error: {se[:300]}"
        return res
    if via in ("auto", "bridge"):
        ok, r = bridge_available()
        if ok and r["ok"]: return {"via": "bridge", **r["data"]}
    h = wpsa.health()
    return {"via": "read-only comparison (no write path available)", "core": h["core"],
            "plugins": [p for p in h["plugins"] if p["update"]], "themes": [t for t in h["themes"] if t["update"]],
            "how_to_update": FALLBACK.format(url=wpsa.URL)}

def backup_check():
    plugins = wpsa.get("/wp-json/wp/v2/plugins") or []
    found = [{"plugin": BACKUP_PLUGINS[s], "status": p["status"]} for p in plugins for s in [p["plugin"].split("/")[0]] if s in BACKUP_PLUGINS]
    active = [f for f in found if f["status"] == "active"]
    return {"backup_plugins": found, "has_active_backup_plugin": bool(active),
            "advice": "Run a fresh backup before updating (e.g. UpdraftPlus → Backup Now)." if active else
                      "No active backup plugin found. Ask the owner to take a host snapshot (most managed hosts have one-click backups) or install UpdraftPlus (Plugins → Add New Plugin → UpdraftPlus) and run Backup Now before updating."}

FATAL = re.compile(r"There has been a critical error|Fatal error|Parse error|Error establishing a database connection|Briefly unavailable for scheduled maintenance", re.I)
def verify():
    checks = {}
    home = wpsa.req("/", auth=False, raw=True)
    checks["homepage"] = {"code": home["code"], "ms": home["ms"], "fatal_text": bool(FATAL.search(home.get("text") or ""))}
    login = wpsa.req("/wp-login.php", auth=False, raw=True)
    checks["wp_login"] = {"code": login["code"], "fatal_text": bool(FATAL.search(login.get("text") or ""))}
    admin = wpsa.req("/wp-admin/", raw=True)  # authenticated; app passwords don't create a cookie session, so a 302 to login is normal
    checks["wp_admin"] = {"code": admin["code"], "fatal_text": bool(FATAL.search(admin.get("text") or ""))}
    api = wpsa.req("/wp-json/wp/v2/users/me")
    checks["rest_api_auth"] = {"code": api["code"]}
    sh = wpsa.req("/wp-json/wp-site-health/v1/tests/background-updates")
    checks["site_health_background_updates"] = (sh.get("data") or {}).get("status") if sh["ok"] else f"HTTP {sh['code']}"
    ok = (home["code"] == 200 and not checks["homepage"]["fatal_text"] and login["code"] == 200 and not checks["wp_login"]["fatal_text"]
          and admin["code"] in (200, 302) and not checks["wp_admin"]["fatal_text"] and api["code"] == 200)
    return {"site_ok": ok, "checks": checks}

ROLLBACK = ("Rollback: (1) If the site shows a critical error, deactivate the plugin by renaming its folder "
            "wp-content/plugins/{slug} → {slug}.off via SFTP/host file manager (or `wp plugin deactivate {slug}`). "
            "(2) Reinstall the previous version: `wp plugin install {slug} --version={before} --force`, or download it from "
            "https://wordpress.org/plugins/{slug}/advanced/ (Previous versions) and upload via Plugins → Add New Plugin → Upload Plugin "
            "(choose 'Replace current with uploaded'). (3) Or restore the backup taken before the update.")

def resolve_plugin_file(x):
    if "/" in x or x.endswith(".php"): return x
    for p in wpsa.get("/wp-json/wp/v2/plugins") or []:
        if p["plugin"].split("/")[0] == x: return p["plugin"] + ".php" if not p["plugin"].endswith(".php") else p["plugin"]
    return x

def do_update(kind, target, via):
    res = {"kind": kind, "target": target}
    use_cli = via == "cli" or (via == "auto" and cli_available())
    if use_cli:
        if not cli_available(): return {"error": "WP-CLI path needs WP_SSH and/or WP_PATH"}
        slug = target.split("/")[0] if target else None
        if kind == "plugin":
            _, before, _ = run_wp(["plugin", "get", slug, "--field=version"])
            rc, so, se = run_wp(["plugin", "update", slug])
            _, after, _ = run_wp(["plugin", "get", slug, "--field=version"])
        elif kind == "theme":
            _, before, _ = run_wp(["theme", "get", slug, "--field=version"])
            rc, so, se = run_wp(["theme", "update", slug])
            _, after, _ = run_wp(["theme", "get", slug, "--field=version"])
        else:
            _, before, _ = run_wp(["core", "version"])
            rc, so, se = run_wp(["core", "update"])
            if rc == 0: run_wp(["core", "update-db"])
            _, after, _ = run_wp(["core", "version"])
        res.update(via="wp-cli" + (" over ssh" if os.environ.get("WP_SSH") else " (local)"), before=before, after=after, ok=rc == 0 and before != after, output=(so + "\n" + se)[-800:])
    else:
        ok, _ = bridge_available()
        if not ok: return {"error": "No write path available.", "how_to_update": FALLBACK.format(url=wpsa.URL)}
        path, body = {"plugin": ("/wp-json/wpsa/v1/update/plugin", {"plugin": resolve_plugin_file(target)}),
                      "theme": ("/wp-json/wpsa/v1/update/theme", {"theme": target}), "core": ("/wp-json/wpsa/v1/update/core", {})}[kind]
        r = post(path, body)
        res.update(via="bridge", http=r["code"], **(r.get("data") if isinstance(r.get("data"), dict) else {"raw": r.get("text")}))
    res["verify"] = verify()
    if not res["verify"]["site_ok"] or not res.get("ok"):
        slug = (target or "").split("/")[0]
        res["rollback"] = ROLLBACK.format(slug=slug, before=res.get("before")) if kind == "plugin" else "Restore the pre-update backup; for themes, reinstall the previous version from wordpress.org/themes/<slug>."
    return res

def post(path, body):
    import base64, urllib.request, urllib.error, time
    r = urllib.request.Request(wpsa.URL + path, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Basic " + base64.b64encode(f"{wpsa.USER}:{wpsa.PW}".encode()).decode()})
    try:
        with urllib.request.urlopen(r, timeout=600) as resp: code, b = resp.status, resp.read()
    except urllib.error.HTTPError as e: code, b = e.code, e.read()
    try: return {"code": code, "data": json.loads(b)}
    except Exception: return {"code": code, "text": b.decode("utf-8", "replace")[-800:]}

if __name__ == "__main__":
    a = sys.argv[1:]
    via = "auto"
    if "--via" in a: i = a.index("--via"); via = a[i + 1]; del a[i:i + 2]
    yes = "--yes" in a; a = [x for x in a if x != "--yes"]
    if not (wpsa.URL and wpsa.USER and wpsa.PW): wpsa.die("Set WP_URL, WP_USER, WP_APP_PASSWORD")
    cmd = a[0] if a else "list"
    if cmd == "list": out(list_updates(via))
    elif cmd == "backup-check": out(backup_check())
    elif cmd == "verify": out(verify())
    elif cmd in ("plugin", "theme", "core"):
        if not yes: wpsa.die("Refusing to write without --yes. Get the owner's explicit approval for this exact update first.")
        if cmd != "core" and len(a) < 2: wpsa.die(f"usage: wp-update.py {cmd} <name> --yes")
        out(do_update(cmd, a[1] if len(a) > 1 else None, via))
    else: wpsa.die("unknown command " + cmd)
