# active-recon

This repository contains active and passive reconnaissance helpers and orchestration scripts.

Primary artifact in this workspace:

- `tools/active_recon_scan.sh` - powerful bash-based active recon orchestration. It runs `nmap`, `nikto`, `whatweb`, `gobuster`/`dirb`, `curl` headers, optional TLS checks (`sslscan`/`sslyze`), and saves outputs under a per-target directory.

Quick usage

```bash
# dry-run and show full commands
bash tools/active_recon_scan.sh --dry-run --show-commands -t example.com

# run aggressively (extra nmap scripts, ssl checks)
bash tools/active_recon_scan.sh --aggressive -t example.com -o /tmp/outdir

# use custom wordlist and extra nmap args
bash tools/active_recon_scan.sh -t example.com --wordlist /tmp/mywordlist.txt --nmap-args "-sV"
```

Key flags

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

- The script checks for presence of external tools and skips missing tools with a warning.
- Use `--dry-run` + `--show-commands` to preview exactly what will be executed before running a scan that hits external infrastructure.

How to publish to GitHub from this folder

Option A — Quick (using GitHub CLI `gh`):

1. Authenticate locally:

```bash
gh auth login
```

2. Create and push the repo (replace owner/name as appropriate):

```bash
gh repo create mahediislamnadim/active-recon --public --source=. --remote=origin --push
```

Option B — Create repo on GitHub web UI:

1. Create a new repository named `active-recon` in your account via https://github.com/new
2. From this folder run (replace URL):

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
