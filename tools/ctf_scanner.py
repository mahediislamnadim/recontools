#!/usr/bin/env python3
"""
ctf_scanner_selenium.py

Selenium-based scanner for JS-rendered pages (optional).
Saves rendered HTML and extracts custom tags/attributes & shadow DOM custom tags.
Outputs results to khoba_output/results.json and khoba_output/results.csv and saves HTML files into khoba_output/html/

This script prefers Selenium for rendering but falls back to requests+BeautifulSoup when Selenium
or Chrome is not available. The fallback won't execute JS but provides useful static analysis.
"""

import re
import json
import csv
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any
import concurrent.futures
import logging

import requests
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

# Selenium is optional; prefer it for JS-rendered pages but provide a requests-based fallback
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except Exception:
    SELENIUM_AVAILABLE = False

# ------------- Config defaults -------------
OUTPUT_DIR = Path("khoba_output")
HTML_DIR = OUTPUT_DIR / "html"
CSV_PATH = OUTPUT_DIR / "results.csv"
JSON_PATH = OUTPUT_DIR / "results.json"
LOG_FILE = OUTPUT_DIR / "scanner.log"

CONCURRENCY = 4
WAIT_AFTER_LOAD = 1.0  # seconds to wait after page load for JS
NAV_TIMEOUT = 30  # seconds (webdriver page_load_timeout)
# -------------------------------------------

# Ensure dirs exist before logging/file operations
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
HTML_DIR.mkdir(parents=True, exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding="utf-8")]
)


def safe_filename(url: str) -> str:
    invalid = r'[:\\/<>|?"*\s]'
    name = re.sub(invalid, "_", url)
    if len(name) > 200:
        name = name[:200]
    return name


def make_driver(show_browser: bool = False):
    opts = Options()
    if not show_browser:
        try:
            opts.add_argument("--headless=new")
        except Exception:
            opts.add_argument("--headless")
        opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,1000")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(NAV_TIMEOUT)
    return driver


def extract_from_html(html: str) -> Dict[str, List[str]]:
    """Parse raw HTML with BeautifulSoup to find custom element tags and custom attributes.
    Returns dict with keys: tags, attrs
    """
    if BeautifulSoup is None:
        # Minimal fallback: crude regex for tags and attributes (best-effort)
        tags = sorted(set(re.findall(r"<([a-zA-Z0-9\-]+)", html)))
        tags = [t for t in tags if '-' in t]
        attrs = sorted(set(re.findall(r"\b([a-zA-Z0-9\-]+)=\"", html)))
        attrs = [a for a in attrs if '-' in a and not a.startswith('aria-') and not a.startswith('data-')]
        return {"tags": tags, "attrs": attrs}

    soup = BeautifulSoup(html, "html.parser")
    tags_set = set()
    attrs_set = set()

    for el in soup.find_all(True):
        name = el.name or ''
        if '-' in name:
            tags_set.add(name.lower())
        for attr in el.attrs.keys():
            if attr and '-' in attr and not attr.startswith('aria-') and not attr.startswith('data-'):
                attrs_set.add(attr)

    return {
        "tags": sorted(tags_set),
        "attrs": sorted(attrs_set),
    }


def scan_single_url_selenium(url: str, show_browser: bool = False, wait_after: float = WAIT_AFTER_LOAD) -> Dict[str, Any]:
    """Use Selenium to render and extract dynamic content."""
    result = {
        "url": url,
        "ok": False,
        "status": None,
        "custom_tags": [],
        "registered_custom_elements": [],
        "custom_attributes": [],
        "saved_html": None,
        "error": None,
    "fetched_at": datetime.now(timezone.utc).isoformat()
    }

    driver = None
    try:
        logging.info(f"[selenium] Scanning: {url}")
        driver = make_driver(show_browser=show_browser)
        driver.get(url)
        time.sleep(wait_after)

        html = driver.page_source

        # Best-effort status retrieval
        try:
            res = driver.execute_script("return (performance.getEntriesByType('navigation')[0] || {}).responseStart || null;")
            result["status"] = None if res is None else 200
        except Exception:
            result["status"] = None

        # Extract via JS to capture shadow DOM and runtime-created custom elements
        js_extract = """
        (() => {
            const out = { tags: [], attrs: [], shadow_tags: [], registered: [] };
            try {
                const els = [...document.querySelectorAll('*')];
                const customEls = els.filter(e => e.tagName && e.tagName.includes('-'));
                out.tags = [...new Set(customEls.map(e => e.tagName.toLowerCase()))];

                const customAttrs = new Set();
                els.forEach(e => {
                    [...e.attributes].forEach(attr => {
                        if (attr && attr.name && attr.name.includes('-') && !attr.name.startsWith('aria-') && !attr.name.startsWith('data-')) {
                            customAttrs.add(attr.name);
                        }
                    });
                });
                out.attrs = Array.from(customAttrs);

                const found = new Set();
                function walk(node) {
                    if (!node) return;
                    if (node.shadowRoot) {
                        try {
                            const inner = [...node.shadowRoot.querySelectorAll('*')];
                            inner.forEach(e => { if (e.tagName && e.tagName.includes('-')) found.add(e.tagName.toLowerCase()); });
                        } catch(e){}
                    }
                    if (node.children) {
                        [...node.children].forEach(c => walk(c));
                    }
                }
                walk(document.documentElement);
                out.shadow_tags = Array.from(found);

                try { out.registered = out.tags.filter(t => !!customElements.get(t)); } catch(e){}
            } catch(e) {}
            return out;
        })();
        """
        dom_info = {}
        try:
            dom_info = driver.execute_script(js_extract) or {}
        except Exception as e:
            logging.debug(f"JS extraction failed for {url}: {e}")
            dom_info = {}

        tags = dom_info.get("tags") or []
        shadow_tags = dom_info.get("shadow_tags") or []
        attrs = dom_info.get("attrs") or []
        registered = dom_info.get("registered") or []

        merged_tags = list(dict.fromkeys(tags + shadow_tags))
        result["custom_tags"] = merged_tags
        result["custom_attributes"] = attrs
        result["registered_custom_elements"] = registered

        # save HTML
        filename = safe_filename(url) + ".html"
        path = HTML_DIR / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        result["saved_html"] = str(path)
        result["ok"] = True
        logging.info(f"[selenium] Done: {url} -> tags: {len(merged_tags)}, attrs: {len(attrs)}")

    except Exception as e:
        logging.exception(f"[selenium] Error scanning {url}: {e}")
        result["error"] = str(e)
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass

    return result


