# active-recon (passive + active recon toolkit)

This repository collects a set of reconnaissance helpers useful for bug bounties and pentests. It now includes both passive recon scripts and an opinionated active recon orchestration script.

Contents overview

- `recon1.0.py` (previously `Test.py`) — passive recon helper (WHOIS, DNS, crt.sh, Wayback, headers, ASN) that writes timestamped reports to `reports/`.
- `tools/ctf_scanner.py` — auxiliary scanner that extracts interesting HTML tags/attributes from URLs (static requests mode + optional Selenium dynamic mode).
- `tools/active_recon_scan.sh` — active recon orchestrator that runs `nmap`, `nikto`, `whatweb`, `gobuster`/`dirb`, `curl` headers, optional TLS checks (`sslscan`/`sslyze`), and saves structured outputs per target.

Quick start

1. Create a Python virtualenv and install requirements for the Python tools (Selenium optional):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Passive recon (single target):

```bash
python recon1.0.py -d example.com
# or if you still have Test.py: python Test.py -d example.com
```

3. Static HTML extraction (ctf scanner):

```bash
printf "http://example.com\n" > urls.txt
python3 tools/ctf_scanner.py -i urls.txt --concurrency 4
```

4. Active recon orchestration (bash):

```bash
# preview commands (safe)
bash tools/active_recon_scan.sh --dry-run --show-commands -t example.com

# real run (aggressive mode enables extra nmap scripts and TLS checks)
bash tools/active_recon_scan.sh --aggressive -t example.com -o /tmp/outdir
```

Key flags for the active orchestrator

- `-t, --target` : target hostname or file with targets (one per line) (required)
- `-o, --output` : output directory (default `khoba_active`)
- `--dry-run` : print commands instead of executing
- `--show-commands` : print the fully-expanded command lines
- `--aggressive` : enable extra nmap scripts, TLS checks, and higher gobuster threads
- `--wordlist` : path to wordlist for directory discovery (default `/usr/share/wordlists/dirb/common.txt`)
- `--nmap-args` : extra args to append to nmap
- `--gobuster-args` : extra args to append to gobuster
- `-c, --concurrency` : max parallel targets when processing a file (default 10)

Notes

- External tools (nmap, nikto, gobuster/dirb, whatweb, curl, sslscan/sslyze) must be installed separately. The script checks for their presence and skips missing tools.
- Use `--dry-run` + `--show-commands` to preview commands before executing against live targets.

Publishing to GitHub

Option A — Quick (using GitHub CLI `gh`):

```bash
gh auth login
gh repo create mahediislamnadim/active-recon --public --source=. --remote=origin --push
```

Option B — Create the repo in the GitHub web UI and push from this folder:

```bash
git remote set-url origin https://github.com/mahediislamnadim/active-recon.git
git push -u origin main
```

If you want me to push the commits for you, create the remote on GitHub and paste the HTTPS repo URL here; I will update the remote and push.

License

MIT — see LICENSE if present.
# recontools

Pro Passive Recon Tool — a lightweight passive reconnaissance script for Bug Bounty and pentest workflows.

This repository includes a small set of tools. The primary script demonstrated here is `Test.py`, which performs passive recon for a target domain and writes a timestamped report to the `reports/` directory.

## Features

- WHOIS lookup
- DNS resolution (A / IPv6)
- crt.sh subdomain enumeration
- Wayback Machine URL harvesting (limited)
- HTTP header retrieval
- ASN lookup via ipinfo.io
- Saves human-readable timestamped reports to `reports/`

## Requirements

Use a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Run the passive recon script against a domain:

```bash
python Test.py -d example.com
```

Options
- `-d`, `--domain`: Target domain (required)

Example

```bash
python Test.py -d mahediislamnadim.github.io
```

Reports will be saved under the `reports/` folder as a timestamped `.txt` file.

## Notes & Limitations

- The script performs only passive information gathering. Do not use it for intrusive scanning unless you have permission.
- External services (crt.sh, Wayback, ipinfo) may rate-limit or return partial results.
- `python-whois` can return different date formats; fields are written as strings in the report.

## Contributing

Contributions welcome — open issues or PRs on GitHub: https://github.com/mahediislamnadim/recontools

## License

Add a LICENSE file if you want to specify terms.

## tools/ctf_scanner.py (optional dynamic scanning)

The `tools/ctf_scanner.py` script is an auxiliary scanner that extracts interesting HTML tags and attributes from a list of URLs. It supports two modes:

- Static (default): Uses `requests` + BeautifulSoup to fetch and parse HTML. This mode works without a browser or Selenium and is suitable for most quick checks.
- Dynamic (optional): If `selenium` and a browser driver (e.g., Chrome + chromedriver) are available, the scanner will use Selenium to render JavaScript and extract content that only appears after page load.

Basic usage (static):

```bash
printf "http://example.com\n" > urls.txt
python3 tools/ctf_scanner.py -i urls.txt --concurrency 4
```

If Selenium is available and you want dynamic rendering, install the optional dependencies from `requirements.txt` and run the scanner normally; it will auto-detect Selenium and use it.

Outputs:
- khoba_output/results.json - per-URL JSON summary
- khoba_output/results.csv  - CSV summary
- khoba_output/html/        - saved HTML files per URL

Note: Dynamic Selenium runs require a working browser driver. If Selenium is missing, the scanner falls back to the static requests-based extractor.
