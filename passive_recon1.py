import requests
import socket
import whois
import json
import argparse
import os
from datetime import datetime
from rich import print
from rich.console import Console
from rich.table import Table

console = Console()
session = requests.Session()

def banner():
    console.print("\n[bold cyan]🔍 Pro Passive Recon Tool[/bold cyan] by [green]ChatGPT[/green]")
    console.print("[yellow]Targeted Recon, Reporting & Automation for Bug Bounty Hunters[/yellow]\n")

def get_whois_info(domain):
    console.print("[blue][+] Getting WHOIS Info...[/blue]")
    try:
        w = whois.whois(domain)
        return {
            "domain": w.domain_name,
            "registrar": w.registrar,
            "created": str(w.creation_date),
            "emails": w.emails,
            "name_servers": w.name_servers
        }
    except Exception as e:
        console.print(f"[red][-] WHOIS error:[/red] {e}")
        return {}

def get_dns_info(domain):
    console.print("[blue][+] Getting DNS Info...[/blue]")
    dns_data = {}
    try:
        ip = socket.gethostbyname(domain)
        dns_data['A Record'] = ip
    except Exception:
        dns_data['A Record'] = 'N/A'

    try:
        result = socket.getaddrinfo(domain, None)
        dns_data['IPv6'] = list(set([i[4][0] for i in result if ':' in i[4][0]]))
    except Exception:
        dns_data['IPv6'] = 'N/A'

    return dns_data

def get_crtsh_subdomains(domain):
    console.print("[blue][+] Getting Subdomains from crt.sh...[/blue]")
    subdomains = set()
    try:
        url = f"https://crt.sh/?q=%25.{domain}&output=json"
        r = session.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            for item in data:
                for sub in item['name_value'].split('\n'):
                    if domain in sub:
                        subdomains.add(sub.strip())
    except Exception as e:
        console.print(f"[red][-] crt.sh Error:[/red] {e}")
    return sorted(subdomains)

def get_wayback_urls(domain):
    console.print("[blue][+] Getting Wayback Machine URLs...[/blue]")
    urls = []
    try:
        url = f"http://web.archive.org/cdx/search/cdx?url={domain}/*&output=json&fl=original&collapse=urlkey"
        r = session.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            urls = list(set([entry[0] for entry in data[1:]]))
    except Exception as e:
        console.print(f"[red][-] Wayback Error:[/red] {e}")
    return urls[:30]

def get_http_headers(domain):
    console.print("[blue][+] Getting HTTP Headers...[/blue]")
    headers = {}
    try:
        r = session.get(f"http://{domain}", timeout=10)
        headers = dict(r.headers)
    except Exception as e:
        console.print(f"[red][-] HTTP header fetch failed:[/red] {e}")
    return headers

def get_asn_info(domain):
    console.print("[blue][+] Getting ASN Info (IPinfo.io)...[/blue]")
    try:
        ip = socket.gethostbyname(domain)
        r = session.get(f"https://ipinfo.io/{ip}/json")
        if r.status_code == 200:
            data = r.json()
            return {
                "IP": ip,
                "ASN": data.get("org", "N/A"),
                "City": data.get("city", "N/A"),
                "Region": data.get("region", "N/A"),
                "Country": data.get("country", "N/A")
            }
    except Exception as e:
        console.print(f"[red][-] ASN Info Error:[/red] {e}")
    return {}

def save_report(domain, data):
    directory = "reports"
    os.makedirs(directory, exist_ok=True)
    filename = f"{directory}/{domain}_recon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Passive Recon Report for {domain}\n")
        f.write("="*50 + "\n\n")

        f.write("[+] WHOIS Info:\n")
        for k, v in data['whois'].items():
            f.write(f"{k}: {v}\n")

        f.write("\n[+] DNS Info:\n")
        for k, v in data['dns'].items():
            f.write(f"{k}: {v}\n")

        f.write("\n[+] ASN Info:\n")
        for k, v in data['asn'].items():
            f.write(f"{k}: {v}\n")

        f.write("\n[+] HTTP Headers:\n")
        for k, v in data['headers'].items():
            f.write(f"{k}: {v}\n")

        f.write("\n[+] Subdomains:\n")
        for s in data['subdomains']:
            f.write(f"{s}\n")

        f.write("\n[+] Wayback URLs:\n")
        for url in data['wayback']:
            f.write(f"{url}\n")

    console.print(f"\n[green][✓] Report saved to:[/green] {filename}")

def main():
    parser = argparse.ArgumentParser(description="Pro Passive Recon Script")
    parser.add_argument("-d", "--domain", help="Target domain (e.g. example.com)", required=True)
    args = parser.parse_args()
    domain = args.domain.strip()

    banner()

    recon_data = {
        "whois": get_whois_info(domain),
        "dns": get_dns_info(domain),
        "asn": get_asn_info(domain),
        "headers": get_http_headers(domain),
        "subdomains": get_crtsh_subdomains(domain),
        "wayback": get_wayback_urls(domain),
    }

    save_report(domain, recon_data)

if __name__ == "__main__":
    main()