def scan_single_url_requests(url: str, wait_after: float = WAIT_AFTER_LOAD) -> Dict[str, Any]:
    """Fallback scanner using requests (no JS execution)."""
    result = {
        "url": url,
        "ok": False,
        "status": None,
        "custom_tags": [],
        "registered_custom_elements": [],
        "custom_attributes": [],
        "saved_html": None,
        "error": None,
    "fetched_at": datetime.now(timezone.utc).isoformat()
    }
    headers = {"User-Agent": "ctf-scanner/1.0 (+https://github.com)"}
    try:
        logging.info(f"[requests] Fetching: {url}")
        r = requests.get(url, headers=headers, timeout=NAV_TIMEOUT, allow_redirects=True)
        result["status"] = r.status_code
        html = r.text

        info = extract_from_html(html)
        result["custom_tags"] = info.get("tags", [])
        result["custom_attributes"] = info.get("attrs", [])

        # save HTML
        filename = safe_filename(url) + ".html"
        path = HTML_DIR / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        result["saved_html"] = str(path)
        result["ok"] = True
        logging.info(f"[requests] Done: {url} -> tags: {len(result['custom_tags'])}, attrs: {len(result['custom_attributes'])}")
    except Exception as e:
        logging.exception(f"[requests] Error scanning {url}: {e}")
        result["error"] = str(e)
    return result


def read_urls(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
    return lines


def save_outputs(results: List[Dict[str, Any]]):
    # JSON
    with open(JSON_PATH, "w", encoding="utf-8") as jf:
        json.dump(results, jf, indent=2, ensure_ascii=False)

    # CSV
    keys = ["url", "ok", "status", "custom_tags", "registered_custom_elements", "custom_attributes", "saved_html", "error", "fetched_at"]
    with open(CSV_PATH, "w", encoding="utf-8", newline='') as cf:
        writer = csv.DictWriter(cf, fieldnames=keys)
        writer.writeheader()
        for r in results:
            row = {k: (json.dumps(r.get(k), ensure_ascii=False) if isinstance(r.get(k), (list, dict)) else r.get(k)) for k in keys}
            writer.writerow(row)


def main():
    ap = argparse.ArgumentParser(description="CTF scanner (Selenium-based) - extract custom tags/attributes")
    ap.add_argument("-i", "--input", required=True, help="input file with one URL per line")
    ap.add_argument("--concurrency", type=int, default=CONCURRENCY, help="number of concurrent workers")
    ap.add_argument("--wait", type=float, default=WAIT_AFTER_LOAD, help="seconds to wait after page load")
    ap.add_argument("--show-browser", action="store_true", help="show browser for debugging")
    args = ap.parse_args()

    urls = read_urls(args.input)
    logging.info(f"Loaded {len(urls)} urls from {args.input}")

    results = []
    # Choose method based on availability
    use_selenium = SELENIUM_AVAILABLE
    if use_selenium:
        logging.info("Selenium is available: using Selenium-based rendering")
    else:
        logging.info("Selenium not available: using static requests fallback (no JS)")

    # ThreadPoolExecutor to parallelize
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        if use_selenium:
            futures = [ex.submit(scan_single_url_selenium, u, args.show_browser, args.wait) for u in urls]
        else:
            futures = [ex.submit(scan_single_url_requests, u, args.wait) for u in urls]

        for fut in concurrent.futures.as_completed(futures):
            try:
                res = fut.result()
            except Exception as e:
                logging.exception(f"Worker exception: {e}")
                res = {"url": "unknown", "error": str(e), "ok": False}
            results.append(res)

    save_outputs(results)
    logging.info(f"Saved JSON -> {JSON_PATH} CSV -> {CSV_PATH} HTMLs -> {HTML_DIR.resolve()}")
    print(f"Done. Results: {CSV_PATH} and {JSON_PATH}")


if __name__ == "__main__":
    main()

