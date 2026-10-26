<img width="1280" height="900" alt="chronovault_screenshot" src="https://github.com/user-attachments/assets/5ce3e067-6589-4e20-918f-ade6ac00736e" />


# ChronoVault · Wayback Site Archiver

Archive a **whole website** on the [Internet Archive's Wayback Machine](https://web.archive.org) from a desktop app.
No `pip install`, no terminal juggling: one Python file, standard library only.

![ChronoVault](chronovault_screenshot.png)

*(Screenshot taken against a simulated archive.org server, so the speed shown is not real.)*

## Features

- **Finds your pages**: sitemaps (including nested indexes and `.gz`), an optional polite crawler (honours `robots.txt`), or your own list of URLs.
- **Polite by design**: uses the official Save Page Now 2 API, at least 9 s between submissions, and never more simultaneous captures than your account allows (it reads your free slots and lowers itself on "sessions full").
- **Backs off, never gives up silently**: on `429`/`503`/network errors it pauses with exponential back-off (honouring `Retry-After`) and resumes on its own.
- **Resumable**: every result is appended to `results.jsonl` the moment it arrives. Stop, close the PC, come back tomorrow.
- **Progress at a glance**: percentage, speed, ETA, slots in use, live log, and a per-page table (double-click opens the archived copy).
- **Final check**: local comparison (saved / not archivable / missing) plus verification against the public Wayback index, with one click to re-queue what is not found.
- **CSV export**, Italian and English UI, keys stored only if you tick *Remember keys*.

## Quick start

```bash
python3 chronovault.py
```

Requirements: Python 3.8+ with `tkinter`, and a free archive.org account.
Get your keys at <https://archive.org/account/s3.php> (access key + secret key).

| System | If tkinter is missing |
|---|---|
| Debian / Ubuntu / Kubuntu / Mint | `sudo apt install python3-tk` |
| Fedora | `sudo dnf install python3-tkinter` |
| Arch / Manjaro | `sudo pacman -S tk` |
| macOS (Homebrew) | `brew install python-tk` |
| Windows | re-run the Python installer and enable *tcl/tk* |

1. Type the site address, click **Find pages** (or just **Start**: it finds them first).
2. Paste your keys and click **Check keys**.
3. Click **Start**. Leave it running; **Stop** and **Start** again whenever you like.

## Files

Everything lives in a working folder (default `~/ChronoVault/<site>/`):

| File | What it is |
|---|---|
| `urls.txt` | the list of pages to archive |
| `results.jsonl` | the registry, one JSON line per result (append-only) |
| `site.txt` | the site address of this workspace |

Settings are saved in `~/.config/chronovault/config.json` (Linux), `%APPDATA%\ChronoVault` (Windows) or `~/Library/Application Support/ChronoVault` (macOS).

## Good to know

- Pages that archive.org cannot capture (404, blocked by the site…) are listed as *not archivable* and not retried unless you tick the option.
- The public index can lag by hours: a page "not found online" right after saving is not necessarily a failure.
- Be kind to the Internet Archive: it is a non-profit. Archive sites you care about, and consider [donating](https://archive.org/donate).

## Italiano (breve)

Esegui `python3 chronovault.py`, inserisci l'indirizzo del sito e le chiavi di archive.org
(<https://archive.org/account/s3.php>), poi premi **Avvia**. Puoi fermarlo e riprendere in qualsiasi momento:
il registro `results.jsonl` ricorda cosa è già stato salvato. A fine lavoro la scheda **Verifica finale**
confronta la lista con quanto salvato e con l'indice pubblico della Wayback Machine.

## License

Choose one before publishing (MIT is a common pick).
