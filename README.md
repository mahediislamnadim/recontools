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
