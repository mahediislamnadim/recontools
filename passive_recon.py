import requests
import socket
import whois
import json
import time

# ========= CONFIG =========
TARGET = "example.com"
CRT_SH_URL = f"https://crt.sh/?q=%25.{TARGET}&output=json"
WAYBACK_URL = f"http://web.archive.org/cdx/search/cdx?url={TARGET}/*&output=json&fl=original&collapse=urlkey"
# ==========================

def get_whois_info(domain):
    print("\n[+] Getting WHOIS Info...")
    try:
        w = whois.whois(domain)
        for key in ['domain_name', 'registrar', 'creation_date', 'emails', 'name_servers']:
            print(f"{key.capitalize()}: {w.get(key)}")
    except Exception as e:
        print("[-] WHOIS Error:", e)

def get_dns_info(domain):
    print("\n[+] Getting DNS Info...")
    try:
        ip = socket.gethostbyname(domain)
        print(f"A Record (IP): {ip}")
    except Exception as e:
        print("[-] DNS Error:", e)

def get_crtsh_subdomains():
    print("\n[+] Getting Subdomains from crt.sh...")
    try:
        r = requests.get(CRT_SH_URL)
        if r.status_code == 200:
            data = r.json()
            subdomains = set()
            for item in data:
                name = item['name_value']
                for sub in name.split('\n'):
                    if TARGET in sub:
                        subdomains.add(sub.strip())
            for sub in sorted(subdomains):
                print(f" - {sub}")
        else:
            print("[-] crt.sh error or rate-limited")
    except Exception as e:
        print("[-] crt.sh error:", e)

def get_wayback_urls():
    print("\n[+] Getting URLs from Wayback Machine...")
    try:
        r = requests.get(WAYBACK_URL)
        if r.status_code == 200:
            data = r.json()
            urls = set([entry[0] for entry in data[1:]])  # Skip header
            for url in sorted(urls)[:20]:  # Show only first 20
                print(f" - {url}")
        else:
            print("[-] Wayback request failed")
    except Exception as e:
        print("[-] Wayback Error:", e)

def get_http_headers(domain):
    print("\n[+] Getting HTTP Headers...")
    try:
        r = requests.get(f"http://{domain}", timeout=5)
        for k, v in r.headers.items():
            print(f"{k}: {v}")
    except Exception as e:
        print("[-] Header fetch failed:", e)

# ========= MAIN =========
if __name__ == "__main__":
    print(f"=== Passive Recon on: {TARGET} ===")
    
    get_whois_info(TARGET)
    get_dns_info(TARGET)
    get_crtsh_subdomains()
    get_wayback_urls()
    get_http_headers(TARGET)
    
    print("\n[✓] Recon Complete.")
