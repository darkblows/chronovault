#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChronoVault - Wayback Site Archiver
===================================

Archive a whole website on the Internet Archive's Wayback Machine, from a
friendly desktop app. Pure Python standard library: no pip install needed.

  * finds your pages (sitemaps, optional crawler, or your own list)
  * submits them through the official Save Page Now 2 API, politely
  * respects the account's concurrent-capture limit and backs off on 429/503
  * keeps a registry (results.jsonl): stop any time, resume later
  * final check: local comparison + verification against the public index

Requirements: Python 3.8+ with tkinter, and a free archive.org account
(S3-style keys from https://archive.org/account/s3.php).

Run:  python3 chronovault.py
"""
from __future__ import annotations

import csv
import gzip
import html
import http.client
import json
import os
import queue
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib import robotparser

try:
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import filedialog, messagebox, ttk
except ImportError:  # pragma: no cover
    sys.stderr.write(
        "\nChronoVault needs tkinter, which is not installed.\n\n"
        "  Debian / Ubuntu / Kubuntu / Mint :  sudo apt install python3-tk\n"
        "  Fedora                           :  sudo dnf install python3-tkinter\n"
        "  Arch / Manjaro                   :  sudo pacman -S tk\n"
        "  macOS (Homebrew)                 :  brew install python-tk\n"
        "  Windows                          :  re-run the Python installer and enable 'tcl/tk'\n\n"
    )
    sys.exit(1)

APP_NAME = "ChronoVault"
APP_SUBTITLE = "Wayback Site Archiver"
VERSION = "1.0.0"

API_BASE = os.environ.get("CHRONOVAULT_API_BASE", "https://web.archive.org").rstrip("/")
CDX_URL = os.environ.get("CHRONOVAULT_CDX_URL", "https://web.archive.org/cdx/search/cdx")
S3_KEYS_URL = "https://archive.org/account/s3.php"
FAST = os.environ.get("CHRONOVAULT_FAST") == "1"          # test mode: short waits
UA = "%s/%s (Wayback site archiver; +python-urllib)" % (APP_NAME, VERSION)

# 64x64 PNG icon, 40 colours (~1.2 KB)
ICON_B64 = "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAMAAACdt4HsAAAAn1BMVEUZJ1OVczldTDOziDwKD2k62JViVUtD658XGTMMESMgZVKui0jRmz7ao0EMECMgL1uQc0guoHQMESUhLls0vYYAVVWszWoOFSobJ0z2tkQgLVcjMFwCCycAAAA82pYWITr/wUXmq0MHBhpuWDXNm0JHPC8pKC86My8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB55GypAAAAKHRSTlPv////EP///xXR/////0xM//+Rkf8D//7+//7+/wD/////////////k74NQAAAA4JJREFUeNqll4mWoyAQRVGjiWvWaSJqXCD6/384xaKigtPJ1DnZDO/6qigUUcXjAK/zHRW/DHQ/K1FVIf72B+QI4tcAiLOQScCpOnygnhgHEArAqToXiJDPAISg4swJCFI58N+fR1GAtAIjB/KVHggExABAX+qBAP4RFIB8HVAGdEB7I54Qe/+D/LynffKCP/coZ3SXI5fB5UVwiVkLweJLUKiDm4F3hIhRHsRtrkUbB0YCQei5OcrlLN9EGjxNY9EW+izi3Bgs2BK2APIMRvNNA95b+NWMCIOJrYPL5NmhQ49xP7jOmFFz+beDizqd5+ISglL+jl1PEeJ9AEFKn7qggijTVH6Wb9YoD8QOIChQp8dCBkLPG79hR3oIlhO/dFCI+jWOEoEMUpi/T5W0AuT8afp3nr/XBGYFyAQab1Lg0s1zV/vpNDIJmwMxWymeY+kAIhEjiBmgKqidcQMoB1kFZAaICnjlngOZBDM7IO3agAHwFhYKZADIDPQKGACqCoERwJtQawEzQOYQGwG8BA1dAZJkBXBXrYBWkzishv/8uMsUenGBIlsAkjXsy1IT1A/ff9QaEP5Ml1VcAVpMWdJP46Pj63WMZqLj0ZKtALUK3FsAr9idTDFYJxKAR90asErBP/pHaK5BOyhSGGbAPNpUxDqKKJ95Z5iKKM+Dx8pMgBrHm0aUZasdjSxbkc0DNIChkcYl5M0AKhppMqAD3BVbt+G+p2uc8GkAqOw2OYyIxXoeDClAbJfzFiSXMzYDRA7r1bfUi0ZuqAUgJ5LtGRAVaHsbQFTYOBF4noIWSmgDSAs5tRBKt2ndYXVwCZA1thBA7+Guw+JlAcg2gc6dbm0OmyaSNl7XRVffv0YaApmmKW8StXygakree02Lu+h49F/+8WoFYOyp27vz5t1TUkesh4GvB7cTy/vFrxGdFYClB9iVJI7bc0j/pp7YpAzdVQH8xw5gvAmLnU3KWNqqLU6Lse+/VNSdFYDHvcQmfguAGaDpBgEtgOcU/LmIITYjErFJm5JJaF1iQxFDdLN0He6pk4gF3iawXZONARYgCT6N43lvKLM2Pu+EHkJ9FefrogcAtEbK0CHcXf+LizT30MEFfG6jEB44MvxZdJ2GzPhTW4i/jlA+9n0POKkHz//QywfP7Dt9Vo0OqtMXdQhP46OviOxDRJgp4QgAxO3XjPCWTbK/MOF8T6KBTmMAAAAASUVORK5CYII="

# ---------------------------------------------------------------------------
# Palette "Midnight Archive"
# ---------------------------------------------------------------------------
C = dict(
    bg="#0B1020", surface="#121A30", surface2="#192342", trough="#0E1529",
    border="#27345A", text="#E8ECF6", muted="#8C99BA", accent="#F5B544",
    accent_hi="#FFC96B", accent_fg="#1B1403", ok="#3DDC97", warn="#FFB84D",
    err="#FF6B81", info="#6AA9FF", sel="#25335E",
)

# ---------------------------------------------------------------------------
# Translations
# ---------------------------------------------------------------------------
TEXTS = {
    "it": {
        "subtitle": "Archivia interi siti sulla Wayback Machine",
        "sec_site": "SITO WEB", "lbl_site": "Indirizzo del sito",
        "chk_crawl": "Cerca anche con il crawler (più lento)",
        "chk_filters": "Escludi pagine tecniche (feed, wp-json…)",
        "btn_find": "Trova pagine", "btn_file": "Carica da file…",
        "lbl_found": "{n} pagine nella lista", "lbl_none": "Nessuna lista caricata",
        "sec_account": "ACCOUNT INTERNET ARCHIVE", "lbl_access": "Access key", "lbl_secret": "Secret key",
        "chk_show": "Mostra chiavi", "chk_remember": "Ricorda le chiavi su questo PC",
        "lnk_keys": "Dove trovo le chiavi? →", "btn_check": "Verifica chiavi",
        "keys_ok": "✔ Chiavi valide · slot liberi: {avail} · catture oggi: {used}/{limit}",
        "keys_bad": "✖ Chiavi rifiutate da archive.org", "keys_net": "✖ archive.org non raggiungibile: {err}",
        "keys_missing": "Inserisci access key e secret key", "keys_wait": "Controllo…",
        "sec_params": "PARAMETRI", "lbl_interval": "Secondi tra un invio e l'altro",
        "lbl_conc": "Catture simultanee (max)", "tip_conc": "Si riduce da sola se archive.org risponde «sessioni piene».",
        "chk_retry": "Ritenta anche gli errori permanenti",
        "sec_work": "CARTELLA DI LAVORO", "btn_change": "Cambia…",
        "btn_start": "▶  Avvia", "btn_pause": "Pausa", "btn_resume": "Riprendi", "btn_stop": "Ferma",
        "btn_verify": "✔  Verifica finale", "btn_export": "⬇  Esporta CSV",
        "st_ready": "Pronto", "st_running": "In esecuzione", "st_paused": "In pausa",
        "st_cooldown": "Pausa anti-blocco {t}", "st_done": "Completato", "st_stopped": "Fermato",
        "st_stopping": "Salvo i lavori in corso…", "st_error": "Errore", "st_busy": "Ricerca pagine…",
        "stat_saved": "salvate", "stat_speed": "VELOCITÀ", "stat_eta": "FINE STIMATA", "stat_slots": "SLOT IN USO",
        "stat_left": "DA FARE", "per_hour": "{n}/ora",
        "tab_log": "Registro attività", "tab_pages": "Pagine", "tab_verify": "Verifica finale",
        "flt_all": "Tutte", "flt_saved": "Salvate", "flt_pending": "Da fare", "flt_failed": "Con errori",
        "lbl_search": "Cerca:", "col_url": "URL", "col_status": "Stato", "col_detail": "Dettaglio", "col_time": "Quando",
        "s_saved": "Salvata", "s_pending": "In attesa", "s_perm": "Non archiviabile", "s_retry": "Da ritentare",
        "s_inflight": "In corso",
        "v_total": "TOTALE", "v_saved": "SALVATE", "v_perm": "NON ARCHIVIABILI", "v_missing": "MANCANTI",
        "v_online": "CONFERMATE ONLINE", "v_offline": "NON TROVATE ONLINE",
        "btn_vlocal": "Confronto locale", "btn_vonline": "Verifica sulla Wayback Machine",
        "btn_requeue": "Rimetti in coda le non trovate",
        "v_note": "L'indice pubblico può impiegare alcune ore ad aggiornarsi: una pagina «non trovata» subito dopo il "
                  "salvataggio non è per forza un errore.",
        "r_pending": "Mai archiviata", "r_retry": "Errore temporaneo: {code}", "r_perm": "Errore permanente: {code}",
        "r_offline": "Non presente nell'indice online",
        "msg_site": "Inserisci l'indirizzo del sito (es. esempio.org).",
        "msg_keys": "Inserisci access key e secret key di archive.org.",
        "msg_nolist": "Nessuna pagina trovata. Prova ad attivare il crawler o carica un file con gli URL.",
        "msg_exit": "L'archiviazione è in corso. Fermarla e uscire?",
        "msg_done": "Archiviazione completata!", "msg_done_body": "Salvate {saved} pagine su {total}.\nControlla la scheda «Verifica finale».",
        "msg_auth": "archive.org ha rifiutato le chiavi. Controllale e riprova.",
        "msg_gaveup": "Troppi errori consecutivi: mi fermo. Riprova più tardi, il registro è salvato.",
        "msg_exported": "Report salvato in:\n{path}", "msg_pickdir": "Scegli la cartella di lavoro",
        "msg_pickfile": "Scegli un file con un URL per riga", "msg_lang": "Lingua cambiata.",
        "log_ready": "{app} {ver} pronto.",
        "log_sitemap_try": "Cerco le sitemap…", "log_sitemap_found": "Sitemap: trovati {n} URL.",
        "log_crawl_start": "Avvio il crawler (rispetta robots.txt)…", "log_crawl_prog": "Crawler: {n} pagine visitate…",
        "log_crawl_done": "Crawler: trovate {n} pagine.", "log_list_ready": "Lista pronta: {n} URL in {path}",
        "log_discover_fail": "Ricerca pagine fallita: {err}", "log_file_loaded": "Caricati {n} URL da {path}",
        "log_workspace": "Cartella di lavoro: {path} ({saved} già salvate nel registro)",
        "log_start": "Avvio: {pending} pagine da archiviare · slot {cap} · pausa {interval}s",
        "log_saved": "✔ {url}", "log_perm": "✖ {url} — {code}", "log_retry": "↻ {url} — {code} (tentativo {n})",
        "log_giveup_url": "⚠ {url} — {code}: rinuncio per ora, resta da fare.",
        "log_cooldown": "Archive.org sta rallentando: pausa di {secs}s (blocco n.{n}).",
        "log_cap": "Slot simultanei ridotti a {n}.", "log_slots": "L'account consente {n} catture simultanee.",
        "log_auth_bad": "Chiavi rifiutate (HTTP {code}).", "log_acct_net": "Stato account non verificabile: {err}",
        "log_poll_fail": "Controllo stato fallito: {err}", "log_submit_fail": "Invio fallito ({code}): {url}",
        "log_done": "Finito: tutte le pagine della lista sono state elaborate.",
        "log_stopped": "Fermato. Il registro è salvato: puoi riprendere quando vuoi.",
        "log_stopping": "Attendo i lavori in corso (max {s}s)…", "log_crash": "Errore interno: {err}",
        "log_gaveup": "Troppi errori consecutivi: interrompo.", "log_exported": "Esportato: {path}",
        "log_cdx_start": "Interrogo l'indice pubblico della Wayback Machine…",
        "log_cdx_ok": "Indice online: {ok}/{total} pagine confermate.", "log_cdx_fail": "Verifica online fallita: {err}",
        "log_requeued": "Rimesse in coda {n} pagine.", "log_hint_crawl": "Nessuna sitemap utile: passo al crawler.",
        "log_lang": "Lingua: Italiano",
    },
    "en": {
        "subtitle": "Archive whole websites on the Wayback Machine",
        "sec_site": "WEBSITE", "lbl_site": "Site address",
        "chk_crawl": "Also use the crawler (slower)",
        "chk_filters": "Skip technical pages (feeds, wp-json…)",
        "btn_find": "Find pages", "btn_file": "Load from file…",
        "lbl_found": "{n} pages in the list", "lbl_none": "No list loaded",
        "sec_account": "INTERNET ARCHIVE ACCOUNT", "lbl_access": "Access key", "lbl_secret": "Secret key",
        "chk_show": "Show keys", "chk_remember": "Remember keys on this computer",
        "lnk_keys": "Where do I find my keys? →", "btn_check": "Check keys",
        "keys_ok": "✔ Valid keys · free slots: {avail} · captures today: {used}/{limit}",
        "keys_bad": "✖ Keys rejected by archive.org", "keys_net": "✖ archive.org unreachable: {err}",
        "keys_missing": "Enter access key and secret key", "keys_wait": "Checking…",
        "sec_params": "SETTINGS", "lbl_interval": "Seconds between submissions",
        "lbl_conc": "Simultaneous captures (max)", "tip_conc": "Lowers itself if archive.org answers “sessions full”.",
        "chk_retry": "Retry permanent errors too",
        "sec_work": "WORKING FOLDER", "btn_change": "Change…",
        "btn_start": "▶  Start", "btn_pause": "Pause", "btn_resume": "Resume", "btn_stop": "Stop",
        "btn_verify": "✔  Final check", "btn_export": "⬇  Export CSV",
        "st_ready": "Ready", "st_running": "Running", "st_paused": "Paused",
        "st_cooldown": "Cool-down {t}", "st_done": "Completed", "st_stopped": "Stopped",
        "st_stopping": "Saving in-flight jobs…", "st_error": "Error", "st_busy": "Finding pages…",
        "stat_saved": "saved", "stat_speed": "SPEED", "stat_eta": "ESTIMATED END", "stat_slots": "SLOTS IN USE",
        "stat_left": "TO DO", "per_hour": "{n}/hour",
        "tab_log": "Activity log", "tab_pages": "Pages", "tab_verify": "Final check",
        "flt_all": "All", "flt_saved": "Saved", "flt_pending": "To do", "flt_failed": "With errors",
        "lbl_search": "Search:", "col_url": "URL", "col_status": "Status", "col_detail": "Detail", "col_time": "When",
        "s_saved": "Saved", "s_pending": "Waiting", "s_perm": "Not archivable", "s_retry": "To retry",
        "s_inflight": "In progress",
        "v_total": "TOTAL", "v_saved": "SAVED", "v_perm": "NOT ARCHIVABLE", "v_missing": "MISSING",
        "v_online": "CONFIRMED ONLINE", "v_offline": "NOT FOUND ONLINE",
        "btn_vlocal": "Local comparison", "btn_vonline": "Verify on the Wayback Machine",
        "btn_requeue": "Re-queue the ones not found",
        "v_note": "The public index can take a few hours to catch up: a page “not found” right after saving is not "
                  "necessarily an error.",
        "r_pending": "Never archived", "r_retry": "Temporary error: {code}", "r_perm": "Permanent error: {code}",
        "r_offline": "Not present in the online index",
        "msg_site": "Enter the site address (e.g. example.org).",
        "msg_keys": "Enter your archive.org access key and secret key.",
        "msg_nolist": "No pages found. Try enabling the crawler or load a file with URLs.",
        "msg_exit": "Archiving is in progress. Stop it and quit?",
        "msg_done": "Archiving completed!", "msg_done_body": "Saved {saved} of {total} pages.\nSee the “Final check” tab.",
        "msg_auth": "archive.org rejected the keys. Check them and try again.",
        "msg_gaveup": "Too many consecutive errors: stopping. Try again later, the registry is saved.",
        "msg_exported": "Report saved to:\n{path}", "msg_pickdir": "Choose the working folder",
        "msg_pickfile": "Choose a file with one URL per line", "msg_lang": "Language changed.",
        "log_ready": "{app} {ver} ready.",
        "log_sitemap_try": "Looking for sitemaps…", "log_sitemap_found": "Sitemaps: found {n} URLs.",
        "log_crawl_start": "Starting the crawler (honours robots.txt)…", "log_crawl_prog": "Crawler: {n} pages visited…",
        "log_crawl_done": "Crawler: found {n} pages.", "log_list_ready": "List ready: {n} URLs in {path}",
        "log_discover_fail": "Page discovery failed: {err}", "log_file_loaded": "Loaded {n} URLs from {path}",
        "log_workspace": "Working folder: {path} ({saved} already saved in the registry)",
        "log_start": "Start: {pending} pages to archive · slots {cap} · delay {interval}s",
        "log_saved": "✔ {url}", "log_perm": "✖ {url} — {code}", "log_retry": "↻ {url} — {code} (attempt {n})",
        "log_giveup_url": "⚠ {url} — {code}: giving up for now, still to do.",
        "log_cooldown": "Archive.org is slowing us down: pausing {secs}s (block #{n}).",
        "log_cap": "Simultaneous slots lowered to {n}.", "log_slots": "The account allows {n} simultaneous captures.",
        "log_auth_bad": "Keys rejected (HTTP {code}).", "log_acct_net": "Could not check account status: {err}",
        "log_poll_fail": "Status check failed: {err}", "log_submit_fail": "Submission failed ({code}): {url}",
        "log_done": "Finished: every page in the list has been processed.",
        "log_stopped": "Stopped. The registry is saved: resume whenever you like.",
        "log_stopping": "Waiting for in-flight jobs (max {s}s)…", "log_crash": "Internal error: {err}",
        "log_gaveup": "Too many consecutive errors: stopping.", "log_exported": "Exported: {path}",
        "log_cdx_start": "Querying the public Wayback Machine index…",
        "log_cdx_ok": "Online index: {ok}/{total} pages confirmed.", "log_cdx_fail": "Online check failed: {err}",
        "log_requeued": "Re-queued {n} pages.", "log_hint_crawl": "No usable sitemap: switching to the crawler.",
        "log_lang": "Language: English",
    },
}

# ---------------------------------------------------------------------------
# Archive.org error classes (same classification as the official tooling)
# ---------------------------------------------------------------------------
PERM_ERRORS = {
    "error:bad-request", "error:blocked", "error:blocked-url", "error:filesize-limit",
    "error:ftp-access-denied", "error:http-version-not-supported", "error:invalid-host-resolution",
    "error:invalid-url-syntax", "error:method-not-allowed", "error:network-authentication-required",
    "error:no-access", "error:not-found", "error:not-implemented", "error:too-many-daily-captures",
    "error:too-many-redirects", "error:unauthorized",
}
BAN_ERRORS = {"error:blocked-client-ip"}

NORMAL_TIMING = dict(poll=4.0, tick=0.25, cd_base=30.0, cd_max=1800.0, drain=30.0, job_timeout=3600.0,
                     retry_wait=60.0, ban_wait=3600.0)
FAST_TIMING = dict(poll=0.3, tick=0.05, cd_base=1.0, cd_max=3.0, drain=4.0, job_timeout=60.0,
                   retry_wait=0.5, ban_wait=3.0)
MAX_ATTEMPTS = 5
GIVE_UP_AFTER = 15      # consecutive cool-downs before stopping the run

EXCLUDE_RE = re.compile(r"/wp-json/|xmlrpc\.php|/wp-admin/|wp-login\.php|\?replytocom=|/feed/?$", re.I)
SKIP_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".zip", ".gz", ".rar", ".7z",
            ".mp3", ".mp4", ".avi", ".mov", ".css", ".js", ".json", ".xml", ".woff", ".woff2", ".ttf", ".exe"}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def now_iso():
    return datetime.now(timezone.utc).isoformat()


def fmt_eta(sec):
    if sec is None:
        return "—"
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m = rem // 60
    if h:
        return "%d h %02d min" % (h, m)
    if m:
        return "%d min" % m
    return "< 1 min"


def fmt_cd(sec):
    m, s = divmod(int(sec), 60)
    return "%d:%02d" % (m, s)


def local_when(iso):
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d/%m %H:%M")
    except Exception:
        return ""


def host_base(netloc):
    h = netloc.lower().split(":")[0]
    return h[4:] if h.startswith("www.") else h


def parse_site(text):
    """'example.org' / 'https://www.example.org/x' -> ('https://www.example.org/', 'example.org')."""
    t = (text or "").strip()
    if not t:
        return None
    if not re.match(r"^[a-z][a-z0-9+.\-]*://", t, re.I):
        t = "https://" + t
    p = urllib.parse.urlsplit(t)
    if not p.netloc:
        return None
    return "%s://%s/" % (p.scheme, p.netloc), host_base(p.netloc)


def norm_url(u):
    p = urllib.parse.urlsplit(u.strip())
    host = host_base(p.netloc)
    path = (p.path or "/").rstrip("/") or "/"
    return host + path + (("?" + p.query) if p.query else "")


def clean_urls(urls, base, filters):
    seen, out = set(), []
    for u in urls:
        u = u.strip().split("#")[0]
        if not re.match(r"^https?://", u, re.I):
            continue
        p = urllib.parse.urlsplit(u)
        if base and host_base(p.netloc) != base:
            continue
        if filters and EXCLUDE_RE.search(u):
            continue
        if u not in seen:
            seen.add(u)
            out.append(u)
    return sorted(out)


def config_dir():
    env = os.environ.get("CHRONOVAULT_CONFIG")
    if env:
        return Path(env)
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / APP_NAME.lower()


def load_config():
    try:
        with open(config_dir() / "config.json", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_config(cfg):
    try:
        d = config_dir()
        d.mkdir(parents=True, exist_ok=True)
        p = d / "config.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass
    except Exception:
        pass


def detect_lang():
    raw = os.environ.get("LC_ALL") or os.environ.get("LANG") or ""
    if not raw:
        try:
            import locale
            raw = locale.getlocale()[0] or ""
        except Exception:
            raw = ""
    return "it" if raw.lower().startswith("it") else "en"


# ---------------------------------------------------------------------------
# HTTP helpers for discovery and verification
# ---------------------------------------------------------------------------
def http_get(url, timeout=30, max_bytes=30_000_000, raise_errors=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(max_bytes)
        return data
    except Exception:
        if raise_errors:
            raise
        return None


LOC_RE = re.compile(r"<loc>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</loc>", re.I | re.S)


def parse_sitemap(url, seen, cancel, depth=0):
    if depth > 6 or url in seen or cancel():
        return []
    seen.add(url)
    data = http_get(url)
    if not data:
        return []
    if data[:2] == b"\x1f\x8b":
        try:
            data = gzip.decompress(data)
        except Exception:
            return []
    out = []
    for m in LOC_RE.finditer(data.decode("utf-8", "replace")):
        loc = html.unescape(m.group(1).strip())
        if re.search(r"\.xml(\.gz)?(\?.*)?$", loc, re.I):
            out.extend(parse_sitemap(loc, seen, cancel, depth + 1))
        else:
            out.append(loc)
    return out


def discover_sitemaps(root, cancel):
    candidates = [root + n for n in ("sitemap.xml", "sitemap_index.xml", "wp-sitemap.xml", "sitemap-index.xml")]
    robots = http_get(root + "robots.txt")
    if robots:
        for line in robots.decode("utf-8", "replace").splitlines():
            if line.lower().startswith("sitemap:"):
                candidates.append(line.split(":", 1)[1].strip())
    seen, urls = set(), []
    for c in candidates:
        urls.extend(parse_sitemap(c, seen, cancel))
    return urls


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.links.append(v)


def crawl(root, base, cancel, progress, max_pages=20000, delay=0.25):
    """Polite breadth-first crawler: same site only, honours robots.txt."""
    rp = robotparser.RobotFileParser()
    txt = http_get(root + "robots.txt")
    rp.parse(txt.decode("utf-8", "replace").splitlines() if txt else [])
    seen, todo, found = {root}, deque([root]), []
    while todo and len(found) < max_pages and not cancel():
        u = todo.popleft()
        if not rp.can_fetch(UA, u):
            continue
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                if "html" not in r.headers.get("Content-Type", "").lower():
                    continue
                final = r.geturl()
                body = r.read(2_000_000)
        except Exception:
            continue
        found.append(u)
        if len(found) % 50 == 0:
            progress(len(found))
        parser = _LinkParser()
        try:
            parser.feed(body.decode("utf-8", "replace"))
        except Exception:
            pass
        for href in parser.links:
            absu = urllib.parse.urljoin(final, href).split("#")[0]
            p = urllib.parse.urlsplit(absu)
            if p.scheme not in ("http", "https") or host_base(p.netloc) != base:
                continue
            if os.path.splitext(p.path)[1].lower() in SKIP_EXT:
                continue
            if absu not in seen:
                seen.add(absu)
                todo.append(absu)
        time.sleep(0 if FAST else delay)
    return found


def cdx_fetch(base):
    """All URLs the Wayback Machine knows for a domain (one request)."""
    q = urllib.parse.urlencode({"url": base, "matchType": "domain", "fl": "original", "collapse": "urlkey"})
    data = http_get("%s?%s" % (CDX_URL, q), timeout=180, max_bytes=300_000_000, raise_errors=True)
    return {norm_url(line) for line in data.decode("utf-8", "replace").splitlines() if line.strip()}


# ---------------------------------------------------------------------------
# Registry: results.jsonl (append-only, same format as the shell script)
# ---------------------------------------------------------------------------
class Registry:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.state = {}       # url -> 'saved' | 'perm'
        self.last = {}        # url -> latest meaningful record
        self.transient = {}   # url -> last transient error code
        self.load()

    def load(self):
        self.state.clear()
        self.last.clear()
        self.transient.clear()
        if not self.path.exists():
            return
        with open(self.path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    self._apply(json.loads(line))
                except ValueError:
                    continue

    def _apply(self, rec):
        url = rec.get("url")
        if not url:
            return
        st, code = rec.get("status"), rec.get("error_code")
        if st == "success":
            self.state[url] = "saved"
            self.last[url] = rec
            self.transient.pop(url, None)
        elif st == "reset":
            self.state.pop(url, None)
            self.transient.pop(url, None)
            self.last.pop(url, None)
        elif st == "failed":
            if code in PERM_ERRORS:
                if self.state.get(url) != "saved":
                    self.state[url] = "perm"
                    self.last[url] = rec
            else:
                self.transient[url] = code or "error:unknown"
                if self.state.get(url) != "saved":
                    self.last[url] = rec

    def append(self, url, status, job_id=None, archive_url=None, error_code=None):
        rec = {"url": url, "job_id": job_id, "status": status, "archive_url": archive_url,
               "error_code": error_code, "recorded_at": now_iso()}
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self._apply(rec)
        return rec

    def status_of(self, url):
        s = self.state.get(url)
        if s:
            return s
        return "retry" if url in self.transient else "pending"

    def pending(self, urls, retry_perm=False):
        return [u for u in urls if self.state.get(u) is None or (retry_perm and self.state.get(u) == "perm")]

    def counts(self, urls):
        saved = sum(1 for u in urls if self.state.get(u) == "saved")
        perm = sum(1 for u in urls if self.state.get(u) == "perm")
        return dict(total=len(urls), saved=saved, perm=perm, pending=len(urls) - saved - perm)


# ---------------------------------------------------------------------------
# Save Page Now 2 client
# ---------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, status, message="", retry_after=None, code=None):
        super().__init__(message)
        self.status, self.message, self.retry_after, self.code = status, message, retry_after, code


class ApiClient:
    def __init__(self, access, secret, base=API_BASE):
        self.access, self.secret, self.base = access.strip(), secret.strip(), base

    def _call(self, method, path, form=None, timeout=60):
        data = urllib.parse.urlencode(form).encode() if form is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers={
            "User-Agent": UA, "Accept": "application/json",
            "Authorization": "LOW %s:%s" % (self.access, self.secret)})
        if data is not None:
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            msg, code = body[:200], None
            try:
                j = json.loads(body)
                msg = j.get("message") or msg
                code = j.get("status_ext")
            except ValueError:
                pass
            ra = e.headers.get("Retry-After") if e.headers else None
            raise ApiError(e.code, msg, int(ra) if ra and ra.isdigit() else None, code)
        except (urllib.error.URLError, socket.timeout, ConnectionError, OSError, http.client.HTTPException) as e:
            raise ApiError(None, str(getattr(e, "reason", e)))
        try:
            return json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            raise ApiError(200, "invalid JSON from server")

    def user_status(self):
        return self._call("GET", "/save/status/user", timeout=30)

    def submit(self, url, params=None):
        d = self._call("POST", "/save", form=dict({"url": url}, **(params or {})))
        if isinstance(d, dict) and d.get("status") == "error":
            raise ApiError(429 if "session" in str(d.get("status_ext", "")) else 400,
                           d.get("message", ""), None, d.get("status_ext"))
        job = d.get("job_id") if isinstance(d, dict) else None
        if not job:
            raise ApiError(200, "no job_id returned (server busy?)")
        return job

    def job_status(self, ids):
        res = self._call("POST", "/save/status", form={"job_ids": ",".join(ids)})
        return res if isinstance(res, list) else [res]


# ---------------------------------------------------------------------------
# Engine: the polite submitter (runs in its own thread, talks via a queue)
# ---------------------------------------------------------------------------
class Engine(threading.Thread):
    def __init__(self, client, registry, urls, cfg, events):
        super().__init__(daemon=True)
        self.client, self.reg, self.urls, self.cfg, self.ev = client, registry, urls, cfg, events
        self.pause_ev, self.stop_ev = threading.Event(), threading.Event()
        self.tm = FAST_TIMING if FAST else NORMAL_TIMING
        self.todo = deque()
        self.inflight = {}
        self.attempts, self.not_before, self.sub_fail = {}, {}, {}
        self.cap = max(1, int(cfg["concurrency"]))
        self.next_submit = self.cooldown_until = 0.0
        self.cd_level = 0
        self.outcomes = deque(maxlen=10)
        self.done_times = deque(maxlen=30)
        self.poll_fail = 0
        self.fatal = None

    # -- events --------------------------------------------------------
    def log(self, lvl, key, **kw):
        self.ev.put(("log", lvl, key, kw))

    # -- thread entry --------------------------------------------------
    def run(self):
        try:
            reason = self._loop()
        except Exception as exc:  # never let the thread die silently
            self.log("err", "log_crash", err=repr(exc))
            reason = "error"
        self.ev.put(("done", reason))

    # -- main loop -----------------------------------------------------
    def _loop(self):
        tm = self.tm
        self.todo = deque(self.reg.pending(self.urls, self.cfg["retry_perm"]))
        if not self.todo:
            return "complete"
        if not self._refresh_account(first=True):
            return "auth"
        self.log("info", "log_start", pending=len(self.todo), cap=self.cap, interval=self.cfg["interval"])
        next_poll = last_pub = last_acct = time.time()
        while True:
            now = time.time()
            if self.stop_ev.is_set():
                self._drain()
                return "stopped"
            if self.fatal:
                return self.fatal
            if self.inflight and now >= next_poll:
                self._poll()
                next_poll = time.time() + tm["poll"]
            if (not self.pause_ev.is_set() and self.todo and len(self.inflight) < self.cap
                    and now >= self.next_submit and now >= self.cooldown_until):
                url = self._next_url(now)
                if url:
                    self._submit(url)
                    self.next_submit = time.time() + self.cfg["interval"]
            if now - last_acct > 300:
                last_acct = now
                self._refresh_account()
            if not self.todo and not self.inflight:
                return "complete"
            if now - last_pub >= 1.0:
                last_pub = now
                self._publish()
            time.sleep(tm["tick"])

    # -- helpers -------------------------------------------------------
    def _refresh_account(self, first=False):
        try:
            st = self.client.user_status()
        except ApiError as e:
            if e.status in (401, 403):
                self.log("err", "log_auth_bad", code=e.status)
                return False
            if first:
                self.log("warn", "log_acct_net", err=e.message)
            return True
        avail, proc = st.get("available"), st.get("processing")
        if isinstance(avail, int) and isinstance(proc, int) and avail + proc >= 1 and avail + proc < self.cap:
            self.cap = avail + proc
            self.log("info", "log_slots", n=self.cap)
        return True

    def _next_url(self, now):
        for _ in range(len(self.todo)):
            u = self.todo.popleft()
            if self.not_before.get(u, 0) <= now:
                return u
            self.todo.append(u)
        return None

    def _submit(self, url):
        try:
            job = self.client.submit(url, self.cfg.get("params"))
        except ApiError as e:
            self._on_submit_error(url, e)
            return
        self.inflight[job] = {"url": url, "t0": time.time()}
        self.ev.put(("inflight", url))

    def _on_submit_error(self, url, e):
        if e.status in (401, 403):
            self.todo.appendleft(url)
            self.log("err", "log_auth_bad", code=e.status)
            self.fatal = "auth"
            return
        code = e.code or ("http-%s" % e.status if e.status else "network")
        self.log("warn", "log_submit_fail", code=code, url=url)
        if e.status == 400 and not e.code:
            self._record_failed(url, "error:bad-request")
            return
        n = self.sub_fail.get(url, 0) + 1                # server-side trouble is not the page's fault:
        self.sub_fail[url] = n                           # retry it after the pause, give up only after many tries
        if n >= 12:
            self.log("warn", "log_giveup_url", url=url, code=code)
            self._record_failed(url, code)
        else:
            self.todo.appendleft(url)
        if e.status == 429 and self.inflight:           # session limit: we are at the cap
            n = max(1, len(self.inflight))
            if n < self.cap:
                self.cap = n
                self.log("info", "log_cap", n=n)
            self.next_submit = time.time() + (2 if FAST else 20)
        else:
            self._cooldown(e.retry_after)

    def _requeue(self, url, code):
        n = self.attempts.get(url, 0) + 1
        self.attempts[url] = n
        if n >= MAX_ATTEMPTS:
            self.log("warn", "log_giveup_url", url=url, code=code)
            self._record_failed(url, code)
        else:
            self.not_before[url] = time.time() + self.tm["retry_wait"] * n
            self.todo.append(url)
            self.log("warn", "log_retry", url=url, code=code, n=n)

    def _record_failed(self, url, code, job=None):
        rec = self.reg.append(url, "failed", job_id=job, error_code=code)
        self.ev.put(("result", rec))

    def _cooldown(self, retry_after=None, minimum=0.0):
        self.cd_level += 1
        dur = retry_after if retry_after else min(self.tm["cd_max"], self.tm["cd_base"] * 2 ** (self.cd_level - 1))
        dur = max(dur, minimum)
        self.cooldown_until = time.time() + dur
        self.outcomes.clear()
        self.log("warn", "log_cooldown", secs=int(dur), n=self.cd_level)
        if self.cd_level > GIVE_UP_AFTER:
            self.log("err", "log_gaveup")
            self.fatal = "gave_up"

    def _poll(self):
        ids = list(self.inflight)
        try:
            results = self.client.job_status(ids)
        except ApiError as e:
            self.poll_fail += 1
            self.log("warn", "log_poll_fail", err=e.message)
            if e.status in (401, 403):
                self.fatal = "auth"
            elif self.poll_fail >= 5:
                self.poll_fail = 0
                self._cooldown(e.retry_after)
            return
        self.poll_fail = 0
        for d in results:
            jid = d.get("job_id")
            job = self.inflight.get(jid)
            if not job:
                continue
            st = d.get("status")
            if st == "success":
                self._on_success(jid, job, d)
            elif st in ("error", "failed"):
                self._on_job_error(jid, job, d)
            elif time.time() - job["t0"] > self.tm["job_timeout"]:
                del self.inflight[jid]
                self._requeue(job["url"], "timeout")

    def _on_success(self, jid, job, d):
        url = job["url"]
        del self.inflight[jid]
        arch = "%s/web/%s/%s" % (API_BASE, d.get("timestamp"), url)
        rec = self.reg.append(url, "success", job_id=jid, archive_url=arch)
        self.ev.put(("result", rec))
        self.log("ok", "log_saved", url=url)
        self.done_times.append(time.time())
        self.outcomes.append(False)
        self.cd_level = 0
        self.attempts.pop(url, None)
        self.sub_fail.pop(url, None)

    def _on_job_error(self, jid, job, d):
        url = job["url"]
        del self.inflight[jid]
        code = d.get("status_ext") or "error:unknown"
        if "RecursionError" in (d.get("message") or ""):
            code = "error:recursion-error"
        if code in BAN_ERRORS:
            self.todo.appendleft(url)
            self._cooldown(minimum=self.tm["ban_wait"])
            return
        if code in PERM_ERRORS:
            self._record_failed(url, code, jid)
            self.log("err", "log_perm", url=url, code=code)
            return
        if code == "error:user-session-limit":
            n = max(1, len(self.inflight))
            if n < self.cap:
                self.cap = n
                self.log("info", "log_cap", n=n)
        self.outcomes.append(True)
        self._requeue(url, code)
        if len(self.outcomes) >= 6 and sum(self.outcomes) >= 0.6 * len(self.outcomes):
            self._cooldown()

    def _drain(self):
        if not self.inflight:
            return
        self.log("info", "log_stopping", s=int(self.tm["drain"]))
        deadline = time.time() + self.tm["drain"]
        while self.inflight and time.time() < deadline:
            self._poll()
            if self.inflight:
                time.sleep(min(2.0, self.tm["poll"]))

    def _publish(self):
        c = self.reg.counts(self.urls)
        per_hour = eta = None
        if len(self.done_times) >= 3:
            span = self.done_times[-1] - self.done_times[0]
            if span > 0:
                per_hour = (len(self.done_times) - 1) / span * 3600
                eta = c["pending"] / per_hour * 3600 if per_hour else None
        now = time.time()
        left = max(0.0, self.cooldown_until - now)
        state = "paused" if self.pause_ev.is_set() else ("cooldown" if left > 0 else "running")
        c.update(inflight=len(self.inflight), cap=self.cap, per_hour=per_hour, eta=eta, cooldown=left, state=state)
        self.ev.put(("progress", c))


# ---------------------------------------------------------------------------
# GUI widgets
# ---------------------------------------------------------------------------
class RoundBar(tk.Canvas):
    def __init__(self, parent, height=16, bg=None):
        super().__init__(parent, height=height, highlightthickness=0, bd=0, bg=bg or C["surface"])
        self.h, self.frac, self.color = height, 0.0, C["accent"]
        self.bind("<Configure>", lambda e: self.redraw())

    def set(self, frac, color=None):
        self.frac = max(0.0, min(1.0, frac))
        self.color = color or C["accent"]
        self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.h
        r = h / 2.0
        if w < h * 2:
            return
        self.create_line(r, r, w - r, r, width=h, capstyle=tk.ROUND, fill=C["trough"])
        if self.frac > 0:
            x = r + (w - 2 * r) * self.frac
            self.create_line(r, r, max(x, r + 0.5), r, width=h, capstyle=tk.ROUND, fill=self.color)


class ScrollFrame(tk.Frame):
    """A vertically scrollable frame (used for the sidebar)."""

    def __init__(self, parent, bg):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.sb.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win, width=e.width))
        for w in (self.canvas, self.inner):
            w.bind("<Enter>", self._bind_wheel)
            w.bind("<Leave>", self._unbind_wheel)

    def _on_inner(self, _e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        need = self.inner.winfo_reqheight() > self.canvas.winfo_height()
        if need and not self.sb.winfo_ismapped():
            self.sb.pack(side="right", fill="y")
        elif not need and self.sb.winfo_ismapped():
            self.sb.pack_forget()

    def _bind_wheel(self, _e):
        self.canvas.bind_all("<MouseWheel>", self._wheel)
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))

    def _unbind_wheel(self, _e):
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.unbind_all(ev)

    def _wheel(self, e):
        if self.inner.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-e.delta / 40) or (-1 if e.delta > 0 else 1), "units")


# ---------------------------------------------------------------------------
# The application
# ---------------------------------------------------------------------------
class App:
    def __init__(self):
        self.cfg = load_config()
        self.lang = self.cfg.get("language") or detect_lang()
        if self.lang not in TEXTS:
            self.lang = "en"
        self.root = tk.Tk()
        self.root.title("%s — %s" % (APP_NAME, APP_SUBTITLE))
        sh = self.root.winfo_screenheight()
        self.root.geometry("1180x%d" % min(860, max(640, sh - 80)))
        self.root.minsize(980, 620)
        self.root.configure(bg=C["bg"])
        try:
            self.icon = tk.PhotoImage(data=ICON_B64)
            self.root.iconphoto(True, self.icon)
            self.logo = self.icon.subsample(2, 2)
        except tk.TclError:
            self.icon = self.logo = None
        self._fonts()
        self._style()

        self.events = queue.Queue()
        self.engine = None
        self.registry = None
        self.urls = []
        self.url_idx = {}
        self.inflight_urls = set()
        self.log_hist = deque(maxlen=4000)
        self.last_progress = None
        self.state = "ready"
        self.busy = False
        self.start_after = False
        self.online_missing = []
        self.online_done = False
        self.closing = False
        self.keys_msg = ("muted", "", {})

        c = self.cfg
        self.v_site = tk.StringVar(value=c.get("site", ""))
        self.v_access = tk.StringVar(value=c.get("access", ""))
        self.v_secret = tk.StringVar(value=c.get("secret", ""))
        self.v_remember = tk.BooleanVar(value=bool(c.get("remember", False)))
        self.v_show = tk.BooleanVar(value=False)
        self.v_crawl = tk.BooleanVar(value=bool(c.get("crawl", False)))
        self.v_filters = tk.BooleanVar(value=bool(c.get("filters", True)))
        self.v_interval = tk.StringVar(value=str(c.get("interval", 12)))
        self.v_conc = tk.StringVar(value=str(c.get("concurrency", 3)))
        self.v_retry = tk.BooleanVar(value=False)
        self.v_filter = tk.StringVar(value="all")
        self.v_search = tk.StringVar(value="")
        self.v_search.trace_add("write", lambda *a: self.refresh_table())
        self.workdir = Path(c["workdir"]) if c.get("workdir") else None

        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.add_log("info", "log_ready", app=APP_NAME, ver=VERSION)
        self.open_workspace(announce=False)
        self.root.after(100, self.pump)

    # ----- i18n --------------------------------------------------------
    def tr(self, key, **kw):
        s = TEXTS[self.lang].get(key) or TEXTS["en"].get(key) or key
        try:
            return s.format(**kw)
        except (KeyError, IndexError):
            return s

    # ----- fonts & style -----------------------------------------------
    def _fonts(self):
        fams = set(tkfont.families(self.root))

        def pick(prefs, default):
            for p in prefs:
                if p in fams:
                    return p
            return default
        base = tkfont.nametofont("TkDefaultFont").actual("family")
        ui = pick(["Inter", "Segoe UI", "SF Pro Text", "Ubuntu", "Noto Sans", "Cantarell", "DejaVu Sans"], base)
        mono = pick(["JetBrains Mono", "Cascadia Mono", "Consolas", "SF Mono", "Menlo", "Ubuntu Mono",
                     "DejaVu Sans Mono"], "TkFixedFont")
        self.f_base = (ui, 10)
        self.f_bold = (ui, 10, "bold")
        self.f_small = (ui, 9)
        self.f_cap = (ui, 8, "bold")
        self.f_title = (ui, 20, "bold")
        self.f_big = (ui, 34, "bold")
        self.f_num = (ui, 20, "bold")
        self.f_mono = (mono, 9)

    def _style(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure(".", background=C["surface"], foreground=C["text"], font=self.f_base, bordercolor=C["border"],
                    lightcolor=C["surface2"], darkcolor=C["surface2"], troughcolor=C["trough"], focuscolor=C["accent"])
        s.configure("TButton", background=C["surface2"], foreground=C["text"], bordercolor=C["border"],
                    lightcolor=C["surface2"], darkcolor=C["surface2"], padding=(14, 8), relief="flat", font=self.f_bold, width=0)
        s.map("TButton", background=[("disabled", C["surface"]), ("active", C["sel"])],
              foreground=[("disabled", C["muted"])], bordercolor=[("active", C["accent"])])
        s.configure("Accent.TButton", background=C["accent"], foreground=C["accent_fg"], bordercolor=C["accent"],
                    lightcolor=C["accent"], darkcolor=C["accent"])
        s.map("Accent.TButton", background=[("disabled", C["surface2"]), ("active", C["accent_hi"])],
              foreground=[("disabled", C["muted"])], lightcolor=[("active", C["accent_hi"])],
              darkcolor=[("active", C["accent_hi"])], bordercolor=[("disabled", C["border"])])
        s.configure("Danger.TButton", foreground=C["err"])
        s.configure("Small.TButton", padding=(10, 5), font=self.f_small)
        for name in ("TEntry", "TSpinbox"):
            s.configure(name, fieldbackground=C["surface2"], foreground=C["text"], insertcolor=C["text"],
                        bordercolor=C["border"], lightcolor=C["surface2"], darkcolor=C["surface2"], padding=6,
                        arrowcolor=C["muted"], background=C["surface2"])
            s.map(name, bordercolor=[("focus", C["accent"])], lightcolor=[("focus", C["surface2"])])
        s.configure("TCombobox", fieldbackground=C["surface2"], background=C["surface2"], foreground=C["text"],
                    arrowcolor=C["muted"], bordercolor=C["border"], lightcolor=C["surface2"],
                    darkcolor=C["surface2"], padding=5)
        s.map("TCombobox", fieldbackground=[("readonly", C["surface2"])], foreground=[("readonly", C["text"])],
              selectbackground=[("readonly", C["surface2"])], selectforeground=[("readonly", C["text"])])
        self.root.option_add("*TCombobox*Listbox.background", C["surface2"])
        self.root.option_add("*TCombobox*Listbox.foreground", C["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", C["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", C["accent_fg"])
        s.configure("TCheckbutton", background=C["surface"], foreground=C["text"], indicatorbackground=C["surface2"],
                    indicatorforeground=C["accent_fg"], indicatormargin=(0, 0, 6, 0), focuscolor=C["surface"])
        s.map("TCheckbutton", background=[("active", C["surface"])],
              indicatorbackground=[("selected", C["accent"]), ("active", C["sel"])])
        s.configure("TNotebook", background=C["bg"], borderwidth=0, tabmargins=(0, 0, 0, 0),
                    bordercolor=C["bg"], lightcolor=C["bg"], darkcolor=C["bg"])
        s.configure("TNotebook.Tab", background=C["surface"], foreground=C["muted"], padding=(20, 10),
                    borderwidth=0, font=self.f_bold, bordercolor=C["bg"], lightcolor=C["bg"], darkcolor=C["bg"])
        s.map("TNotebook.Tab", background=[("selected", C["surface2"])], foreground=[("selected", C["accent"])],
              expand=[("selected", (0, 0, 0, 0)), ("!selected", (0, 0, 0, 0))],
              bordercolor=[("selected", C["surface2"])], lightcolor=[("selected", C["surface2"])],
              darkcolor=[("selected", C["surface2"])])
        s.configure("Treeview", background=C["surface"], fieldbackground=C["surface"], foreground=C["text"],
                    rowheight=26, borderwidth=0, font=self.f_small)
        s.configure("Treeview.Heading", background=C["surface2"], foreground=C["muted"], relief="flat",
                    padding=7, font=self.f_cap)
        s.map("Treeview", background=[("selected", C["sel"])], foreground=[("selected", C["text"])])
        s.map("Treeview.Heading", background=[("active", C["sel"])])
        s.configure("Vertical.TScrollbar", background=C["surface2"], troughcolor=C["bg"], bordercolor=C["bg"],
                    arrowcolor=C["muted"], lightcolor=C["surface2"], darkcolor=C["surface2"], relief="flat")
        s.map("Vertical.TScrollbar", background=[("active", C["sel"])])

    # ----- small widget factories --------------------------------------
    def lbl(self, parent, text="", font=None, fg=None, bg=None, **kw):
        return tk.Label(parent, text=text, font=font or self.f_base, fg=fg or C["text"],
                        bg=bg or C["surface"], **kw)

    def card(self, parent, title=None, pady=(0, 8)):
        outer = tk.Frame(parent, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
        outer.pack(fill="x", pady=pady)
        inner = tk.Frame(outer, bg=C["surface"])
        inner.pack(fill="both", expand=True, padx=14, pady=10)
        if title:
            self.lbl(inner, title, self.f_cap, C["accent"]).pack(anchor="w", pady=(0, 8))
        return inner

    # ----- UI construction ----------------------------------------------
    def build_ui(self):
        if getattr(self, "main", None):
            self.main.destroy()
        self.main = tk.Frame(self.root, bg=C["bg"])
        self.main.pack(fill="both", expand=True)
        self.main.grid_rowconfigure(1, weight=1)
        self.main.grid_columnconfigure(0, weight=1)
        self._build_header()
        body = tk.Frame(self.main, bg=C["bg"])
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(14, 16))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        side = ScrollFrame(body, C["bg"])
        side.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        side.canvas.configure(width=352)
        self._build_sidebar(side.inner)
        right = tk.Frame(body, bg=C["bg"])
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(2, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self._build_progress(right)
        self._build_controls(right)
        self._build_tabs(right)
        self.refresh_all()
        self.replay_log()

    def _build_header(self):
        h = tk.Frame(self.main, bg=C["surface"], highlightthickness=0)
        h.grid(row=0, column=0, sticky="ew")
        tk.Frame(self.main, bg=C["accent"], height=2).grid(row=0, column=0, sticky="sew")
        inner = tk.Frame(h, bg=C["surface"])
        inner.pack(fill="x", padx=20, pady=12)
        if self.logo:
            tk.Label(inner, image=self.logo, bg=C["surface"]).pack(side="left", padx=(0, 12))
        t = tk.Frame(inner, bg=C["surface"])
        t.pack(side="left")
        self.lbl(t, APP_NAME, self.f_title, C["text"]).pack(anchor="w")
        self.lbl(t, self.tr("subtitle"), self.f_small, C["muted"]).pack(anchor="w")
        langs = tk.Frame(inner, bg=C["surface"])
        langs.pack(side="right")
        for code in ("it", "en"):
            on = code == self.lang
            b = tk.Label(langs, text=code.upper(), font=self.f_cap, padx=10, pady=5, cursor="hand2",
                         fg=C["accent_fg"] if on else C["muted"], bg=C["accent"] if on else C["surface2"])
            b.pack(side="left", padx=(0, 4))
            b.bind("<Button-1>", lambda e, c=code: self.set_lang(c))
        self.lbl(inner, "v" + VERSION, self.f_small, C["muted"]).pack(side="right", padx=14)

    def _build_sidebar(self, p):
        # --- site
        c = self.card(p, self.tr("sec_site"))
        self.lbl(c, self.tr("lbl_site"), self.f_small, C["muted"]).pack(anchor="w")
        e = ttk.Entry(c, textvariable=self.v_site)
        e.pack(fill="x", pady=(2, 6))
        e.bind("<Return>", lambda ev: self.find_pages())
        ttk.Checkbutton(c, text=self.tr("chk_crawl"), variable=self.v_crawl).pack(anchor="w", pady=1)
        ttk.Checkbutton(c, text=self.tr("chk_filters"), variable=self.v_filters).pack(anchor="w", pady=1)
        row = tk.Frame(c, bg=C["surface"])
        row.pack(fill="x", pady=(8, 4))
        self.btn_find = ttk.Button(row, text=self.tr("btn_find"), command=self.find_pages)
        self.btn_find.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.btn_file = ttk.Button(row, text=self.tr("btn_file"), command=self.load_file)
        self.btn_file.pack(side="left", expand=True, fill="x", padx=(4, 0))
        self.lbl_found = self.lbl(c, "", self.f_small, C["muted"])
        self.lbl_found.pack(anchor="w")
        # --- account
        c = self.card(p, self.tr("sec_account"))
        self.lbl(c, self.tr("lbl_access"), self.f_small, C["muted"]).pack(anchor="w")
        ttk.Entry(c, textvariable=self.v_access).pack(fill="x", pady=(2, 6))
        self.lbl(c, self.tr("lbl_secret"), self.f_small, C["muted"]).pack(anchor="w")
        self.e_secret = ttk.Entry(c, textvariable=self.v_secret, show="•")
        self.e_secret.pack(fill="x", pady=(2, 6))
        ttk.Checkbutton(c, text=self.tr("chk_show"), variable=self.v_show, command=self._toggle_show).pack(anchor="w", pady=1)
        ttk.Checkbutton(c, text=self.tr("chk_remember"), variable=self.v_remember).pack(anchor="w", pady=1)
        row = tk.Frame(c, bg=C["surface"])
        row.pack(fill="x", pady=(8, 4))
        self.btn_check = ttk.Button(row, text=self.tr("btn_check"), command=self.check_keys, style="Small.TButton")
        self.btn_check.pack(side="left")
        link = self.lbl(row, self.tr("lnk_keys"), self.f_small, C["info"], cursor="hand2")
        link.pack(side="left", padx=10)
        link.bind("<Button-1>", lambda e: webbrowser.open(S3_KEYS_URL))
        self.lbl_keys = self.lbl(c, "", self.f_small, C["muted"], wraplength=300, justify="left")
        self.lbl_keys.pack(anchor="w", pady=(2, 0))
        # --- params
        c = self.card(p, self.tr("sec_params"))
        for label, var, lo, hi in ((self.tr("lbl_interval"), self.v_interval, 9, 120),
                                   (self.tr("lbl_conc"), self.v_conc, 1, 6)):
            r = tk.Frame(c, bg=C["surface"])
            r.pack(fill="x", pady=3)
            self.lbl(r, label, self.f_base).pack(side="left")
            ttk.Spinbox(r, from_=lo, to=hi, textvariable=var, width=5, justify="center").pack(side="right")
        self.lbl(c, self.tr("tip_conc"), self.f_small, C["muted"], wraplength=300, justify="left").pack(anchor="w", pady=(2, 6))
        ttk.Checkbutton(c, text=self.tr("chk_retry"), variable=self.v_retry).pack(anchor="w")
        # --- workspace
        c = self.card(p, self.tr("sec_work"), pady=(0, 0))
        self.lbl_work = self.lbl(c, "", self.f_small, C["muted"], wraplength=300, justify="left")
        self.lbl_work.pack(anchor="w", pady=(0, 8))
        ttk.Button(c, text=self.tr("btn_change"), command=self.change_workdir, style="Small.TButton").pack(anchor="w")

    def _build_progress(self, p):
        card = tk.Frame(p, bg=C["surface"], highlightthickness=1, highlightbackground=C["border"])
        card.grid(row=0, column=0, sticky="ew")
        inner = tk.Frame(card, bg=C["surface"])
        inner.pack(fill="x", padx=20, pady=16)
        top = tk.Frame(inner, bg=C["surface"])
        top.pack(fill="x")
        self.lbl_pct = self.lbl(top, "0%", self.f_big, C["accent"])
        self.lbl_pct.pack(side="left")
        mid = tk.Frame(top, bg=C["surface"])
        mid.pack(side="left", padx=18)
        self.lbl_counts = self.lbl(mid, "", self.f_bold)
        self.lbl_counts.pack(anchor="w")
        self.lbl_sub = self.lbl(mid, "", self.f_small, C["muted"])
        self.lbl_sub.pack(anchor="w")
        self.pill = tk.Label(top, text="", font=self.f_cap, padx=14, pady=6)
        self.pill.pack(side="right")
        self.bar = RoundBar(inner, 16)
        self.bar.pack(fill="x", pady=(14, 14))
        stats = tk.Frame(inner, bg=C["surface"])
        stats.pack(fill="x")
        self.stat = {}
        for i, key in enumerate(("stat_speed", "stat_eta", "stat_slots", "stat_left")):
            stats.grid_columnconfigure(i, weight=1, uniform="s")
            f = tk.Frame(stats, bg=C["surface"])
            f.grid(row=0, column=i, sticky="w")
            self.lbl(f, self.tr(key), self.f_cap, C["muted"]).pack(anchor="w")
            self.stat[key] = self.lbl(f, "—", (self.f_num[0], 15, "bold"))
            self.stat[key].pack(anchor="w")

    def _build_controls(self, p):
        row = tk.Frame(p, bg=C["bg"])
        row.grid(row=1, column=0, sticky="ew", pady=12)
        self.btn_start = ttk.Button(row, text=self.tr("btn_start"), command=self.start, style="Accent.TButton")
        self.btn_start.pack(side="left", padx=(0, 8))
        self.btn_pause = ttk.Button(row, text=self.tr("btn_pause"), command=self.toggle_pause)
        self.btn_pause.pack(side="left", padx=(0, 8))
        self.btn_stop = ttk.Button(row, text=self.tr("btn_stop"), command=self.stop, style="Danger.TButton")
        self.btn_stop.pack(side="left", padx=(0, 8))
        ttk.Button(row, text=self.tr("btn_export"), command=self.export_csv).pack(side="right")
        ttk.Button(row, text=self.tr("btn_verify"), command=self.final_check).pack(side="right", padx=8)

    def _build_tabs(self, p):
        nb = ttk.Notebook(p)
        nb.grid(row=2, column=0, sticky="nsew")
        self.nb = nb
        # log
        t = tk.Frame(nb, bg=C["surface2"])
        nb.add(t, text="  " + self.tr("tab_log") + "  ")
        self.txt = tk.Text(t, bg=C["trough"], fg=C["text"], font=self.f_mono, bd=0, highlightthickness=0, wrap="word",
                           padx=12, pady=10, state="disabled", insertbackground=C["text"], selectbackground=C["sel"])
        sb = ttk.Scrollbar(t, command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.txt.pack(fill="both", expand=True)
        for tag, col in (("info", C["text"]), ("ok", C["ok"]), ("warn", C["warn"]), ("err", C["err"]), ("ts", C["muted"])):
            self.txt.tag_configure(tag, foreground=col)
        # pages
        t = tk.Frame(nb, bg=C["surface"])
        nb.add(t, text="  " + self.tr("tab_pages") + "  ")
        bar = tk.Frame(t, bg=C["surface"])
        bar.pack(fill="x", padx=12, pady=10)
        self.flt_map = [("all", "flt_all"), ("saved", "flt_saved"), ("pending", "flt_pending"), ("failed", "flt_failed")]
        self.cb_filter = ttk.Combobox(bar, state="readonly", width=14, values=[self.tr(k) for _, k in self.flt_map])
        self.cb_filter.current([k for k, _ in self.flt_map].index(self.v_filter.get()))
        self.cb_filter.pack(side="left")
        self.cb_filter.bind("<<ComboboxSelected>>", self._on_filter)
        self.lbl(bar, self.tr("lbl_search"), self.f_small, C["muted"]).pack(side="left", padx=(14, 6))
        ttk.Entry(bar, textvariable=self.v_search, width=30).pack(side="left")
        self.lbl_shown = self.lbl(bar, "", self.f_small, C["muted"])
        self.lbl_shown.pack(side="right")
        wrap = tk.Frame(t, bg=C["surface"])
        wrap.pack(fill="both", expand=True)
        cols = ("url", "status", "detail", "time")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        for col, w, st in (("url", 380, True), ("status", 130, False), ("detail", 330, True), ("time", 90, False)):
            self.tree.heading(col, text=self.tr("col_" + col), anchor="w")
            self.tree.column(col, width=w, stretch=st, anchor="w")
        vs = ttk.Scrollbar(wrap, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        for tag, col in (("saved", C["ok"]), ("perm", C["err"]), ("retry", C["warn"]),
                         ("inflight", C["info"]), ("pending", C["muted"])):
            self.tree.tag_configure(tag, foreground=col)
        self.tree.bind("<Double-1>", self._open_row)
        # verify
        t = tk.Frame(nb, bg=C["surface"])
        nb.add(t, text="  " + self.tr("tab_verify") + "  ")
        tiles = tk.Frame(t, bg=C["surface"])
        tiles.pack(fill="x", padx=14, pady=(14, 6))
        self.vt = {}
        for i, (key, col) in enumerate((("v_total", C["text"]), ("v_saved", C["ok"]), ("v_perm", C["err"]),
                                        ("v_missing", C["warn"]), ("v_online", C["info"]), ("v_offline", C["warn"]))):
            tiles.grid_columnconfigure(i % 3, weight=1, uniform="v")
            f = tk.Frame(tiles, bg=C["surface2"], highlightthickness=1, highlightbackground=C["border"])
            f.grid(row=i // 3, column=i % 3, sticky="ew", padx=3, pady=3)
            self.lbl(f, self.tr(key), self.f_cap, C["muted"], bg=C["surface2"]).pack(anchor="w", padx=12, pady=(7, 0))
            self.vt[key] = self.lbl(f, "—", (self.f_num[0], 17, "bold"), col, bg=C["surface2"])
            self.vt[key].pack(anchor="w", padx=12, pady=(0, 7))
        b = tk.Frame(t, bg=C["surface"])
        b.pack(fill="x", padx=14, pady=6)
        ttk.Button(b, text=self.tr("btn_vlocal"), command=self.verify_local, style="Small.TButton").pack(side="left")
        self.btn_vonline = ttk.Button(b, text=self.tr("btn_vonline"), command=self.verify_online, style="Small.TButton")
        self.btn_vonline.pack(side="left", padx=8)
        self.btn_requeue = ttk.Button(b, text=self.tr("btn_requeue"), command=self.requeue_missing, style="Small.TButton")
        self.btn_requeue.pack(side="left")
        note = self.lbl(t, self.tr("v_note"), self.f_small, C["muted"], justify="left", anchor="w")
        note.pack(fill="x", padx=16, pady=(2, 8))
        note.bind("<Configure>", lambda e, w=note: w.configure(wraplength=max(200, e.width - 4)))
        wrap = tk.Frame(t, bg=C["surface"])
        wrap.pack(fill="both", expand=True)
        self.vtree = ttk.Treeview(wrap, columns=("url", "reason"), show="headings", selectmode="browse")
        self.vtree.heading("url", text=self.tr("col_url"), anchor="w")
        self.vtree.heading("reason", text=self.tr("col_detail"), anchor="w")
        self.vtree.column("url", width=460, stretch=True)
        self.vtree.column("reason", width=330, stretch=True)
        vs = ttk.Scrollbar(wrap, command=self.vtree.yview)
        self.vtree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.vtree.pack(fill="both", expand=True)

    # ----- language ------------------------------------------------------
    def set_lang(self, code):
        if code == self.lang or self.engine_alive() or self.busy:
            return
        self.lang = code
        self.cfg["language"] = code
        save_config(self.cfg)
        self.build_ui()

    # ----- logging ---------------------------------------------------------
    def add_log(self, lvl, key, **kw):
        entry = (datetime.now().strftime("%H:%M:%S"), lvl, key, kw)
        self.log_hist.append(entry)
        self._write_log(entry)

    def _write_log(self, entry):
        if not getattr(self, "txt", None):
            return
        ts, lvl, key, kw = entry
        at_end = self.txt.yview()[1] >= 0.98
        self.txt.configure(state="normal")
        self.txt.insert("end", "[%s] " % ts, "ts")
        self.txt.insert("end", self.tr(key, **kw) + "\n", lvl)
        self.txt.configure(state="disabled")
        if at_end:
            self.txt.see("end")

    def replay_log(self):
        for entry in self.log_hist:
            self._write_log(entry)

    # ----- keys ------------------------------------------------------------
    def _toggle_show(self):
        self.e_secret.configure(show="" if self.v_show.get() else "•")

    def client(self):
        a, s = self.v_access.get().strip(), self.v_secret.get().strip()
        if not a or not s:
            return None
        return ApiClient(a, s)

    def set_keys_msg(self, kind, key, **kw):
        self.keys_msg = (kind, key, kw)
        col = {"ok": C["ok"], "err": C["err"], "muted": C["muted"]}[kind]
        self.lbl_keys.configure(text=self.tr(key, **kw) if key else "", fg=col)

    def check_keys(self):
        cl = self.client()
        if not cl:
            self.set_keys_msg("err", "keys_missing")
            return
        self.set_keys_msg("muted", "keys_wait")

        def work():
            try:
                st = cl.user_status()
                self.events.put(("keys", "ok", st))
            except ApiError as e:
                self.events.put(("keys", "bad" if e.status in (401, 403) else "net", e.message))
        threading.Thread(target=work, daemon=True).start()

    # ----- workspace ---------------------------------------------------------
    def default_workdir(self, base):
        return Path.home() / APP_NAME / re.sub(r"[^A-Za-z0-9._-]", "_", base)

    def open_workspace(self, announce=True):
        self.lbl_work.configure(text=str(self.workdir) if self.workdir else "—")
        if not self.workdir:
            self.refresh_all()
            return
        up = self.workdir / "urls.txt"
        self.urls = []
        if up.exists():
            with open(up, encoding="utf-8", errors="replace") as f:
                self.urls = [l.strip() for l in f if l.strip()]
        self.registry = Registry(self.workdir / "results.jsonl")
        sf = self.workdir / "site.txt"
        if sf.exists() and not self.v_site.get().strip():
            self.v_site.set(sf.read_text(encoding="utf-8").strip())
        elif self.urls and not self.v_site.get().strip():
            p = urllib.parse.urlsplit(self.urls[0])
            self.v_site.set("%s://%s/" % (p.scheme, p.netloc))
        self.reindex()
        if self.urls or announce:
            self.add_log("info", "log_workspace", path=str(self.workdir),
                         saved=self.registry.counts(self.urls)["saved"] if self.urls else 0)
        self.refresh_all()

    def change_workdir(self):
        if self.engine_alive():
            return
        d = filedialog.askdirectory(title=self.tr("msg_pickdir"), initialdir=str(self.workdir or Path.home()))
        if d:
            self.workdir = Path(d)
            self.cfg["workdir"] = d
            self.open_workspace()

    def ensure_workdir(self, base):
        if not self.workdir:
            self.workdir = self.default_workdir(base)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.lbl_work.configure(text=str(self.workdir))

    def reindex(self):
        self.url_idx = {u: i for i, u in enumerate(self.urls)}
        self.refresh_table()

    # ----- finding pages -------------------------------------------------------
    def set_busy(self, flag):
        self.busy = flag
        self.update_controls()

    def find_pages(self):
        if self.busy or self.engine_alive():
            return
        parsed = parse_site(self.v_site.get())
        if not parsed:
            messagebox.showinfo(APP_NAME, self.tr("msg_site"))
            return
        root_url, base = parsed
        self.ensure_workdir(base)
        use_crawl, filters = self.v_crawl.get(), self.v_filters.get()
        self.set_busy(True)
        ev = self.events.put

        def work():
            urls = []
            try:
                ev(("log", "info", "log_sitemap_try", {}))
                urls = discover_sitemaps(root_url, lambda: False)
                ev(("log", "ok" if urls else "warn", "log_sitemap_found", {"n": len(urls)}))
                if use_crawl or not urls:
                    if not use_crawl:
                        ev(("log", "info", "log_hint_crawl", {}))
                    ev(("log", "info", "log_crawl_start", {}))
                    found = crawl(root_url, base, lambda: False,
                                  lambda n: ev(("log", "info", "log_crawl_prog", {"n": n})))
                    ev(("log", "ok", "log_crawl_done", {"n": len(found)}))
                    urls.extend(found)
                urls = clean_urls(urls, base, filters)
            except Exception as exc:
                ev(("log", "err", "log_discover_fail", {"err": repr(exc)}))
            ev(("urls", urls, root_url))
        threading.Thread(target=work, daemon=True).start()

    def load_file(self):
        if self.busy or self.engine_alive():
            return
        path = filedialog.askopenfilename(title=self.tr("msg_pickfile"))
        if not path:
            return
        with open(path, encoding="utf-8", errors="replace") as f:
            raw = f.read().splitlines()
        urls = clean_urls(raw, None, self.v_filters.get())
        self.add_log("info", "log_file_loaded", n=len(urls), path=path)
        root = ""
        if urls:
            p = urllib.parse.urlsplit(urls[0])
            root = "%s://%s/" % (p.scheme, p.netloc)
            if not self.v_site.get().strip():
                self.v_site.set(root)
        base = host_base(urllib.parse.urlsplit(urls[0]).netloc) if urls else "list"
        self.ensure_workdir(base)
        self.events.put(("urls", urls, root))

    def set_urls(self, urls, root):
        self.set_busy(False)
        if not urls:
            self.start_after = False
            messagebox.showinfo(APP_NAME, self.tr("msg_nolist"))
            self.refresh_all()
            return
        self.urls = urls
        self.workdir.mkdir(parents=True, exist_ok=True)
        (self.workdir / "urls.txt").write_text("\n".join(urls) + "\n", encoding="utf-8")
        if root:
            (self.workdir / "site.txt").write_text(root, encoding="utf-8")
        self.registry = Registry(self.workdir / "results.jsonl")
        self.add_log("ok", "log_list_ready", n=len(urls), path=str(self.workdir / "urls.txt"))
        self.reindex()
        self.refresh_all()
        if self.start_after:
            self.start_after = False
            self.start()

    # ----- run control ---------------------------------------------------------
    def engine_alive(self):
        return bool(self.engine and self.engine.is_alive())

    def persist(self):
        c = self.cfg
        c.update(site=self.v_site.get().strip(), workdir=str(self.workdir) if self.workdir else "",
                 crawl=self.v_crawl.get(), filters=self.v_filters.get(), interval=self.v_interval.get(),
                 concurrency=self.v_conc.get(), remember=self.v_remember.get(), language=self.lang)
        if self.v_remember.get():
            c.update(access=self.v_access.get().strip(), secret=self.v_secret.get().strip())
        else:
            c.pop("access", None)
            c.pop("secret", None)
        save_config(c)

    def start(self):
        if self.engine_alive() or self.busy:
            return
        cl = self.client()
        if not cl:
            messagebox.showinfo(APP_NAME, self.tr("msg_keys"))
            return
        if not self.urls:
            self.start_after = True
            self.find_pages()
            return
        try:
            interval = float(self.v_interval.get().replace(",", "."))
            conc = int(float(self.v_conc.get()))
        except ValueError:
            interval, conc = 12.0, 3
        if not FAST:
            interval = max(9.0, interval)
        conc = max(1, min(6, conc))
        self.v_interval.set(("%g" % interval))
        self.v_conc.set(str(conc))
        self.persist()
        self.registry = self.registry or Registry(self.workdir / "results.jsonl")
        cfg = dict(interval=interval, concurrency=conc, retry_perm=self.v_retry.get(), params={})
        self.engine = Engine(cl, self.registry, self.urls, cfg, self.events)
        self.state = "running"
        self.inflight_urls.clear()
        self.engine.start()
        self.update_controls()

    def toggle_pause(self):
        if not self.engine_alive():
            return
        if self.engine.pause_ev.is_set():
            self.engine.pause_ev.clear()
        else:
            self.engine.pause_ev.set()
            self.state = "paused"
        self.update_controls()
        self.update_progress()

    def stop(self):
        if self.engine_alive():
            self.engine.stop_ev.set()
            self.state = "stopping"
            self.update_controls()
            self.update_progress()

    def on_close(self):
        if self.engine_alive():
            if not messagebox.askyesno(APP_NAME, self.tr("msg_exit")):
                return
            self.engine.stop_ev.set()
            self.closing = True
            self.state = "stopping"
            self.update_progress()
            self._wait_close(0)
            return
        self.persist()
        self.root.destroy()

    def _wait_close(self, n):
        if self.engine_alive() and n < 400:
            self.root.after(150, lambda: self._wait_close(n + 1))
        else:
            self.persist()
            self.root.destroy()

    # ----- events from threads -----------------------------------------------------
    def pump(self):
        try:
            for _ in range(300):
                self.handle(self.events.get_nowait())
        except queue.Empty:
            pass
        except tk.TclError:
            return
        self.root.after(100, self.pump)

    def handle(self, ev):
        kind = ev[0]
        if kind == "log":
            self.add_log(ev[1], ev[2], **ev[3])
        elif kind == "progress":
            self.last_progress = ev[1]
            self.state = ev[1]["state"] if self.state not in ("stopping",) else self.state
            self.update_progress()
        elif kind == "inflight":
            self.inflight_urls.add(ev[1])
            self.update_row(ev[1])
        elif kind == "result":
            rec = ev[1]
            self.inflight_urls.discard(rec["url"])
            self.update_row(rec["url"])
            self.update_progress(force=True)
        elif kind == "done":
            self.on_engine_done(ev[1])
        elif kind == "urls":
            self.set_urls(ev[1], ev[2])
        elif kind == "keys":
            self.on_keys(ev[1], ev[2])
        elif kind == "cdx":
            self.on_cdx(ev[1], ev[2])

    def on_keys(self, res, data):
        if res == "ok":
            self.set_keys_msg("ok", "keys_ok", avail=data.get("available", "?"),
                              used=data.get("daily_captures", "?"), limit=data.get("daily_captures_limit", "?"))
        elif res == "bad":
            self.set_keys_msg("err", "keys_bad")
        else:
            self.set_keys_msg("err", "keys_net", err=data)

    def on_engine_done(self, reason):
        self.inflight_urls.clear()
        self.refresh_table()
        if reason == "complete":
            self.state = "done"
            self.add_log("ok", "log_done")
            self.update_progress(force=True)
            self.verify_local()
            self.nb.select(2)
            self.update_controls()
            if not self.closing:
                c = self.registry.counts(self.urls)
                messagebox.showinfo(self.tr("msg_done"), self.tr("msg_done_body", saved=c["saved"], total=c["total"]))
            return
        if reason == "stopped":
            self.state = "stopped"
            self.add_log("info", "log_stopped")
        else:
            self.state = "error"
            if not self.closing:
                messagebox.showwarning(APP_NAME, self.tr("msg_auth" if reason == "auth" else "msg_gaveup"))
        self.update_progress(force=True)
        self.update_controls()

    # ----- progress rendering --------------------------------------------------------
    def counts(self):
        if self.registry and self.urls:
            return self.registry.counts(self.urls)
        return dict(total=len(self.urls), saved=0, perm=0, pending=len(self.urls))

    def update_progress(self, force=False):
        c = dict(self.counts())
        lp = self.last_progress if self.engine_alive() else None
        total, saved, perm, pending = c["total"], c["saved"], c["perm"], c["pending"]
        done = saved + perm
        frac = done / total if total else 0.0
        self.lbl_pct.configure(text="%d%%" % int(frac * 100))
        self.lbl_counts.configure(text="%d / %d %s" % (saved, total, self.tr("stat_saved")))
        sub = ""
        if perm:
            sub = "%s: %d" % (self.tr("v_perm").capitalize(), perm)
        self.lbl_sub.configure(text=sub)
        st = self.state
        color = {"ready": (C["surface2"], C["muted"]), "running": (C["accent"], C["accent_fg"]),
                 "paused": (C["info"], C["bg"]), "cooldown": (C["warn"], C["accent_fg"]),
                 "done": (C["ok"], C["bg"]), "stopped": (C["surface2"], C["text"]),
                 "stopping": (C["info"], C["bg"]), "error": (C["err"], C["bg"])}.get(st, (C["surface2"], C["muted"]))
        if self.busy:
            text, color = self.tr("st_busy"), (C["info"], C["bg"])
        elif st == "cooldown" and lp:
            text = self.tr("st_cooldown", t=fmt_cd(lp.get("cooldown", 0)))
        else:
            text = self.tr("st_" + st) if st in ("ready", "running", "paused", "done", "stopped", "stopping", "error") else self.tr("st_ready")
        self.pill.configure(text="  %s  " % text.upper(), bg=color[0], fg=color[1])
        self.bar.set(frac, C["ok"] if (st == "done" or (total and done >= total)) else C["accent"])
        if lp:
            self.stat["stat_speed"].configure(text=self.tr("per_hour", n=int(lp["per_hour"])) if lp.get("per_hour") else "—")
            self.stat["stat_eta"].configure(text=fmt_eta(lp.get("eta")))
            self.stat["stat_slots"].configure(text="%d / %d" % (lp.get("inflight", 0), lp.get("cap", 0)))
        else:
            for k in ("stat_speed", "stat_eta", "stat_slots"):
                self.stat[k].configure(text="—")
        self.stat["stat_left"].configure(text=str(pending) if total else "—")

    def update_controls(self):
        alive = self.engine_alive()
        busy = self.busy
        self.btn_start.configure(state="disabled" if (alive or busy) else "normal")
        self.btn_pause.configure(state="normal" if alive and self.state != "stopping" else "disabled",
                                 text=self.tr("btn_resume") if (alive and self.engine.pause_ev.is_set()) else self.tr("btn_pause"))
        self.btn_stop.configure(state="normal" if alive and self.state != "stopping" else "disabled")
        for b in (self.btn_find, self.btn_file):
            b.configure(state="disabled" if (alive or busy) else "normal")

    def refresh_all(self):
        self.lbl_found.configure(text=self.tr("lbl_found", n=len(self.urls)) if self.urls else self.tr("lbl_none"))
        self.lbl_work.configure(text=str(self.workdir) if self.workdir else "—")
        if self.keys_msg[1]:
            self.set_keys_msg(self.keys_msg[0], self.keys_msg[1], **self.keys_msg[2])
        self.update_progress()
        self.update_controls()
        self.refresh_table()

    # ----- pages table -----------------------------------------------------------------
    def row_for(self, url):
        reg = self.registry
        st = "inflight" if url in self.inflight_urls else (reg.status_of(url) if reg else "pending")
        rec = reg.last.get(url) if reg else None
        if st == "saved":
            return "saved", self.tr("s_saved"), (rec or {}).get("archive_url") or "", local_when((rec or {}).get("recorded_at", ""))
        if st == "perm":
            return "perm", self.tr("s_perm"), (rec or {}).get("error_code") or "", local_when((rec or {}).get("recorded_at", ""))
        if st == "retry":
            return "retry", self.tr("s_retry"), reg.transient.get(url, ""), local_when((rec or {}).get("recorded_at", ""))
        if st == "inflight":
            return "inflight", self.tr("s_inflight"), "", ""
        return "pending", self.tr("s_pending"), "", ""

    def _matches(self, tag, url):
        f = self.v_filter.get()
        if f == "saved" and tag != "saved":
            return False
        if f == "pending" and tag not in ("pending", "retry", "inflight"):
            return False
        if f == "failed" and tag not in ("perm", "retry"):
            return False
        q = self.v_search.get().strip().lower()
        return not q or q in url.lower()

    def refresh_table(self):
        if not getattr(self, "tree", None):
            return
        self.tree.delete(*self.tree.get_children())
        shown = 0
        for i, u in enumerate(self.urls):
            tag, status, detail, when = self.row_for(u)
            if self._matches(tag, u):
                self.tree.insert("", "end", iid=str(i), values=(u, status, detail, when), tags=(tag,))
                shown += 1
        self.lbl_shown.configure(text="%d / %d" % (shown, len(self.urls)))

    def update_row(self, url):
        i = self.url_idx.get(url)
        if i is None or not getattr(self, "tree", None):
            return
        tag, status, detail, when = self.row_for(url)
        iid = str(i)
        exists = self.tree.exists(iid)
        if self._matches(tag, url):
            if exists:
                self.tree.item(iid, values=(url, status, detail, when), tags=(tag,))
            elif len(self.tree.get_children()) < 5000:
                self.tree.insert("", "end", iid=iid, values=(url, status, detail, when), tags=(tag,))
        elif exists:
            self.tree.delete(iid)

    def _on_filter(self, _e):
        self.v_filter.set(self.flt_map[self.cb_filter.current()][0])
        self.refresh_table()

    def _open_row(self, _e):
        sel = self.tree.selection()
        if not sel:
            return
        url = self.urls[int(sel[0])]
        rec = self.registry.last.get(url) if self.registry else None
        webbrowser.open((rec or {}).get("archive_url") or url)

    # ----- final check ---------------------------------------------------------------------
    def final_check(self):
        self.verify_local()
        self.nb.select(2)

    def verify_local(self):
        if not self.registry or not self.urls:
            return
        c = self.registry.counts(self.urls)
        self.vt["v_total"].configure(text=str(c["total"]))
        self.vt["v_saved"].configure(text=str(c["saved"]))
        self.vt["v_perm"].configure(text=str(c["perm"]))
        self.vt["v_missing"].configure(text=str(c["pending"]))
        self.fill_vtree()

    def fill_vtree(self):
        self.vtree.delete(*self.vtree.get_children())
        online_bad = set(self.online_missing) if self.online_done else set()
        for u in self.urls:
            st = self.registry.status_of(u)
            reason = None
            if st == "perm":
                reason = self.tr("r_perm", code=(self.registry.last.get(u) or {}).get("error_code", ""))
            elif st == "retry":
                reason = self.tr("r_retry", code=self.registry.transient.get(u, ""))
            elif st == "pending":
                reason = self.tr("r_pending")
            elif u in online_bad:
                reason = self.tr("r_offline")
            if reason:
                self.vtree.insert("", "end", values=(u, reason))

    def verify_online(self):
        parsed = parse_site(self.v_site.get())
        if not parsed or not self.urls:
            messagebox.showinfo(APP_NAME, self.tr("msg_nolist"))
            return
        base = parsed[1]
        self.btn_vonline.configure(state="disabled")
        self.add_log("info", "log_cdx_start")

        def work():
            try:
                self.events.put(("cdx", "ok", cdx_fetch(base)))
            except Exception as exc:
                self.events.put(("cdx", "err", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def on_cdx(self, res, data):
        self.btn_vonline.configure(state="normal")
        if res != "ok":
            self.add_log("err", "log_cdx_fail", err=data)
            return
        self.verify_local()
        found = [u for u in self.urls if norm_url(u) in data]
        self.online_missing = [u for u in self.urls if self.registry.state.get(u) == "saved" and norm_url(u) not in data]
        self.online_done = True
        self.vt["v_online"].configure(text=str(len(found)))
        self.vt["v_offline"].configure(text=str(len(self.urls) - len(found)))
        self.add_log("ok", "log_cdx_ok", ok=len(found), total=len(self.urls))
        self.fill_vtree()

    def requeue_missing(self):
        if not self.online_missing or self.engine_alive():
            return
        for u in self.online_missing:
            self.registry.append(u, "reset")
        self.add_log("info", "log_requeued", n=len(self.online_missing))
        self.online_missing, self.online_done = [], False
        self.refresh_all()
        self.verify_local()

    def export_csv(self):
        if not self.registry or not self.urls:
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="chronovault_report.csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["url", "status", "archive_url", "error_code", "recorded_at"])
            for u in self.urls:
                rec = self.registry.last.get(u) or {}
                w.writerow([u, self.registry.status_of(u), rec.get("archive_url") or "",
                            rec.get("error_code") or self.registry.transient.get(u, ""), rec.get("recorded_at") or ""])
        self.add_log("ok", "log_exported", path=path)
        messagebox.showinfo(APP_NAME, self.tr("msg_exported", path=path))

    def run(self):
        self.root.mainloop()


def main():
    if "--version" in sys.argv:
        print("%s %s" % (APP_NAME, VERSION))
        return
    App().run()


if __name__ == "__main__":
    main()
