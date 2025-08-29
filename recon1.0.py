import requests
import socket
import whois
import json
import argparse
import os
from datetime import datetime
from rich import print
from rich.console import Console
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

console = Console()

# Configure a requests session with retries and a friendly User-Agent
session = requests.Session()
RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"],
)
adapter = HTTPAdapter(max_retries=RETRY_STRATEGY)
session.mount("https://", adapter)
session.mount("http://", adapter)
session.headers.update({"User-Agent": "ProPassiveRecon/1.0 (+https://example.com)"})


def banner():
    console.print("\n[bold cyan]🔍 Pro Passive Recon Tool[/bold cyan] by [green]AI Helper[/green]")
    console.print("[yellow]Targeted Recon, Reporting & Automation for Bug Bounty Hunters[/yellow]\n")


def safe_str(v):
    try:
        if v is None:
            return "N/A"
        if isinstance(v, (list, set, tuple)):
            return ", ".join([str(x) for x in v])
        return str(v)
    except Exception:
        return "N/A"


def get_whois_info(domain):
    console.print("[blue][+] Getting WHOIS Info...[/blue]")
    try:
        w = whois.whois(domain)
        return {
            "domain": safe_str(w.domain_name),
            "registrar": safe_str(w.registrar),
            "created": safe_str(w.creation_date),
            "emails": safe_str(w.emails),
            "name_servers": safe_str(w.name_servers),
        }
    except Exception as e:
        console.print(f"[red][-] WHOIS error:[/red] {e}")
        return {}


def get_dns_info(domain):
    console.print("[blue][+] Getting DNS Info...[/blue]")
    dns_data = {}
    try:
        ip = socket.gethostbyname(domain)
        dns_data["A Record"] = ip
    except Exception:
        dns_data["A Record"] = "N/A"

    try:
        result = socket.getaddrinfo(domain, None)
        ipv6 = list({i[4][0] for i in result if ':' in i[4][0]})
        dns_data["IPv6"] = ipv6 or "N/A"
    except Exception:
        dns_data["IPv6"] = "N/A"

    return dns_data


def get_crtsh_subdomains(domain):
    console.print("[blue][+] Getting Subdomains from crt.sh...[/blue]")
    subdomains = set()
    try:
        url = f"https://crt.sh/?q=%25.{domain}&output=json"
        r = session.get(url, timeout=10)
        if r.status_code == 200:
            try:
                data = r.json()
                for item in data:
                    for sub in str(item.get('name_value', '')).split('\n'):
                        sub = sub.strip()
                        if sub and domain in sub:
                            subdomains.add(sub)
            except ValueError:
                console.print("[yellow]crt.sh returned non-JSON response[/yellow]")
    except Exception as e:
        console.print(f"[red][-] crt.sh Error:[/red] {e}")
    return sorted(subdomains)


def get_wayback_urls(domain, limit=30):
    console.print("[blue][+] Getting Wayback Machine URLs...[/blue]")
    urls = []
    try:
        url = f"http://web.archive.org/cdx/search/cdx?url={domain}/*&output=json&fl=original&collapse=urlkey"
        r = session.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            urls = list({entry[0] for entry in data[1:]})
    except Exception as e:
        console.print(f"[red][-] Wayback Error:[/red] {e}")
    return list(urls)[:limit]


def get_http_headers(domain):
    console.print("[blue][+] Getting HTTP Headers...[/blue]")
    headers = {}
    for scheme in ("https://", "http://"):
        try:
            r = session.get(f"{scheme}{domain}", timeout=10, allow_redirects=True)
            if r.status_code:
                headers = dict(r.headers)
                headers['status_code'] = r.status_code
                headers['url'] = r.url
                break
        except Exception:
            continue
    if not headers:
        console.print("[yellow]Could not fetch HTTP headers for http(s) schemes[/yellow]")
    return headers


def get_asn_info(domain):
    console.print("[blue][+] Getting ASN Info (ipinfo.io)...[/blue]")
    try:
        ip = socket.gethostbyname(domain)
        r = session.get(f"https://ipinfo.io/{ip}/json", timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {
                "IP": ip,
                "ASN": data.get("org", "N/A"),
                "City": data.get("city", "N/A"),
                "Region": data.get("region", "N/A"),
                "Country": data.get("country", "N/A"),
            }
    except Exception as e:
        console.print(f"[red][-] ASN Info Error:[/red] {e}")
    return {}


def save_report_text(domain, data, outdir):
    os.makedirs(outdir, exist_ok=True)
    filename = os.path.join(outdir, f"{domain}_recon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Passive Recon Report for {domain}\n")
        f.write("=" * 50 + "\n\n")

        f.write("[+] WHOIS Info:\n")
        for k, v in (data.get('whois') or {}).items():
            f.write(f"{k}: {v}\n")

        f.write("\n[+] DNS Info:\n")
        for k, v in (data.get('dns') or {}).items():
            f.write(f"{k}: {v}\n")

        f.write("\n[+] ASN Info:\n")
        for k, v in (data.get('asn') or {}).items():
            f.write(f"{k}: {v}\n")

        f.write("\n[+] HTTP Headers:\n")
        for k, v in (data.get('headers') or {}).items():
            f.write(f"{k}: {v}\n")

        f.write("\n[+] Subdomains:\n")
        for s in (data.get('subdomains') or []):
            f.write(f"{s}\n")

        f.write("\n[+] Wayback URLs:\n")
        for url in (data.get('wayback') or []):
            f.write(f"{url}\n")

    console.print(f"\n[green][✓] Text report saved to:[/green] {filename}")
    return filename


def save_report_json(domain, data, outdir):
    os.makedirs(outdir, exist_ok=True)
    filename = os.path.join(outdir, f"{domain}_recon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

    def clean(obj):
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items()}
        if isinstance(obj, (list, set, tuple)):
            return [clean(i) for i in obj]
        return safe_str(obj)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(clean({"domain": domain, "generated": datetime.utcnow().isoformat(), **data}), f, indent=2)

    console.print(f"\n[green][✓] JSON report saved to:[/green] {filename}")
    return filename


def normalize_domain(d):
    d = d.strip()
    for p in ("http://", "https://"):
        if d.startswith(p):
            d = d[len(p):]
    return d.rstrip('/')


def main():
    parser = argparse.ArgumentParser(description="Pro Passive Recon Script")
    parser.add_argument("-d", "--domain", help="Target domain (e.g. example.com)", required=True)
    parser.add_argument("-o", "--outdir", help="Output directory", default="reports")
    parser.add_argument("--json", help="Also save JSON report", action="store_true")
    parser.add_argument("--limit-wayback", help="Limit wayback URLs", type=int, default=30)
    args = parser.parse_args()

    domain = normalize_domain(args.domain)

    banner()

    recon_data = {
        "whois": get_whois_info(domain),
        "dns": get_dns_info(domain),
        "asn": get_asn_info(domain),
        "headers": get_http_headers(domain),
        "subdomains": get_crtsh_subdomains(domain),
        "wayback": get_wayback_urls(domain, limit=args.limit_wayback),
    }

    text_file = save_report_text(domain, recon_data, args.outdir)
    json_file = None
    if args.json:
        json_file = save_report_json(domain, recon_data, args.outdir)

    console.print("\n[cyan]Done.\nSummary:[/cyan]")
    console.print(f"Text report: [green]{text_file}[/green]")
    if json_file:
        console.print(f"JSON report: [green]{json_file}[/green]")


if __name__ == "__main__":
    main()
